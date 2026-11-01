"""Reads extrusion paths from a Bambu G-code file as points sampled along each extruding move, grouped by feature."""
import json
import re
import zipfile

import numpy as np

MOVE = re.compile(r"^G[123] (.*)")
SKIPPED = ("Brim", "Skirt", "Custom", "Prime tower", None)


def read_paths(path, step_mm=0.5):
    """Returns {"support", "interface", "model"} -> array of (x, y, layer index, z) points, sampled every step_mm along each move that extrudes."""
    feature, layer, z, x, y = None, -1, 0.0, 0.0, 0.0
    pts = {"support": [], "interface": [], "model": []}
    for line in open(path):
        if line.startswith("; FEATURE: "):
            feature = line[11:].strip()
            continue
        if line.startswith("; CHANGE_LAYER"):
            layer += 1
            continue
        if line.startswith("; Z_HEIGHT: "):
            z = float(line[12:])
            continue
        m = MOVE.match(line)
        if not m:
            continue
        args = dict((w[0], float(w[1:])) for w in m.group(1).split(";")[0].split() if w[0] in "XYEIJ" and len(w) > 1)
        nx, ny = args.get("X", x), args.get("Y", y)
        # Moves with E but no XY are unretracts, not extrusion
        if args.get("E", 0) > 0 and ("X" in args or "Y" in args) and layer >= 0 and feature not in SKIPPED:
            key = "interface" if feature == "Support interface" else "support" if feature.startswith("Support") else "model"
            if line[1] in "23":
                px, py = arc(x, y, nx, ny, args.get("I", 0.0), args.get("J", 0.0), line[1] == "3", step_mm)
            else:
                t = np.linspace(0, 1, max(1, int(np.hypot(nx - x, ny - y) / step_mm)) + 1)
                px, py = x + (nx - x) * t, y + (ny - y) * t
            pts[key].append(np.stack([px, py, np.full_like(px, layer), np.full_like(px, z)], axis=1))
        x, y = nx, ny
    return {k: np.concatenate(v) if v else np.zeros((0, 4)) for k, v in pts.items()}


def arc(x, y, nx, ny, i, j, ccw, step_mm):
    """Points every step_mm or less along a G2 (clockwise) or G3 (counter-clockwise) arc from (x, y) to (nx, ny) about the centre (x + i, y + j); equal ends mean a full circle."""
    cx, cy = x + i, y + j
    a0, a1 = np.arctan2(y - cy, x - cx), np.arctan2(ny - cy, nx - cx)
    sweep = (a1 - a0) % (2 * np.pi) if ccw else -((a0 - a1) % (2 * np.pi))
    if np.isclose(sweep, 0) and np.isclose(x, nx) and np.isclose(y, ny):
        sweep = 2 * np.pi if ccw else -2 * np.pi
    r0, r1 = np.hypot(x - cx, y - cy), np.hypot(nx - cx, ny - cy)
    t = np.linspace(0, 1, max(1, int(np.ceil(max(r0, r1) * abs(sweep) / step_mm))) + 1)
    r, a = r0 + (r1 - r0) * t, a0 + sweep * t
    px, py = cx + r * np.cos(a), cy + r * np.sin(a)
    px[-1], py[-1] = nx, ny
    return px, py


def config_value(path, key):
    """A value from the settings block Bambu appends to the G-code, as a string, or None."""
    prefix = f"; {key} = "
    for line in open(path):
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None


def plate_transform(three_mf, stl_bounds):
    """4x4 matrix from STL coordinates to G-code coordinates: the slicer centres the object, arranging may rotate it about Z and move it, and the G-code sits the printer's extruder_offset away from the plate (0x2 on a P1S)."""
    archive = zipfile.ZipFile(three_mf)
    model = archive.read("3D/3dmodel.model").decode()

    def matrix(tag):
        v = [float(t) for t in re.search(rf'<{tag} [^>]*transform="([^"]+)"', model).group(1).split()]
        m = np.eye(4)
        m[:3, :3], m[:3, 3] = np.array(v[:9]).reshape(3, 3).T, v[9:]
        return m

    centre = np.eye(4)
    centre[:3, 3] = -np.asarray(stl_bounds).mean(0)
    nozzle = np.eye(4)
    if "Metadata/project_settings.config" in archive.namelist():
        offset = json.loads(archive.read("Metadata/project_settings.config")).get("extruder_offset", ["0x0"])[0]
        nozzle[:2, 3] = -np.array([float(v) for v in offset.split("x")])
    return nozzle @ matrix("item") @ matrix("component") @ centre
