"""Takes the outward thickening back off rods such as claws in the voxel solid, keeping their filled core, so they print at their scanned size instead of half a minimum wall fatter all round."""
import numpy as np
from scipy import ndimage


def trim_rod_shell(solid, surface, rod_zone, *, keep_voxels, close_iter):
    """The solid with every voxel in rod_zone dropped unless it lies within keep_voxels of the scan surface or inside it; close_iter seals scan holes first, as the build does, so a holed rod is not left as a hollow sleeve."""
    if not rod_zone.any():
        return solid
    # Work in the zone's bounding box with room for the closing and a cap of untrimmed solid beyond it
    m = close_iter + keep_voxels + 2
    lo = np.maximum(np.argwhere(rod_zone).min(0) - m, 0)
    hi = np.minimum(np.argwhere(rod_zone).max(0) + m + 1, solid.shape)
    box = tuple(slice(a, b) for a, b in zip(lo, hi))
    zone = rod_zone[box]
    thin = ndimage.distance_transform_edt(~surface[box]) <= keep_voxels
    thin = ndimage.binary_closing(np.pad(thin, close_iter), iterations=close_iter)[(slice(close_iter, -close_iter),) * 3]
    # Where a rod runs out of the zone into the leg, the untrimmed solid there caps its open end so the fill can find the core
    core = ndimage.binary_fill_holes(thin | (solid[box] & ~zone))
    out = solid.copy()
    out[box] &= ~zone | core
    return out
