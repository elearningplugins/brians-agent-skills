"""Example and Hypothesis property tests for printcheck.py, using shapes whose thickness, overhang and islands are known exactly."""
import numpy as np
import pytest
import trimesh
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays
from shapely.geometry import Polygon

from printcheck import find_islands, guard_relief, needs_support, roughness, self_intersections, wall_thickness

SLAB_WIDTH = 20.0
mesh_settings = settings(max_examples=25, deadline=None)


def slab(thickness, width=SLAB_WIDTH):
    """A square plate centred on the origin, subdivided so interior vertices have exactly vertical normals."""
    box = trimesh.creation.box(extents=[width, width, thickness])
    return box.subdivide_to_size(max(thickness, 1.0))


def interior_top(mesh, width=SLAB_WIDTH, margin=4.0):
    """Indices of vertices on the top face, away from the edges where vertex normals tilt."""
    v = mesh.vertices
    idx = np.where((v[:, 2] > v[:, 2].max() - 1e-6) & (np.abs(v[:, 0]) < width / 2 - margin) & (np.abs(v[:, 1]) < width / 2 - margin))[0]
    assert len(idx) > 0
    return idx


def rotated(mesh, ax, ay, az):
    """Copy of the mesh rotated about the X, Y and Z axes in degrees."""
    m = mesh.copy()
    m.apply_transform(trimesh.transformations.euler_matrix(*np.radians([ax, ay, az])))
    return m


def tilted_slab(degrees, lift_mm=10.0):
    """A 1 mm slab tilted about X and lifted so its lowest point is lift_mm above the bed."""
    m = rotated(slab(1.0), degrees, 0, 0)
    m.apply_translation([0, 0, lift_mm - m.bounds[0][2]])
    return m


# Wall thickness


def test_slab_thickness_is_exact():
    m = slab(1.6)
    t, _ = wall_thickness(m)
    np.testing.assert_allclose(t[interior_top(m)], 1.6, atol=0.01)


def test_inward_normals_measure_nothing():
    # Regression for the stale-normals bug: inverted normals make every inward ray miss, which build_v2.py turns into a hard stop
    m = slab(1.6)
    m.invert()
    t, hit = wall_thickness(m)
    assert np.isinf(t).all()
    assert (hit == -1).all()


def test_single_dented_vertex_does_not_skew_the_reading():
    # The neighbour median exists so one noisy vertex cannot fake a thin wall
    m = slab(2.0)
    v = interior_top(m)[0]
    verts = m.vertices.copy()
    verts[v, 2] -= 1.0
    m = trimesh.Trimesh(verts, m.faces, process=False)
    t, _ = wall_thickness(m)
    # Neighbours see the wall slightly obliquely (about 2.07 mm); a mean that let the dent's own 1.0 mm ray in would read about 1.90 mm
    assert 2.0 <= t[v] <= 2.1


def test_rays_entering_another_part_from_outside_are_not_walls():
    # A backwards-facing part casts its ray out across the gap into the next part; that must read as unmeasured, not as a wall the width of the gap
    lower = slab(1.0)
    lower.invert()
    upper = slab(1.0)
    upper.apply_translation([0, 0, 3.0])
    m = trimesh.util.concatenate([lower, upper])
    idx = interior_top(lower)
    t, hit = wall_thickness(m)
    assert np.isinf(t[idx]).all()
    assert (hit[idx] == -1).all()


@mesh_settings
@given(st.floats(0.6, 4.0))
def test_slab_thickness_matches_any_thickness(t):
    m = slab(t)
    measured, _ = wall_thickness(m)
    np.testing.assert_allclose(measured[interior_top(m)], t, atol=0.01)


@mesh_settings
@given(st.floats(0.6, 3.0), st.floats(-180, 180), st.floats(-180, 180), st.floats(-180, 180))
def test_thickness_does_not_depend_on_orientation(t, ax, ay, az):
    m = slab(t)
    idx = interior_top(m)
    measured, _ = wall_thickness(rotated(m, ax, ay, az))
    np.testing.assert_allclose(measured[idx], t, atol=0.01)


