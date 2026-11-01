"""End-to-end tests for true_surface.pull_back on shapes whose scan surface and wall thickness are known exactly."""
import numpy as np
import pytest
import trimesh
from scipy.spatial import cKDTree

from printcheck import self_intersections
from true_surface import pull_back

PITCH, MIN_WALL, MIN_PRINT, MARGIN = 0.35, 1.6, 1.2, 0.2
OFFSET = MIN_WALL / 2 + PITCH / 2


def slab(thickness, size=14.0, edge=0.35):
    """A box standing upright (scan +Y is up), thickness along Z, finely subdivided so the pull acts on many vertices."""
    m = trimesh.creation.box(extents=[size, size, thickness])
    while m.edges_unique_length.max() > edge:
        m = m.subdivide()
    m.apply_translation([0, size / 2, 0])
    return m


def plane_samples(z, size=14.0, step=0.14):
    g = np.arange(-size / 2, size / 2 + 1e-9, step)
    x, y = np.meshgrid(g, g + size / 2)
    return np.c_[x.ravel(), y.ravel(), np.full(x.size, z)]


def run(mesh, samples, **kw):
    normals = mesh.face_normals.copy()
    crossings = self_intersections(mesh)

    def folded(m):
        bad = np.einsum("ij,ij->i", m.face_normals, normals) < -0.3
        bad[np.setdiff1d(self_intersections(m), crossings)] = True
        return bad

    args = dict(pitch=PITCH, min_wall_mm=MIN_WALL, min_print_mm=MIN_PRINT, pull_margin_mm=MARGIN, bed_fade_mm=2.0, fold_cut=0.5, fold_ramp_mm=1.5, folded=folded)
    args.update(kw)
    return pull_back(mesh, samples, **args)


def interior(mesh, size=14.0):
    """Vertices on the two big faces, away from the rim, the bed fade and the corners where wall rays run along the face."""
    v = mesh.vertices
    return (np.abs(v[:, 0]) < size / 2 - 3) & (v[:, 1] > 6) & (v[:, 1] < size - 3)


def test_thin_sheet_gives_up_its_spare_wall_on_both_sides():
    # A 0.6 mm plate scanned on both faces, thickened by OFFSET each side as the voxel solid does; each side may give up half the wall above MIN_PRINT + MARGIN
    real = 0.6
    m = slab(real + 2 * OFFSET)
    scan = np.r_[plane_samples(real / 2), plane_samples(-real / 2)]
    verts, report = run(m, scan)
    keep = interior(m)
    wall = real + 2 * OFFSET
    expected = (wall - MIN_PRINT - MARGIN) / 2
    moved = np.linalg.norm(verts - m.vertices, axis=1)[keep]
    np.testing.assert_allclose(moved, expected, atol=0.03)
    assert not report["masks"]["guard"][keep].any()


def test_thick_wall_lands_on_the_scan():
    m = slab(10.0)
    scan = np.r_[plane_samples(5.0 - OFFSET), plane_samples(-5.0 + OFFSET)]
    verts, report = run(m, scan)
    keep = interior(m)
    np.testing.assert_allclose(np.abs(verts[keep, 2]), 5.0 - OFFSET, atol=0.03)


@pytest.mark.parametrize("thickness", [2.2, 2.6, 3.0, 3.4, 4.0])
def test_pull_is_uniform_across_a_flat_face(thickness):
    # A patchwork of pulled and unpulled vertices on a flat face is exactly the noise this guards against
    m = slab(thickness)
    real = thickness - 2 * OFFSET
    scan = np.r_[plane_samples(real / 2), plane_samples(-real / 2)]
    verts, _ = run(m, scan)
    moved = np.linalg.norm(verts - m.vertices, axis=1)[interior(m)]
    assert moved.max() - moved.min() < 0.05


def test_walls_never_end_below_the_printable_minimum():
    for thickness in (1.5, 1.8, 2.2, 3.0):
        m = slab(thickness)
        real = max(thickness - 2 * OFFSET, 0.05)
        scan = np.r_[plane_samples(real / 2), plane_samples(-real / 2)]
        verts, _ = run(m, scan)
        z = verts[interior(m), 2]
        assert z[z > 0].min() - z[z < 0].max() >= min(thickness, MIN_PRINT + MARGIN) - 0.02


