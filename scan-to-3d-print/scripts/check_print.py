"""Pre-print check for a Z-up STL: local wall thickness, overhangs that need support, and islands that start in mid-air."""
import argparse
import json
import pathlib

import matplotlib
import numpy as np
import scipy.sparse
import trimesh
from scipy.spatial import cKDTree

from printcheck import find_islands, self_intersections, wall_thickness
from printcheck import needs_support as needs_support_faces

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("stl")
ap.add_argument("--nozzle-mm", type=float, default=0.4)
ap.add_argument("--layer-mm", type=float, default=0.2)
ap.add_argument("--support-angle", type=float, default=30.0, help="slicer threshold: surfaces flatter than this many degrees from horizontal need support")
ap.add_argument("--slender-mm", type=float, default=2.5, help="prints, but can snap when handled or when supports are removed")
ap.add_argument("--min-island-mm2", type=float, default=0.05)
ap.add_argument("--out-dir", default=".")
args = ap.parse_args()

mesh = trimesh.load(args.stl)
mesh.apply_translation(-mesh.bounds[0])
name = pathlib.Path(args.stl).stem
out_dir = pathlib.Path(args.out_dir)
fail_mm = 2 * args.nozzle_mm
warn_mm = 3 * args.nozzle_mm
print(f"{name}: {len(mesh.faces)} faces, extent {np.round(mesh.extents, 1).tolist()} mm, watertight {mesh.is_watertight}")

thickness, hit = wall_thickness(mesh)
needs_support = needs_support_faces(mesh, args.support_angle, args.layer_mm)
overhang_45 = needs_support_faces(mesh, 45, args.layer_mm)
islands = find_islands(mesh, args.layer_mm, args.min_island_mm2)
crossings = self_intersections(mesh)


def describe(c):
    """Names a location from its position in the model's bounding box (Z up, front toward -Y); rename the zones for a particular model."""
    fx, fy, fz = (c - mesh.bounds[0]) / mesh.extents
    if fz < 0.15:
        return "base"
    height = "lower" if fz < 0.5 else "upper"
    side = "left" if fx < 0.3 else "right" if fx > 0.7 else "middle"
    return f"{height} {side} {'front' if fy < 0.35 else 'back'}"


# Group thin vertices into connected regions so the report lists places, not points
thin = thickness < warn_mm
edges = mesh.edges_unique
both = thin[edges[:, 0]] & thin[edges[:, 1]]
graph = scipy.sparse.coo_matrix((np.ones(both.sum()), (edges[both, 0], edges[both, 1])), shape=(len(thin),) * 2)
n_comp, labels = scipy.sparse.csgraph.connected_components(graph, directed=False)
vertex_area = np.zeros(len(mesh.vertices))
np.add.at(vertex_area, mesh.faces.ravel(), np.repeat(mesh.area_faces / 3, 3))
regions = []
for lab in np.unique(labels[thin]):
    sel = (labels == lab) & thin
    area = vertex_area[sel].sum()
    if area < 0.5:
        continue
    pts = mesh.vertices[sel]
    regions.append({
        "where": describe(pts.mean(0)),
        "min_thickness_mm": round(float(thickness[sel].min()), 2),
        "below_fail_mm2": round(float(vertex_area[sel & (thickness < fail_mm)].sum()), 1),
        "area_mm2": round(float(area), 1),
        "center_mm": np.round(pts.mean(0), 1).tolist(),
    })
regions.sort(key=lambda r: -r["below_fail_mm2"])


def group(mask, min_area):
    """Connected regions of flagged vertices, largest first."""
    keep = mask[edges[:, 0]] & mask[edges[:, 1]]
    g = scipy.sparse.coo_matrix((np.ones(keep.sum()), (edges[keep, 0], edges[keep, 1])), shape=(len(mask),) * 2)
    _, lab = scipy.sparse.csgraph.connected_components(g, directed=False)
    found = []
    for k in np.unique(lab[mask]):
        sel = (lab == k) & mask
        area = vertex_area[sel].sum()
        if area >= min_area:
            pts = mesh.vertices[sel]
            found.append({"where": describe(pts.mean(0)), "min_thickness_mm": round(float(thickness[sel].min()), 2), "area_mm2": round(float(area), 1), "center_mm": np.round(pts.mean(0), 1).tolist()})
    return sorted(found, key=lambda r: -r["area_mm2"])


slender_regions = group(thickness < args.slender_mm, 2.0)

