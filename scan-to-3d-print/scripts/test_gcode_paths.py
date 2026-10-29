"""Tests for gcode_paths.read_paths: straight moves, arcs and what is skipped."""
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from gcode_paths import read_paths


def write(tmp_path, body):
    path = tmp_path / "t.gcode"
    path.write_text("; CHANGE_LAYER\n; Z_HEIGHT: 0.2\n; FEATURE: Outer wall\n" + body)
    return path


def test_straight_move_is_sampled_along_its_length(tmp_path):
    pts = read_paths(write(tmp_path, "G1 X0 Y0\nG1 X10 Y0 E1\n"), 0.5)["model"]
    assert len(pts) == 21
    np.testing.assert_allclose(pts[:, 1], 0)
    assert pts[:, 0].min() == 0 and pts[:, 0].max() == 10


@pytest.mark.parametrize("cmd, mid_y", [("G3", -5.0), ("G2", 5.0)])
def test_half_circle_arc_follows_the_circle(tmp_path, cmd, mid_y):
    # From (0,0) to (10,0) about centre (5,0): G3 turns counter-clockwise from the left point, so through -Y, and G2 through +Y
    pts = read_paths(write(tmp_path, f"G1 X0 Y0\n{cmd} X10 Y0 I5 J0 E1\n"), 0.1)["model"]
    np.testing.assert_allclose(np.hypot(pts[:, 0] - 5, pts[:, 1]), 5, atol=1e-9)
    assert np.sign(pts[len(pts) // 2, 1]) == np.sign(mid_y)
    assert abs(pts[:, 1]).max() == pytest.approx(5, abs=0.01)


@settings(max_examples=40, deadline=None)
@given(st.floats(0.5, 20), st.floats(-np.pi, np.pi), st.floats(0.2, 6.0), st.booleans())
def test_arc_points_lie_on_the_circle_and_end_at_the_target(tmp_path_factory, r, a0, sweep, ccw):
    a1 = a0 + sweep if ccw else a0 - sweep
    sx, sy, ex, ey = r * np.cos(a0), r * np.sin(a0), r * np.cos(a1), r * np.sin(a1)
    cmd = "G3" if ccw else "G2"
    path = write(tmp_path_factory.mktemp("arc"), f"G1 X{sx:.6f} Y{sy:.6f}\n{cmd} X{ex:.6f} Y{ey:.6f} I{-sx:.6f} J{-sy:.6f} E1\n")
    pts = read_paths(path, 0.2)["model"]
    np.testing.assert_allclose(np.hypot(pts[:, 0], pts[:, 1]), r, atol=1e-4)
    np.testing.assert_allclose(pts[-1, :2], [ex, ey], atol=1e-5)
    steps = np.hypot(*np.diff(pts[:, :2], axis=0).T)
    assert steps.max() <= 0.2 + 1e-6


def test_full_circle_arc_when_start_equals_end(tmp_path):
    pts = read_paths(write(tmp_path, "G1 X0 Y0\nG3 X0 Y0 I5 J0 E1\n"), 0.1)["model"]
    assert pts[:, 0].max() == pytest.approx(10, abs=0.01)


def test_unretract_and_travel_are_not_extrusion(tmp_path):
    pts = read_paths(write(tmp_path, "G1 X0 Y0\nG1 E0.8\nG1 X5 Y5\nG2 X10 Y5 I2.5 J0\n"), 0.5)["model"]
    assert len(pts) == 0


def fake_3mf(path, item, component, extruder_offset):
    import json
    import zipfile
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("3D/3dmodel.model", f'<model><component objectid="1" transform="{component}"/><item objectid="2" transform="{item}"/></model>')
        if extruder_offset is not None:
            z.writestr("Metadata/project_settings.config", json.dumps({"extruder_offset": [extruder_offset]}))
    return path


@pytest.mark.parametrize("offset, shift", [("0x2", [0, -2]), ("1.5x-3", [-1.5, 3]), (None, [0, 0])])
def test_plate_transform_lands_in_gcode_coordinates(tmp_path, offset, shift):
    # Item turns 90 degrees about Z and moves to (100, 50); the printer's G-code sits extruder_offset away from the plate
    item = "0 1 0 -1 0 0 0 0 1 100 50 0"
    component = "1 0 0 0 1 0 0 0 1 0 0 5"
    from gcode_paths import plate_transform
    T = plate_transform(fake_3mf(tmp_path / "p.3mf", item, component, offset), [[0, 0, 0], [20, 10, 10]])
    got = T @ [20, 5, 5, 1]
    np.testing.assert_allclose(got[:3], [100 + shift[0], 50 + 10 + shift[1], 5], atol=1e-9)
