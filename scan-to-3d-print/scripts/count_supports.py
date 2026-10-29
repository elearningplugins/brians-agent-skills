"""Estimates separate support structures in a Bambu G-code file: which stand on the plate, which rest on the model, and how many interface pads the model sits on."""
import json
import sys

import numpy as np
from scipy import ndimage

from gcode_paths import read_paths

CELL = 0.5
paths = read_paths(sys.argv[1], CELL)
lo = np.concatenate(list(paths.values()))[:, :2].min(0) - 2
top = np.concatenate(list(paths.values())).max(0)
shape = (int((top[0] - lo[0]) / CELL) + 5, int((top[1] - lo[1]) / CELL) + 5, int(top[2]) + 2)


def grid(p):
    """Occupancy of (x cell, y cell, layer) for a set of path points."""
    g = np.zeros(shape, bool)
    g[((p[:, 0] - lo[0]) / CELL).astype(int), ((p[:, 1] - lo[1]) / CELL).astype(int), p[:, 2].astype(int)] = True
    return g


interface = grid(paths["interface"])
sup = grid(paths["support"]) | interface
mod = grid(paths["model"])
# Close small gaps between neighbouring tree branches in the same layer so one tree counts once
lab, n = ndimage.label(ndimage.binary_dilation(sup, structure=np.ones((5, 5, 3), bool)))
on_plate = set(np.unique(lab[:, :, 0][lab[:, :, 0] > 0]))
# A support structure rests on the model if model extrusion lies directly beneath any of its bottom cells
below_model = ndimage.binary_dilation(mod, structure=np.ones((3, 3, 1), bool))
rests_on_model = set()
for z in range(1, shape[2]):
    touching = lab[:, :, z][(lab[:, :, z] > 0) & below_model[:, :, z - 1] & ~(lab[:, :, z - 1] > 0)]
    rests_on_model.update(np.unique(touching).tolist())
sizes = ndimage.sum(sup, lab, range(1, n + 1))
significant = [i + 1 for i, s in enumerate(sizes) if s * CELL * CELL * 0.2 >= 1.0]
# Contact pads: interface regions with model extrusion in the layer directly above, so a region that holds nothing up does not count
pad_lab, n_pads = ndimage.label(ndimage.binary_dilation(interface, structure=np.ones((3, 3, 3), bool)))
model_above = np.zeros(shape, bool)
model_above[:, :, :-1] = ndimage.binary_dilation(mod, structure=np.ones((3, 3, 1), bool))[:, :, 1:]
pads = np.unique(pad_lab[(pad_lab > 0) & interface & model_above])
top_layers = {i: int(np.where((lab == i).any(axis=(0, 1)))[0].max()) for i in significant}
report = {
    "support_structures": len(significant),
    "standing_on_plate": len([i for i in significant if i in on_plate]),
    "resting_on_model": len([i for i in significant if i in rests_on_model and i not in on_plate]),
    "both_plate_and_model": len([i for i in significant if i in rests_on_model and i in on_plate]),
    "interface_contact_pads": int(len(pads)),
    "interface_regions_without_model_above": int(n_pads - len(pads)),
    "tallest_support_mm": round(max((t + 1) * 0.2 for t in top_layers.values()), 1) if top_layers else 0,
    "note": "estimates from G-code paths on a 0.5 mm grid, not Bambu figures; pad counts vary by about 10% between identical re-slices",
}
print(json.dumps(report))
