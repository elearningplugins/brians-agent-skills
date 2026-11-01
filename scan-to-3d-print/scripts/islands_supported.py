"""Checks every island check_print.py found against the G-code: an island is safe only if model extrusion lies under it in the layer below, or support within the support gap below."""
import json
import sys

import numpy as np
import trimesh
from scipy.spatial import cKDTree

from gcode_paths import config_value, plate_transform, read_paths


def layer_tops(paths):
    """Top Z of each printed layer, indexed by layer number, from the extrusion the G-code records."""
    pts = np.concatenate([v for v in paths.values() if len(v)])
    tops = np.zeros(int(pts[:, 2].max()) + 1)
    np.maximum.at(tops, pts[:, 2].astype(int), pts[:, 3])
    return np.maximum.accumulate(tops)


def check(paths, islands, to_plate, gap_layers, check_layer_mm=0.2):
    """Counts islands with support or model beneath them; islands are in STL coordinates at the centre of check_print.py's layers."""
    tops = layer_tops(paths)
    # Layers are spaced 100 apart in the tree so a search radius of a few millimetres stays inside one layer
    below = {k: cKDTree(v[:, :3] * [1, 1, 100]) for k, v in paths.items() if len(v)}
    report = {"islands": len(islands), "on_support": 0, "on_model": 0, "unsupported": []}
    for isl in islands:
        # The island starts at the bottom of check_print.py's layer, so it first prints in the first G-code layer whose top is above that
        layer = int(np.searchsorted(tops, isl["z_mm"] - check_layer_mm / 2 + 1e-6))
        xy = trimesh.transform_points([[*isl["xy_mm"], isl["z_mm"]]], to_plate)[0, :2]
        radius = np.sqrt(isl["area_mm2"] / np.pi) + 1.0
        # Model must be directly below; support stops a gap short of the model so it peels off
        reach = {"model": [1]}
        found = {k: any(t.query_ball_point([xy[0], xy[1], (layer - d) * 100], radius) for d in reach.get(k, range(1, gap_layers + 2))) for k, t in below.items()}
        if found.get("support") or found.get("interface"):
            report["on_support"] += 1
        elif found.get("model"):
            report["on_model"] += 1
        else:
            report["unsupported"].append(isl)
    return report


def gap_layers_of(gcode):
    """How many layers the support stops short of the model."""
    return round(float(config_value(gcode, "support_top_z_distance")) / float(config_value(gcode, "layer_height")))


if __name__ == "__main__":
    gcode, check_json, three_mf, stl = sys.argv[1:5]
    islands = json.loads(open(check_json).read())["islands"]["list"]
    # Arranging can rotate the model on the plate, so islands found in STL coordinates are placed with the transform the project file records
    to_plate = plate_transform(three_mf, trimesh.load(stl).bounds)
    print(json.dumps(check(read_paths(gcode, 0.3), islands, to_plate, gap_layers_of(gcode))))
