"""Tests for coverage.uncovered: surface points with no model extrusion near them in their layer or a neighbour."""
import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from coverage import uncovered


def ring_paths(radius, layers, h=0.2, step=0.3):
    """Model extrusion as one circular wall loop per layer, in read_paths' (x, y, layer, z) columns."""
    t = np.linspace(0, 2 * np.pi, int(2 * np.pi * radius / step), endpoint=False)
    rows = [np.c_[radius * np.cos(t), radius * np.sin(t), np.full(t.size, k), np.full(t.size, (k + 1) * h)] for k in range(layers)]
    return np.concatenate(rows)


def cylinder_surface(radius, height, n=4000, seed=0):
    rng = np.random.default_rng(seed)
    a, z = rng.uniform(0, 2 * np.pi, n), rng.uniform(0.25, height - 0.05, n)
    return np.c_[radius * np.cos(a), radius * np.sin(a), z]


def test_wall_centred_half_a_line_inside_covers_the_surface():
    model = ring_paths(10.0 - 0.21, 50)
    tops = np.arange(1, 51) * 0.2
    assert uncovered(cylinder_surface(10.0, 10.0), model, tops, width=0.42).mean() == 0


@settings(max_examples=20, deadline=None)
@given(st.floats(1.5, 5.0), st.floats(0, 2 * np.pi))
def test_surface_shifted_off_the_extrusion_is_found(shift, angle):
    # A placement error of a millimetre or more, like the P1S extruder offset, must show up as surface with nothing printed at it
    model = ring_paths(10.0 - 0.21, 50)
    tops = np.arange(1, 51) * 0.2
    pts = cylinder_surface(10.0, 10.0) + [shift * np.cos(angle), shift * np.sin(angle), 0]
    assert uncovered(pts, model, tops, width=0.42).mean() > 0.2


def test_surface_below_the_first_layer_top_is_not_judged():
    model = ring_paths(9.79, 5)
    tops = np.arange(1, 6) * 0.2
    pts = np.array([[30.0, 0, 0.1]])
    assert not uncovered(pts, model, tops, width=0.42).any()
