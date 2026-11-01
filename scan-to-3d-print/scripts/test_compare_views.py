"""Tests for compare_views.render on shapes whose silhouette and distances are known exactly."""
import numpy as np
import pytest
import trimesh

from compare_views import camera, distance_to, render


def sphere(radius=10.0, centre=(0.0, 0.0, 0.0)):
    m = trimesh.creation.icosphere(subdivisions=4, radius=radius)
    m.apply_translation(centre)
    return m


@pytest.mark.parametrize("elev,azim", [(0, -90), (30, 45), (-60, 180)])
def test_sphere_covers_a_disc_of_its_radius_from_any_side(elev, azim):
    px, rad = 200, 20.0
    _, mask = render(sphere(), np.zeros(3), rad, elev, azim, px, two_sided=False)
    # The disc covers pi r^2 of the (2 rad)^2 square, within the faceting of the sphere
    np.testing.assert_allclose(mask.mean(), np.pi * 10.0**2 / (2 * rad) ** 2, rtol=0.03)


def test_camera_axes_are_orthonormal_and_look_from_the_named_side():
    right, up, view = camera(0, -90)
    np.testing.assert_allclose(np.c_[right, up, view].T @ np.c_[right, up, view], np.eye(3), atol=1e-12)
    # Azimuth -90 looks from -Y, the front of a model facing -Y, with Z up
    np.testing.assert_allclose(view, [0, -1, 0], atol=1e-12)
    np.testing.assert_allclose(up, [0, 0, 1], atol=1e-12)


def test_nearer_surface_hides_the_one_behind():
    near, far = sphere(5.0, (0, -20, 0)), sphere(5.0, (0, 20, 0))
    both = trimesh.util.concatenate([near, far])
    values = np.r_[np.zeros(len(near.vertices)), np.ones(len(far.vertices))]
    img, mask = render(both, np.zeros(3), 10.0, 0, -90, 100, two_sided=False, values=values, vmax=1.0)
    # From the front only the near sphere shows, so every covered pixel carries its blue, not the far sphere's red
    covered = img[mask].astype(float)
    assert (covered[:, 2] > covered[:, 0]).all()


def test_distance_to_a_surface_offset_by_a_known_gap():
    inner, outer = sphere(10.0), sphere(11.0)
    d = distance_to(inner.vertices, outer, samples=400_000)
    np.testing.assert_allclose(d, 1.0, atol=0.05)
