"""Monte Carlo over slicer settings for one model: samples settings, slices each with Bambu Studio, and scores time, filament and print-quality proxies from the G-code."""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import time

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from coverage import uncovered
from gcode_paths import config_value, plate_transform, read_paths
from islands_supported import check as check_islands
from islands_supported import gap_layers_of, layer_tops

BAMBU = "/Applications/BambuStudio.app/Contents/MacOS/BambuStudio"
HERE = pathlib.Path(__file__).resolve().parent
# Settings that change the print's geometry, support or material; speeds and temperatures change quality in ways geometry cannot measure, so they stay at the profile's values
SPACE = {
    "layer_height": [0.08, 0.12, 0.16, 0.2, 0.24, 0.28],
    "wall_loops": [2, 3, 4],
    "sparse_infill_density": ["5%", "10%", "15%", "20%"],
    "sparse_infill_pattern": ["grid", "gyroid", "lightning", "adaptivecubic"],
    "wall_generator": ["classic", "arachne"],
    "top_shell_layers": [3, 4, 5],
    "bottom_shell_layers": [2, 3],
    "support_threshold_angle": [20, 25, 30, 35, 40],
    "tree_support_branch_angle": [30, 40, 45, 55],
    "support_top_z_distance": [0.15, 0.2, 0.25],
    "support_interface_top_layers": [1, 2, 3],
}
BASELINE = {"layer_height": 0.2, "wall_loops": 2, "sparse_infill_density": "15%", "sparse_infill_pattern": "grid", "wall_generator": "classic", "top_shell_layers": 5, "bottom_shell_layers": 3, "support_threshold_angle": 30, "tree_support_branch_angle": 45, "support_top_z_distance": 0.2, "support_interface_top_layers": 2}


def sample_settings(rng):
    """One setting per key, uniformly from SPACE."""
    return {k: v[rng.integers(len(v))] for k, v in SPACE.items()}


def parse_duration(text):
    """Seconds in a Bambu duration such as '1d 3h 50m 27s'."""
    units = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    return sum(int(n) * units[u] for n, u in re.findall(r"(\d+)([dhms])", text))


def cusp_heights(mesh, tops):
    """Stair-step height each face is left with: the thickness of the layer it falls in times its normal's vertical component; flat faces lie on a layer boundary and have none."""
    thickness = np.diff(np.r_[0.0, tops])
    layer = np.clip(np.searchsorted(tops, mesh.triangles_center[:, 2]), 0, len(tops) - 1)
    nz = np.abs(mesh.face_normals[:, 2])
    return np.where(nz > 0.999, 0.0, thickness[layer] * nz)


def slice_once(settings, stl, work, machine, filament):
    """Slices stl with the settings applied to the flattened process profile; returns the G-code and 3MF paths and the slicing seconds."""
    work.mkdir(parents=True, exist_ok=True)
    process = work / "process.json"
    base = json.loads((HERE / "profiles" / "process-tree.json").read_text())
    for k, v in settings.items():
        base[k] = str(v)
    process.write_text(json.dumps(base, indent=2))
    t0 = time.time()
    log = open(work / "cli.log", "w")
    subprocess.run([BAMBU, "--debug", "1", "--orient", "0", "--arrange", "1", "--load-settings", f"{machine};{process}", "--load-filaments", str(filament), "--slice", "0", "--export-3mf", "sample.3mf", "--outputdir", str(work), str(stl)], stdout=log, stderr=subprocess.STDOUT, check=False)
    gcode, three_mf = work / "plate_1.gcode", work / "sample.3mf"
    if not gcode.exists() or not three_mf.exists():
        raise RuntimeError(f"slice failed, see {work / 'cli.log'}")
    return gcode, three_mf, time.time() - t0