@mesh_settings
@given(st.floats(0.6, 2.0), st.floats(0.5, 4.0))
def test_thickness_scales_with_the_model(t, k):
    m = slab(t)
    idx = interior_top(m)
    base, _ = wall_thickness(m)
    big = m.copy()
    big.apply_scale(k)
    scaled, _ = wall_thickness(big)
    np.testing.assert_allclose(scaled[idx], base[idx] * k, atol=0.01 * k)


def shell(outer_r, inner_r):
    """A hollow ball: the outer sphere facing out and the inner sphere facing into the cavity."""
    inner = trimesh.creation.icosphere(subdivisions=4, radius=inner_r)
    inner.invert()
    return trimesh.util.concatenate([trimesh.creation.icosphere(subdivisions=4, radius=outer_r), inner])


@pytest.mark.parametrize("outer, inner", [(10.0, 8.8), (5.0, 3.4), (20.0, 19.0)])
def test_curved_shell_reads_its_thickness_on_both_faces(outer, inner):
    t, _ = wall_thickness(shell(outer, inner))
    np.testing.assert_allclose(t, outer - inner, atol=0.03)


def test_concave_crease_does_not_read_thin():
    # Inside corner of an L: vertices near the crease see solid material in every inward direction, never less than the arm thickness
    m = boxes(([0, 0, 1.0], [20, 20, 2.0]), ([-9, 0, 6.0], [2.0, 20, 12.0])).subdivide_to_size(0.5)
    v = m.vertices
    crease = (np.abs(v[:, 0] + 8.0) < 1.0) & (np.abs(v[:, 2] - 2.0) < 1.0) & (np.abs(v[:, 1]) < 6.0)
    t, _ = wall_thickness(m)
    assert crease.sum() > 0
    assert t[crease].min() >= 2.0 - 0.01


@mesh_settings
@given(st.floats(3.0, 20.0))
def test_tapered_wall_reads_close_to_its_true_thickness(degrees):
    # A wedge's faces are not parallel, so a ray along one face's normal crosses the wedge obliquely; the reading must stay within 10% of the perpendicular thickness
    length, root = 30.0, 4.0
    tip = root - length * np.tan(np.radians(degrees))
    assume(tip > 0.3)
    section = [[0, 0], [length, 0], [length, tip], [0, root]]
    m = trimesh.creation.extrude_polygon(Polygon(section), 20.0).subdivide_to_size(0.5)
    v = m.vertices
    bottom = (np.abs(v[:, 1]) < 1e-6) & (v[:, 0] > 3) & (v[:, 0] < length - 3) & (v[:, 2] > 4) & (v[:, 2] < 16)
    t, _ = wall_thickness(m)
    # Perpendicular distance from a bottom-face point to the sloping top face
    slope = np.radians(degrees)
    true = (root - v[bottom, 0] * np.tan(slope)) * np.cos(slope)
    np.testing.assert_allclose(t[bottom], true, rtol=0.1)


# Self-intersection


def test_clean_box_has_no_self_intersections():
    assert len(self_intersections(trimesh.creation.box(extents=[5, 5, 5]).subdivide_to_size(1.0))) == 0


def test_overlapping_parts_intersect():
    a = trimesh.creation.box(extents=[5, 5, 5])
    b = trimesh.creation.box(extents=[5, 5, 5], transform=trimesh.transformations.translation_matrix([2, 1, 1]))
    assert len(self_intersections(trimesh.util.concatenate([a, b]))) > 0


def pushed_through(depth_mm=2.0):
    """A 1 mm slab with one interior top vertex driven depth_mm down, through the bottom face."""
    m = slab(1.0)
    verts = m.vertices.copy()
    verts[interior_top(m)[0], 2] -= depth_mm
    return trimesh.Trimesh(verts, m.faces, process=False)


def test_vertex_pushed_through_the_far_wall_is_found():
    # The fold a careless pull-back makes: one vertex driven through the opposite side of a thin slab
    assert len(self_intersections(pushed_through())) > 0


