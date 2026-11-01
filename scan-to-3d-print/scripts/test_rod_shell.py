"""Tests for rod_shell.trim_rod_shell on voxel tubes whose scanned radius is known exactly."""
import numpy as np
from scipy import ndimage

from rod_shell import trim_rod_shell

PITCH, SHELL_MM, RADIUS = 0.1, 0.6, 0.8
SHAPE = (140, 40, 40)
AXIS = np.array([0.0, 2.0, 2.0])


def tube_samples(gap_at=None):
    """A capped tube of RADIUS along X, sampled densely; gap_at leaves a hole about two voxels wide in its side there."""
    a = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    A, X = np.meshgrid(a, np.arange(2.0, 12.0, 0.03))
    side = np.c_[X.ravel(), AXIS[1] + RADIUS * np.cos(A.ravel()), AXIS[2] + RADIUS * np.sin(A.ravel())]
    if gap_at is not None:
        side = side[np.linalg.norm(side - gap_at, axis=1) > 0.12]
    r, b = np.meshgrid(np.linspace(0, RADIUS, 30), a)
    caps = [np.c_[np.full(r.size, x), AXIS[1] + r.ravel() * np.cos(b.ravel()), AXIS[2] + r.ravel() * np.sin(b.ravel())] for x in (2.0, 12.0)]
    return np.r_[side, caps[0], caps[1]]


def voxelize(samples):
    surface = np.zeros(SHAPE, bool)
    i = np.floor(samples / PITCH).astype(int)
    surface[i[:, 0], i[:, 1], i[:, 2]] = True
    solid = ndimage.binary_fill_holes(ndimage.distance_transform_edt(~surface) <= SHELL_MM / PITCH)
    return surface, solid


def radius_at(solid, x_mm):
    yz = np.argwhere(solid[int(x_mm / PITCH)])
    return (np.linalg.norm((yz + 0.5) * PITCH - AXIS[1:], axis=1)).max()


def test_rod_loses_its_thickening_but_keeps_its_core():
    # The build thickens every scanned surface by half the minimum wall; on a claw that turns a 1.6 mm rod into 2.8 mm, and the trim should bring it back to about the scanned radius plus one voxel
    surface, solid = voxelize(tube_samples())
    assert radius_at(solid, 7.0) > RADIUS + SHELL_MM - PITCH
    trimmed = trim_rod_shell(solid, surface, np.ones(SHAPE, bool), keep_voxels=1, close_iter=2)
    assert abs(radius_at(trimmed, 7.0) - (RADIUS + PITCH)) < 1.5 * PITCH
    assert trimmed[70, 20, 20]
    assert ndimage.label(trimmed)[1] == 1


def test_only_the_rod_zone_is_trimmed():
    surface, solid = voxelize(tube_samples())
    zone = np.zeros(SHAPE, bool)
    zone[:70] = True
    trimmed = trim_rod_shell(solid, surface, zone, keep_voxels=1, close_iter=2)
    assert radius_at(trimmed, 4.0) < RADIUS + 2.5 * PITCH
    assert radius_at(trimmed, 10.0) == radius_at(solid, 10.0)


def test_a_small_scan_hole_does_not_hollow_the_rod():
    # A claw's scan with a hole in its side would fill as a hollow sleeve without sealing, which prints as two thin walls
    surface, solid = voxelize(tube_samples(gap_at=np.array([7.0, AXIS[1] + RADIUS, AXIS[2]])))
    assert solid[70, 20, 20]
    trimmed = trim_rod_shell(solid, surface, np.ones(SHAPE, bool), keep_voxels=1, close_iter=2)
    assert trimmed[60:80, 20, 20].all()