def score(gcode, three_mf, mesh_stl, surface_stl, islands):
    """Cost and quality proxies for one sliced G-code."""
    header = {}
    for line in open(gcode):
        if "total estimated time:" in line:
            header["time_s"] = parse_duration(line.split("total estimated time:")[-1])
        elif line.startswith("; total filament weight"):
            header["filament_g"] = float(line.split(":")[-1].split(",")[0])
    paths = read_paths(gcode, 0.3)
    width = float(config_value(gcode, "outer_wall_line_width") or 0.42)
    density = float(config_value(gcode, "filament_density").split(",")[0])
    diameter = float(config_value(gcode, "filament_diameter").split(",")[0])
    support_mm = 0.0
    feature = None
    for line in open(gcode):
        if line.startswith("; FEATURE: "):
            feature = line[11:].strip()
        elif feature and feature.startswith("Support") and line.startswith(("G1 ", "G2 ", "G3 ")) and " E" in line and (" X" in line or " Y" in line):
            m = re.search(r" E(-?[\d.]+)", line.split(";")[0])
            if m and float(m.group(1)) > 0:
                support_mm += float(m.group(1))
    support_g = support_mm * np.pi * (diameter / 2) ** 2 / 1000 * density
    to_plate = plate_transform(three_mf, mesh_stl.bounds)
    mesh = mesh_stl.copy()
    mesh.apply_transform(to_plate)
    tops = layer_tops(paths)
    gap = gap_layers_of(gcode)
    cusp = cusp_heights(mesh, tops)
    area = mesh.area_faces
    # Lost detail: model surface with no model extrusion near it, which is where a thin feature was dropped
    model = paths["model"]
    lost = uncovered(trimesh.transform_points(surface_stl, to_plate), model, tops, width)
    # Support scarring: top interface cells with model resting on them within the support gap
    inter = paths["interface"]
    scar_cells = set()
    if len(inter):
        mt = cKDTree(np.c_[model[:, :2], model[:, 2] * 1000])
        for k in range(1, gap + 2):
            hit = mt.query(np.c_[inter[:, :2], (inter[:, 2] + k) * 1000], distance_upper_bound=0.5)[0] < 0.5
            scar_cells.update(map(tuple, np.floor(inter[hit, :2] / 0.5).astype(int).tolist()))
    # Unsupported overhang: faces turned more than 45 degrees from vertical toward the bed, with nothing printed under them within the support gap
    down = (mesh.face_normals[:, 2] < -np.cos(np.radians(45))) & (mesh.triangles_center[:, 2] > tops[0] + 0.05)
    allp = np.concatenate([v for v in paths.values() if len(v)])
    at = cKDTree(np.c_[allp[:, :2], allp[:, 2] * 1000])
    c = mesh.triangles_center[down]
    fl = np.clip(np.searchsorted(tops, c[:, 2] - 1e-6), 0, len(tops) - 1)
    held = np.zeros(len(c), bool)
    for k in range(1, gap + 2):
        held |= at.query(np.c_[c[:, :2], (fl - k) * 1000], distance_upper_bound=1.0)[0] < 1.0
    isl = check_islands(paths, islands, to_plate, gap)
    return {
        **header,
        "support_g": round(support_g, 1),
        "layers": len(tops),
        "cusp_mean_mm": round(float((cusp * area).sum() / area.sum()), 4),
        "cusp_p95_mm": round(float(np.percentile(np.repeat(cusp, np.maximum(1, (area / area.mean()).round().astype(int))), 95)), 4),
        "lost_detail_pct": round(100 * float(lost.mean()), 3),
        "scar_area_mm2": round(len(scar_cells) * 0.25, 1),
        "unsupported_overhang_mm2": round(float(mesh.area_faces[down][~held].sum()), 1),
        "unsupported_islands": len(isl["unsupported"]),
        "unsupported_island_mm2": round(sum(i["area_mm2"] for i in isl["unsupported"]), 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stl")
    ap.add_argument("check_json", help="check_print.py report for the same STL, for its islands")
    ap.add_argument("--samples", type=int, default=50)
    ap.add_argument("--baseline-repeats", type=int, default=3, help="slice the default settings this many times to measure run-to-run noise")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="monte-carlo.jsonl")
    ap.add_argument("--work", default="/tmp/slice-monte-carlo")
    args = ap.parse_args()
    mesh = trimesh.load(args.stl)
    mesh.apply_translation(-mesh.bounds[0])
    surface, _ = trimesh.sample.sample_surface(mesh, 200_000, seed=0)
    islands = json.loads(pathlib.Path(args.check_json).read_text())["islands"]["list"]
    done = set()
    out = pathlib.Path(args.out)
    if out.exists():
        done = {json.dumps(json.loads(line)["settings"], sort_keys=True) + str(json.loads(line).get("repeat", 0)) for line in out.read_text().splitlines() if line.strip()}
    rng = np.random.default_rng(args.seed)
    plan = [(BASELINE, r) for r in range(args.baseline_repeats)] + [(sample_settings(rng), 0) for _ in range(args.samples)]
    for i, (settings, repeat) in enumerate(plan):
        key = json.dumps(settings, sort_keys=True) + str(repeat)
        if key in done:
            continue
        work = pathlib.Path(args.work) / f"s{i:03d}"
        shutil.rmtree(work, ignore_errors=True)
        row = {"i": i, "settings": settings, "repeat": repeat, "baseline": settings == BASELINE}
        try:
            gcode, three_mf, secs = slice_once(settings, args.stl, work, HERE / "profiles" / "machine.json", HERE / "profiles" / "pla.json")
            row.update(score(gcode, three_mf, mesh, surface, islands), slice_s=round(secs))
        except Exception as e:
            row["error"] = str(e)
        # G-code at fine layers runs to 100 MB, so keep only the scores
        shutil.rmtree(work, ignore_errors=True)
        with out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(i, {k: row.get(k) for k in ("time_s", "filament_g", "support_g", "cusp_mean_mm", "lost_detail_pct", "scar_area_mm2", "unsupported_overhang_mm2", "unsupported_islands", "error")}, flush=True)


if __name__ == "__main__":
    main()