total = mesh.area
report = {
    "file": args.stl,
    "extent_mm": np.round(mesh.extents, 1).tolist(),
    "nozzle_mm": args.nozzle_mm,
    "watertight": bool(mesh.is_watertight),
    "bodies": len(mesh.split(only_watertight=False)),
    "self_intersecting_faces": {"count": len(crossings), "centres_mm": np.round(mesh.triangles_center[crossings], 1).tolist()},
    "thickness": {
        "fail_below_mm": fail_mm,
        "warn_below_mm": warn_mm,
        "rays_valid_pct": round(100 * (hit >= 0).mean(), 1),
        "pct_area_below_fail": round(100 * vertex_area[thickness < fail_mm].sum() / total, 2),
        "pct_area_below_warn": round(100 * vertex_area[thin].sum() / total, 2),
        "slender_below_mm": args.slender_mm,
        "pct_area_slender": round(100 * vertex_area[thickness < args.slender_mm].sum() / total, 1),
        "slender_regions": slender_regions[:15],
        "thinnest_mm": round(float(thickness[np.isfinite(thickness)].min()), 2),
        "regions": regions[:15],
    },
    "overhang": {
        "support_angle_deg": args.support_angle,
        "needs_support_mm2": round(float(mesh.area_faces[needs_support].sum()), 0),
        "needs_support_pct": round(100 * mesh.area_faces[needs_support].sum() / total, 1),
        "steeper_than_45_pct": round(100 * mesh.area_faces[overhang_45].sum() / total, 1),
    },
    "islands": {"count": len(islands), "list": sorted(islands, key=lambda i: i["z_mm"])},
}
(out_dir / f"{name}-check.json").write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k not in ("thickness", "islands", "self_intersecting_faces")} | {"islands": report["islands"]["count"], "self_intersecting_faces": report["self_intersecting_faces"]["count"], "thickness": {k: v for k, v in report["thickness"].items() if not k.endswith("regions")}}, indent=2))
for r in regions[:10]:
    print("thin:", r)
for r in slender_regions[:10]:
    print("slender:", r)

# Render a decimated copy, coloring each face from the nearest original vertex
view = mesh.simplify_quadric_decimation(face_count=min(len(mesh.faces), 200_000))
_, nearest = cKDTree(mesh.vertices).query(view.triangles_center)
_, nearest_face = cKDTree(mesh.triangles_center).query(view.triangles_center)
t = thickness[nearest]
colors = np.tile([0.78, 0.78, 0.78], (len(view.faces), 1))
colors[needs_support[nearest_face]] = [0.35, 0.55, 0.95]
colors[t < args.slender_mm] = [0.95, 0.85, 0.2]
colors[t < warn_mm] = [1.0, 0.55, 0.1]
colors[t < fail_mm] = [0.85, 0.1, 0.1]
light = np.array([0.3, -0.6, 0.75])
shade = np.clip(view.face_normals @ (light / np.linalg.norm(light)), 0, 1) * 0.55 + 0.45
fc = colors * shade[:, None]
fig = plt.figure(figsize=(16, 16), dpi=110)
for i, (title, el, az) in enumerate([("front", 10, -90), ("back", 10, 90), ("left", 10, 180), ("from below", -35, -60)]):
    ax = fig.add_subplot(2, 2, i + 1, projection="3d")
    ax.set_box_aspect((1, 1, 1), zoom=1.35)
    ax.add_collection3d(Poly3DCollection(view.triangles, facecolors=fc, edgecolor="none"))
    if islands and title == "from below":
        isl = np.array([i_["xy_mm"] + [i_["z_mm"]] for i_ in islands])
        ax.scatter(isl[:, 0], isl[:, 1], isl[:, 2], c="k", s=25, depthshade=False)
    mid, rad = mesh.extents / 2, mesh.extents.max() / 2
    ax.set_xlim(mid[0] - rad, mid[0] + rad)
    ax.set_ylim(mid[1] - rad, mid[1] + rad)
    ax.set_zlim(mid[2] - rad, mid[2] + rad)
    ax.view_init(el, az)
    ax.set_axis_off()
    ax.set_title(title)
fig.legend(handles=[
    Patch(color=(0.85, 0.1, 0.1), label=f"thinner than {fail_mm:.1f} mm (likely to fail)"),
    Patch(color=(1.0, 0.55, 0.1), label=f"{fail_mm:.1f}-{warn_mm:.1f} mm (may not print cleanly)"),
    Patch(color=(0.95, 0.85, 0.2), label=f"{warn_mm:.1f}-{args.slender_mm:.1f} mm (slender, can snap)"),
    Patch(color=(0.35, 0.55, 0.95), label=f"needs support (<{args.support_angle:.0f} deg from horizontal)"),
    Patch(color="k", label="island start (black dots, below view)"),
], loc="lower center", ncol=3, fontsize=12)
fig.suptitle(f"{name}: {mesh.extents[0]:.0f} x {mesh.extents[1]:.0f} x {mesh.extents[2]:.0f} mm, {args.nozzle_mm} mm nozzle")
plt.savefig(out_dir / f"{name}-check.png")
print("wrote", out_dir / f"{name}-check.png")