# Regression: re-casting 1e-6 mm past a skipped face is below float32 resolution away from the origin, so edge rays re-hit their own face until they gave up, and about half the edges of a printed model went unchecked
@pytest.mark.parametrize("offset", [[0, 0, 0], [120, 80, 60], [250, 250, 250]])
def test_crossings_are_found_anywhere_on_the_build_plate(offset):
    near = pushed_through()
    far = near.copy()
    far.apply_translation(offset)
    np.testing.assert_array_equal(self_intersections(far), self_intersections(near))


@mesh_settings
@given(st.floats(0.6, 3.0), st.floats(0, 250), st.floats(0, 250), st.floats(0, 250))
def test_slab_thickness_does_not_depend_on_position(t, x, y, z):
    m = slab(t)
    m.apply_translation([x, y, z])
    th, _ = wall_thickness(m)
    np.testing.assert_allclose(th[interior_top(slab(t))], t, atol=0.01)


def brute_force_crossings(mesh):
    """Every face some non-adjacent edge passes through, by testing every edge against every face: where the edge meets the face's plane, and whether that point is inside the face."""
    e = mesh.edges_unique
    a, b = mesh.vertices[e[:, 0]][:, None], mesh.vertices[e[:, 1]][:, None]
    p0, p1, p2 = (mesh.triangles[:, i][None] for i in range(3))
    n = np.cross(p1 - p0, p2 - p0)
    da, db = ((a - p0) * n).sum(-1), ((b - p0) * n).sum(-1)
    straddles = da * db < 0
    x = a + (b - a) * (da / np.where(straddles, da - db, 1.0))[..., None]
    inside = np.ones(da.shape, bool)
    for q0, q1 in ((p0, p1), (p1, p2), (p2, p0)):
        inside &= (np.cross(q1 - q0, x - q0) * n).sum(-1) > 0
    shared = (mesh.faces[None] == e[:, 0][:, None, None]).any(-1) | (mesh.faces[None] == e[:, 1][:, None, None]).any(-1)
    return np.unique(np.nonzero(straddles & inside & ~shared)[1])


@mesh_settings
@given(st.integers(0, 10**6), st.floats(0.3, 3.0), st.floats(-1, 1), st.floats(-1, 1), st.floats(0, 250))
def test_every_face_an_edge_crosses_is_found(seed, depth, dx, dy, at):
    # Regression: casting rays along the edges grazed each edge's own faces, so about half the edges of a printed model went unchecked; compare with testing every edge against every face
    m = trimesh.creation.box(extents=[8, 8, 1.0]).subdivide_to_size(1.5)
    verts = m.vertices.copy()
    v = np.random.default_rng(seed).integers(len(verts))
    verts[v] += np.array([dx, dy, -1.0 if verts[v, 2] > 0 else 1.0]) * depth
    m = trimesh.Trimesh(verts + at, m.faces, process=False)
    expected = brute_force_crossings(m)
    found = self_intersections(m)
    assert set(expected) <= set(found)


@mesh_settings
@given(st.floats(0.6, 3.0), st.floats(-180, 180), st.floats(-180, 180), st.floats(0.2, 5.0))
def test_slab_never_self_intersects_in_any_pose(t, ax, ay, k):
    m = rotated(slab(t), ax, ay, 0)
    m.apply_scale(k)
    assert len(self_intersections(m)) == 0


# Support


def test_flat_ceiling_needs_support():
    m = tilted_slab(0)
    assert m.area_faces[needs_support(m, 30, 0.2)].sum() == pytest.approx(SLAB_WIDTH**2)


def test_bed_contact_needs_no_support():
    m = tilted_slab(0, lift_mm=0.0)
    assert m.area_faces[needs_support(m, 30, 0.2)].sum() == 0.0


@pytest.mark.parametrize("degrees, expected", [(29.5, True), (30.5, False)])
def test_support_threshold_boundary(degrees, expected):
    m = tilted_slab(degrees)
    assert bool(needs_support(m, 30, 0.2).any()) is expected


@mesh_settings
@given(st.floats(0, 55))
def test_underside_needs_support_only_below_the_threshold(degrees):
    assume(abs(degrees - 30) > 0.5)
    m = tilted_slab(degrees)
    area = m.area_faces[needs_support(m, 30, 0.2)].sum()
    if degrees < 30:
        assert area == pytest.approx(SLAB_WIDTH**2)
    else:
        assert area == 0.0


