"""Checks the sliced G-code against the model it came from: every bit of model surface should have model extrusion within a line width of it, in its own layer or a neighbour."""
import argparse
import json

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from gcode_paths import config_value, plate_transform, read_paths
from islands_supported import layer_tops


def uncovered(pts, model, tops, width):
    """Mask of surface points, in G-code coordinates, with no model extrusion within width + 0.25 mm in their layer or either neighbour; points in the first layer are not judged."""
    layer = np.clip(np.searchsorted(tops, pts[:, 2]), 0, len(tops) - 1)
    # Layers sit 1000 apart in the tree so a search radius of a few millimetres stays inside one layer
    tree = cKDTree(np.c_[model[:, :2], model[:, 2] * 1000])
    d = np.min([tree.query(np.c_[pts[:, :2], (layer + k) * 1000], distance_upper_bound=5)[0] for k in (-1, 0, 1)], axis=0)
    return (d > width + 0.25) & (pts[:, 2] > tops[0])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("gcode")
    ap.add_argument("three_mf")
    ap.add_argument("stl")
    ap.add_argument("--samples", type=int, default=200_000)
    ap.add_argument("--max-uncovered-pct", type=float, default=1.0, help="a placement error or a misread move shows as much more than this; dropped thin features as a few hundredths of a percent")
    args = ap.parse_args()
    mesh = trimesh.load(args.stl)
    pts, _ = trimesh.sample.sample_surface(mesh, args.samples, seed=0)
    pts = trimesh.transform_points(pts, plate_transform(args.three_mf, mesh.bounds))
    paths = read_paths(args.gcode, 0.3)
    width = float(config_value(args.gcode, "outer_wall_line_width") or 0.42)
    pct = round(100 * float(uncovered(pts, paths["model"], layer_tops(paths), width).mean()), 3)
    print(json.dumps({"uncovered_surface_pct": pct, "limit_pct": args.max_uncovered_pct}))
    if pct > args.max_uncovered_pct:
        raise SystemExit(f"{pct}% of the model surface has no extrusion near it: the G-code and model disagree on placement or shape")