def test_report_accounts_for_every_stage():
    m = slab(10.0)
    scan = np.r_[plane_samples(5.0 - OFFSET), plane_samples(-5.0 + OFFSET)]
    _, report = run(m, scan)
    assert set(report["blocked"]) == {"bed_fade", "hold", "guard", "folds", "thin"}
    assert report["blocked"]["bed_fade"] > 0
    # Only the block's rims, where a 90 degree edge reads as a thin wall, may lose pull to the guard; the faces never do
    assert not report["masks"]["guard"][interior(m)].any()
    assert report["blocked"]["folds"] == 0 and report["blocked"]["hold"] == 0
    assert 0 < report["applied_share"] <= 1


def test_hold_mask_keeps_those_vertices_in_place():
    m = slab(10.0)
    scan = np.r_[plane_samples(5.0 - OFFSET), plane_samples(-5.0 + OFFSET)]
    hold = m.vertices[:, 0] > 0
    verts, report = run(m, scan, hold=hold)
    # One smoothing pass blends the pull across the hold's border, so check a vertex ring in from it
    inside = hold & interior(m) & (m.vertices[:, 0] > 1.0)
    np.testing.assert_allclose(verts[inside], m.vertices[inside], atol=0.02)
    # Relaxing must not move held vertices either, even where they sit on a sharp edge
    edge = hold & (np.abs(np.abs(m.vertices[:, 2]) - 5.0) < 1e-6) & (np.abs(m.vertices[:, 0] - 7.0) < 1e-6)
    np.testing.assert_array_equal(verts[edge], m.vertices[edge])
    assert report["blocked"]["hold"] > 0.3


def voxel_branch(radius=1.75, length=14.0, pitch=PITCH, lift=4.0):
    """A horizontal round branch built like the real solid: voxels at the build pitch, then marching cubes, so it carries the same staircase."""
    from skimage import measure
    pad = 3
    g = np.arange(-radius - pad * pitch, radius + pad * pitch, pitch)
    x = np.arange(-length / 2 - pad * pitch, length / 2 + pad * pitch, pitch)
    X, Y, Z = np.meshgrid(x, g, g, indexing="ij")
    field = ((Y**2 + Z**2 <= radius**2) & (np.abs(X) <= length / 2)).astype(float)
    verts, faces, _, _ = measure.marching_cubes(field, 0.5, spacing=(pitch, pitch, pitch))
    verts += [x[0], g[0], g[0]]
    m = trimesh.Trimesh(verts, faces)
    if m.volume < 0:
        m.invert()
    m.apply_translation([0, lift + radius, 0])
    # A separate block sets the bed well below, so the bed fade leaves the branch alone
    bed = trimesh.creation.box(extents=[4.0, 1.0, 4.0])
    bed.apply_translation([length, -lift, 0])
    return trimesh.util.concatenate([m, bed])


def test_thin_round_part_shrinks_without_folding():
    # A branch 3.5 mm across, scanned at 1.6 mm across: shrinking it halves its triangles while the staircase tilts the pull directions, which crumpled such parts until the pulled surface was relaxed before judging folds
    branch = voxel_branch()
    mid = np.abs(branch.vertices[:, 0]) < 4
    cy, cz = branch.vertices[mid, 1].mean(), branch.vertices[mid, 2].mean()
    a = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    A, X = np.meshgrid(a, np.arange(-7.0, 7.0, 0.1))
    bed = trimesh.creation.box(extents=[4.0, 1.0, 4.0]).vertices + [14.0, -4.0, 0]
    scan = np.r_[np.c_[X.ravel(), cy + 0.8 * np.cos(A.ravel()), cz + 0.8 * np.sin(A.ravel())], bed]
    verts, report = run(branch, scan)
    assert report["blocked"]["folds"] < 0.02
    r = np.hypot(verts[mid, 1] - cy, verts[mid, 2] - cz)
    assert np.median(r) < np.median(np.hypot(branch.vertices[mid, 1] - cy, branch.vertices[mid, 2] - cz)) - 0.3


def test_relaxed_branch_keeps_the_printable_minimum():
    # Relaxing shrinks a thin round part a little more than the wall budget allowed for, so the walls must be measured again afterwards
    from printcheck import wall_thickness
    branch = voxel_branch(radius=1.2)
    mid = (np.abs(branch.vertices[:, 0]) < 4) & (branch.vertices[:, 1] > 0)
    cy, cz = branch.vertices[mid, 1].mean(), branch.vertices[mid, 2].mean()
    a = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    A, X = np.meshgrid(a, np.arange(-7.0, 7.0, 0.1))
    scan = np.c_[X.ravel(), cy + 0.3 * np.cos(A.ravel()), cz + 0.3 * np.sin(A.ravel())]
    verts, report = run(branch, scan)
    wall, _ = wall_thickness(trimesh.Trimesh(verts, branch.faces, process=False))
    assert wall[mid].min() >= MIN_PRINT - 0.02
    assert not report["masks"]["thinned"][mid].any()