# Islands


def boxes(*specs):
    """One watertight mesh, the union of boxes given as (centre, extents), like the single body build_v2.py writes."""
    return trimesh.boolean.union([trimesh.creation.box(extents=e, transform=trimesh.transformations.translation_matrix(c)) for c, e in specs], engine="manifold")


def test_supported_stack_has_no_islands():
    m = boxes(([0, 0, 2.5], [10, 10, 5]), ([0, 0, 7], [4, 4, 5]))
    assert find_islands(m, 0.2, 0.05) == []


def test_overhanging_arm_attached_below_has_no_islands():
    m = boxes(([0, 0, 5], [4, 4, 10]), ([4, 0, 9], [8, 4, 2]))
    assert find_islands(m, 0.2, 0.05) == []


def test_block_floating_straight_above_the_base_is_an_island():
    # Found by Hypothesis: empty layers in the gap were skipped, so the block was compared with the base top and passed as supported
    m = boxes(([0, 0, 2.5], [10, 10, 5]), ([0, 0, 7.5], [3, 3, 3]))
    found = find_islands(m, 0.2, 0.05)
    assert [round(f["area_mm2"], 1) for f in found] == [9.0]


@mesh_settings
@given(st.floats(0.5, 20.0), st.floats(-8, 8), st.floats(-8, 8))
def test_floating_block_is_exactly_one_island(gap, x, y):
    bottom = 5 + gap
    m = boxes(([0, 0, 2.5], [10, 10, 5]), ([x, y, bottom + 1.5], [3, 3, 3]))
    found = find_islands(m, 0.2, 0.05)
    assert len(found) == 1
    assert bottom <= found[0]["z_mm"] <= bottom + 0.2 + 1e-6
    assert found[0]["area_mm2"] == pytest.approx(9.0, rel=1e-3)


# Wall guard


def test_guard_examples():
    wall = np.array([3.0, 2.0, 1.0, 2.2, 2.2 - 1e-9])
    amount = np.full(5, -0.3)
    hit = np.full(5, -1)
    out, outward = guard_relief(amount, wall, hit, np.zeros((0, 3), int), 1.2, 0.5)
    # Thick wall keeps its relief; near the limit relief turns outward only; under the limit it gains half the shortfall; the limit itself is exclusive
    np.testing.assert_allclose(out, [-0.3, 0.0, 0.1, -0.3, 0.0])
    assert outward.tolist() == [False, True, True, False, True]


def test_guard_protects_the_far_side_its_ray_hits():
    wall = np.array([1.5, 9.0, 9.0, 9.0])
    amount = np.array([0.0, -0.4, -0.4, -0.4])
    hit = np.array([0, -1, -1, -1])
    faces = np.array([[1, 2, 3]])
    out, outward = guard_relief(amount, wall, hit, faces, 1.2, 0.5)
    assert outward.tolist() == [True, True, True, True]
    np.testing.assert_allclose(out, [0.0, 0.0, 0.0, 0.0])


@st.composite
def guard_inputs(draw):
    n = draw(st.integers(1, 40))
    n_faces = draw(st.integers(0, 20))
    wall = draw(arrays(float, n, elements=st.one_of(st.floats(0.05, 10.0), st.just(np.inf))))
    amount = draw(arrays(float, n, elements=st.floats(-1.0, 1.0)))
    faces = draw(arrays(int, (n_faces, 3), elements=st.integers(0, n - 1)))
    hit = draw(arrays(int, n, elements=st.integers(-1, n_faces - 1)))
    min_print = draw(st.floats(0.4, 2.0))
    relief = draw(st.floats(0.0, 1.0))
    return amount, wall, hit, faces, min_print, relief


