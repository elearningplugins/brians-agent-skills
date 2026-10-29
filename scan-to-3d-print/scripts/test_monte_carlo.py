"""Tests for the pure parts of monte_carlo.py: time parsing, cusp height and sampling."""
import numpy as np
import pytest
import trimesh
from hypothesis import given, settings
from hypothesis import strategies as st

from monte_carlo import SPACE, cusp_heights, parse_duration, sample_settings


@pytest.mark.parametrize("text, seconds", [("3h 50m 27s", 13827), ("50m 2s", 3002), ("1d 2h 0m 0s", 93600), ("45s", 45)])
def test_parse_duration(text, seconds):
    assert parse_duration(text) == seconds


def test_vertical_walls_and_flat_tops_have_no_cusps():
    box = trimesh.creation.box(extents=[10, 10, 10])
    box.apply_translation([0, 0, 5])
    c = cusp_heights(box, np.arange(0.2, 10.01, 0.2))
    np.testing.assert_allclose(c, 0, atol=1e-9)


@settings(max_examples=25, deadline=None)
@given(st.floats(10, 80), st.sampled_from([0.08, 0.12, 0.2, 0.28]))
def test_slope_cusp_is_layer_height_times_cosine(deg, h):
    # A plate tilted by deg from horizontal: its faces' normals sit deg from vertical, so each step stands h * cos(deg) proud of the slope
    plate = trimesh.creation.box(extents=[20, 20, 0.01])
    plate.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), [1, 0, 0]))
    plate.apply_translation([0, 0, 15])
    big = plate.area_faces > 1
    c = cusp_heights(plate, np.arange(h, 30, h))
    np.testing.assert_allclose(c[big], h * np.cos(np.radians(deg)), rtol=1e-6)


def test_sampled_settings_come_from_the_space():
    rng = np.random.default_rng(0)
    for _ in range(50):
        s = sample_settings(rng)
        assert set(s) == set(SPACE)
        assert all(s[k] in SPACE[k] for k in s)