def test_hold_ramp_fades_the_pull_instead_of_leaving_a_step():
    # A hold that switches off at a line leaves a step as tall as the pull along that line; a ramp spreads it over ramp_mm
    m = slab(10.0)
    scan = np.r_[plane_samples(5.0 - OFFSET), plane_samples(-5.0 + OFFSET)]
    hold = m.vertices[:, 0] > 0
    verts, _ = run(m, scan, hold=hold, hold_ramp_mm=3.0)
    face = interior(m) & (m.vertices[:, 2] > 0)
    x, moved = m.vertices[face, 0], np.linalg.norm(verts - m.vertices, axis=1)[face]
    full = OFFSET
    np.testing.assert_allclose(moved[x < -3.5], full, atol=0.03)
    # Within the ramp the pull follows distance to the nearest held vertex
    gap = cKDTree(m.vertices[hold]).query(m.vertices[face])[0]
    ramp = (gap > 0.5) & (gap < 2.5)
    np.testing.assert_allclose(moved[ramp], full * gap[ramp] / 3.0, atol=0.05)
    np.testing.assert_allclose(moved[x > 0.5], 0.0, atol=0.02)
    # No step: across the border the pull changes by no more than the ramp's slope allows over one vertex spacing
    order = np.argsort(x)
    xs, ms = x[order], moved[order]
    bins = np.round(xs / 0.35).astype(int)
    per_bin = np.array([ms[bins == b].mean() for b in np.unique(bins)])
    assert np.abs(np.diff(per_bin)).max() < full * 0.35 / 3.0 + 0.05


def test_rod_floor_lowers_the_minimum_on_rods_but_not_on_sheets():
    # A claw or twig is a rod whose cross-section spans about its own thickness both ways; a wing or feather is a sheet spread far wider than it is thick
    from printcheck import wall_thickness
    from true_surface import rod_floor
    rod = voxel_branch(radius=0.8)
    mid = (np.abs(rod.vertices[:, 0]) < 4) & (rod.vertices[:, 1] > 0)
    floor = rod_floor(rod.vertices, rod.vertex_normals, wall_thickness(rod)[0], MIN_PRINT, 0.45)
    np.testing.assert_allclose(floor[mid], 0.45, atol=0.05)
    sheet = slab(1.2)
    floor = rod_floor(sheet.vertices, sheet.vertex_normals, wall_thickness(sheet)[0], MIN_PRINT, 0.45)
    np.testing.assert_allclose(floor[interior(sheet)], MIN_PRINT)
    # A sheet's rim is as narrow as a rod across but faces mostly the sheet's two sides, and a wing's rim must keep its minimum
    v = sheet.vertices
    rim = (np.abs(v[:, 0]) > 7.0 - 0.7) & (v[:, 1] > 4) & (v[:, 1] < 10)
    np.testing.assert_allclose(floor[rim], MIN_PRINT, atol=0.01)


def test_rod_with_a_lower_floor_comes_back_thinner_than_the_minimum():
    # A claw scanned 0.6 mm across returns toward that size when its floor is lowered, without going under the floor or folding
    from printcheck import wall_thickness
    from true_surface import rod_floor
    branch = voxel_branch(radius=0.8)
    mid = (np.abs(branch.vertices[:, 0]) < 4) & (branch.vertices[:, 1] > 0)
    cy, cz = branch.vertices[mid, 1].mean(), branch.vertices[mid, 2].mean()
    a = np.linspace(0, 2 * np.pi, 400, endpoint=False)
    A, X = np.meshgrid(a, np.arange(-7.0, 7.0, 0.1))
    scan = np.c_[X.ravel(), cy + 0.3 * np.cos(A.ravel()), cz + 0.3 * np.sin(A.ravel())]
    floor = rod_floor(branch.vertices, branch.vertex_normals, wall_thickness(branch)[0], MIN_PRINT, 0.45)
    verts, report = run(branch, scan, min_print_mm=floor)
    wall, _ = wall_thickness(trimesh.Trimesh(verts, branch.faces, process=False))
    assert np.median(wall[mid]) < MIN_PRINT - 0.3
    assert wall[mid].min() >= 0.45 - 0.05
    assert report["blocked"]["folds"] < 0.02