@given(guard_inputs())
def test_guard_invariants(inputs):
    amount, wall, hit, faces, min_print, relief = inputs
    out, outward = guard_relief(amount.copy(), wall, hit, faces, min_print, relief)
    floor = (min_print - wall) / 2
    # Never pushes in further than asked, never leaves a side below its share of the minimum wall
    assert (out >= amount).all()
    assert (out >= floor - 1e-12).all()
    # Anything near the limit, and the far side of its ray, only moves outward
    near = wall < min_print + 2 * relief
    assert outward[near].all()
    assert outward[faces[hit[near & (hit >= 0)]].ravel()].all()
    assert (out[outward] >= 0).all()
    # Vertices the guard has no reason to touch keep their relief exactly
    untouched = ~outward & (amount >= floor)
    np.testing.assert_array_equal(out[untouched], amount[untouched])


@given(guard_inputs())
def test_guard_is_idempotent(inputs):
    amount, wall, hit, faces, min_print, relief = inputs
    once, _ = guard_relief(amount, wall, hit, faces, min_print, relief)
    twice, _ = guard_relief(once, wall, hit, faces, min_print, relief)
    np.testing.assert_array_equal(once, twice)


@mesh_settings
@given(st.floats(0.8, 3.0), st.floats(0.1, 0.6))
def test_guarded_relief_never_thins_a_slab_below_the_minimum(t, relief):
    # End to end: worst-case relief pushes both faces inward by the full amount, and the guarded slab still measures at least the minimum
    m = slab(t)
    idx = interior_top(m)
    wall, hit = wall_thickness(m)
    amount, _ = guard_relief(np.full(len(m.vertices), -relief), wall, hit, m.faces, 1.2, relief)
    m.vertices = m.vertices + m.vertex_normals * amount[:, None]
    after, _ = wall_thickness(m)
    assert after[idx].min() >= 1.2 - 0.01


@mesh_settings
@given(st.floats(1.0, 12.0), st.floats(4.0, 16.0), st.floats(0, 40), st.floats(0, 40))
def test_hit_face_lies_across_the_measured_wall(t, width, ax, ay):
    # The guard blocks the face a vertex's ray hit, so that face must be across the wall the vertex reports, not somewhere deep in a thick part
    m = rotated(trimesh.creation.box(extents=[width, width, t]).subdivide_to_size(0.5), ax, ay, 0)
    wall, hit = wall_thickness(m)
    has = np.where(hit >= 0)[0]
    tri = m.triangles[hit[has]]
    gap = np.linalg.norm(trimesh.triangles.closest_point(tri, m.vertices[has]) - m.vertices[has], axis=1)
    assert (gap <= 2 * wall[has] + 0.5).all()


def test_guard_leaves_a_thick_block_alone():
    # A 10 mm block's faces are far from any thin wall, so the guard must pass a small inward move straight through
    m = trimesh.creation.box(extents=[14.0, 14.0, 10.0]).subdivide_to_size(0.35)
    wall, hit = wall_thickness(m)
    amount, outward = guard_relief(np.full(len(m.vertices), -0.5), wall, hit, m.faces, 1.2, 0.2)
    idx = interior_top(m, width=14.0, margin=3.0)
    assert not outward[idx].any()
    np.testing.assert_array_equal(amount[idx], -0.5)


# Roughness


def test_flat_plate_has_no_roughness():
    m = slab(2.0)
    np.testing.assert_allclose(roughness(m)[interior_top(m)], 0, atol=1e-9)


@pytest.mark.parametrize("height", [0.1, 0.3, 0.9])
def test_a_single_spike_reads_its_height(height):
    m = slab(2.0)
    v = interior_top(m)[0]
    m.vertices[v, 2] += height
    r = roughness(m)
    assert r[v] == pytest.approx(height, rel=0.05)
    nbrs = m.vertex_neighbors[v]
    assert (r[nbrs] < r[v]).all()


@mesh_settings
@given(st.floats(0.5, 4.0))
def test_roughness_scales_with_the_model(k):
    m = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
    rng = np.random.default_rng(0)
    m.vertices += m.vertex_normals * rng.normal(0, 0.05, len(m.vertices))[:, None]
    big = m.copy()
    big.apply_scale(k)
    np.testing.assert_allclose(roughness(big), k * roughness(m), rtol=1e-6, atol=1e-9)
