"""Pulls a solid thickened around a scan back onto the scan surface, as far as each wall can spare, and reports how much of the planned pull each safety stage removed."""
import numpy as np
import trimesh
from scipy.spatial import cKDTree

from printcheck import guard_relief, wall_thickness

# A vertex counts as wanting a pull, or as losing it to a stage, when the change is at least this many millimetres
SIGNIFICANT_MM = 0.1


def pull_back(mesh, sample_xyz, *, pitch, min_wall_mm, min_print_mm, pull_margin_mm, bed_fade_mm, fold_cut, fold_ramp_mm, folded, hold=None, hold_ramp_mm=0.0, max_attempts=20, relax_passes=5, thin_rounds=8):
    """Returns (vertices, report); scan +Y is up, folded(mesh) flags faces that flipped or cross another, hold marks vertices that must not move and hold_ramp_mm fades the pull in over that distance from them; report["masks"] marks, per stage, the vertices that lost their pull there."""
    offset = min_wall_mm / 2 + pitch / 2
    smooth = trimesh.smoothing.laplacian_calculation(mesh, equal_weight=True)
    wall, hit = wall_thickness(mesh)
    # Pull along smoothed normals: the scan's noisy normals send neighbouring vertices in crossing directions
    normals = mesh.vertex_normals.copy()
    for _ in range(8):
        normals = smooth @ normals
    normals /= np.linalg.norm(normals, axis=1, keepdims=True)
    # Voxel rounding leaves each vertex anywhere within about a voxel of the nominal offset, so pull each by its own measured depth to the scan; where the nearest scan lies off to the side, fall back to the nominal offset
    dist, nearest = cKDTree(sample_xyz).query(mesh.vertices, workers=-1)
    depth = -np.einsum("ij,ij->i", sample_xyz[nearest] - mesh.vertices, normals)
    lateral = np.sqrt(np.maximum(dist**2 - depth**2, 0))
    measured = np.where((depth > 0) & (lateral < pitch), np.clip(depth, 0, offset + pitch), offset)
    # Each side gives up half of whatever the wall has beyond the printable minimum plus a margin, so thin features come back to their scanned size instead of keeping the whole thickening
    spare = np.clip((np.where(np.isfinite(wall), wall, 0.0) - min_print_mm - pull_margin_mm) / 2, 0, None)
    target = -np.minimum(measured, spare)
    wanting = target < -SIGNIFICANT_MM
    blocked, masks = {}, {}

    def stage(name, before, after):
        masks[name] = ((after - before) > SIGNIFICANT_MM) & wanting
        blocked[name] = float(masks[name].sum() / max(wanting.sum(), 1))
        return after

    # The underside sits on the bed and must stay flat, so the pull fades out near the bed
    y = mesh.vertices[:, 1]
    pull = stage("bed_fade", target, target * np.clip((y - y.min() - bed_fade_mm) / bed_fade_mm, 0, 1))
    if hold is not None:
        # A hold that ends at a line leaves a step as tall as the pull there, so the pull fades in with distance from the nearest held vertex
        fade = np.zeros(len(pull))
        if hold.any() and hold_ramp_mm > 0:
            fade[~hold] = np.clip(cKDTree(mesh.vertices[hold]).query(mesh.vertices[~hold], workers=-1)[0] / hold_ramp_mm, 0, 1)
        else:
            fade[~hold] = 1.0
        pull = stage("hold", pull, pull * fade)
    else:
        pull = stage("hold", pull, pull)
    # One light pass only: heavier smoothing would blur the measured depths back into voxel-scale lumps
    pull = smooth @ pull
    # The guard's margin is the pull's own margin: given the full pull it blocked every wall under min_print + 2 x offset, and the far-side faces those walls' rays hit, which left a patchwork of pulled and unpulled surface
    guarded, _ = guard_relief(pull, wall, hit, mesh.faces, min_print_mm, pull_margin_mm)
    pull = stage("guard", pull, guarded)
    # Held vertices stay exactly where they are: the smoothing pass and the guard's outward push for thin walls must not move them either
    if hold is not None:
        pull[hold] = 0.0
    planned = pull.copy()
    fold_factor = np.ones(len(pull))
    thin_factor = np.ones(len(pull))
    # Held vertices must not move at all, so the relaxing leaves them alone as well as the bed
    frozen = (y < y.min() + bed_fade_mm) | (hold if hold is not None else False)
    rings_needed = max(1, int(np.ceil(fold_ramp_mm / mesh.edges_unique_length.mean())))
    for _ in range(thin_rounds + 1):
        for _ in range(max_attempts):
            moved = mesh.vertices + normals * (planned * fold_factor * thin_factor)[:, None]
            # Shrinking a thin round part halves its triangles while the pull direction still varies by a few degrees from vertex to vertex, which crumples them; a few Taubin passes on the pulled surface let the triangles settle before folds are judged
            if relax_passes:
                moved = taubin(moved, smooth, ~frozen, relax_passes)
            trial = trimesh.Trimesh(moved, mesh.faces, process=False)
            # Moving inward in a tight crease can fold the surface through itself; cut the pull around every triangle that flips or crosses another
            bad = folded(trial)
            if not bad.any():
                break
            region = np.zeros(len(pull), bool)
            region[mesh.faces[bad].ravel()] = True
            region |= (smooth @ region.astype(float)) > 0
            # Cut by fold_cut around each fold, ramped over fold_ramp_mm, so a fold leaves a gentle swell and not a step
            rings = np.full(len(pull), np.inf)
            front = region.copy()
            for k in range(rings_needed + 1):
                rings[front & np.isinf(rings)] = k
                front = (smooth @ front.astype(float)) > 0
            fold_factor *= 1 - fold_cut * np.clip(1 - rings / rings_needed, 0, 1)
        else:
            raise SystemExit(f"true surface: still folded after {max_attempts} attempts; rerun with --no-true-surface")
        # Each side sizes its pull from its own wall reading, and a ray crossing a wall at a slant reads it long, so both sides can take more than the wall spares; measure the result and give back half the pull nearest every wall this step took under the minimum
        after, _ = wall_thickness(trial)
        thinned = (after < min_print_mm - 0.02) & (wall >= min_print_mm)
        has_pull = (thin_factor > 0) & (planned * fold_factor < -SIGNIFICANT_MM)
        give, reach = thinned & has_pull, thinned.copy()
        # A lip left standing where both faces of a sheet pulled in is thin because of its neighbours' pull, so look outward a few rings for pull to give back
        for _ in range(6):
            if give.any() or not reach.any():
                break
            reach |= (smooth @ reach.astype(float)) > 0
            give = reach & has_pull
        if not give.any():
            break
        give |= (smooth @ give.astype(float)) > 0
        thin_factor[give] *= 0.5
        thin_factor[thin_factor < 0.07] = 0.0
    pull = planned * fold_factor * thin_factor
    stage("folds", planned, planned * fold_factor)
    stage("thin", planned, planned * thin_factor)
    masks["thinned"] = thinned
    applied = (pull <= target / 2) & wanting
    report = {"thinned_share": float(thinned.mean()), "wanting": int(wanting.sum()), "applied_share": float(applied.sum() / max(wanting.sum(), 1)), "blocked": blocked, "max_pull_mm": float(-pull.min()) if len(pull) else 0.0, "masks": masks}
    return trial.vertices, report


def rod_floor(vertices, normals, wall, min_print_mm, rod_print_mm, max_wall_mm=2.0, radius_scale=2.5, max_radius_mm=np.inf, rod_ratio=0.5, sheet_ratio=0.7, round_lo=0.25, round_hi=0.4, chunk=4000):
    """Per-vertex printable minimum: rod_print_mm on rods such as claws and twigs, min_print_mm elsewhere, blended in between; a vertex no thicker than max_wall_mm is on a rod when the second spread of the surface within radius_scale times its wall is under rod_ratio times the mean wall there and its normals face round it (second eigenvalue of their second moment above round_hi), and on a sheet above sheet_ratio or below round_lo."""
    floor = np.full(len(vertices), float(min_print_mm))
    # Thicker parts never come near the floor; the ball scales with the wall because a fixed ball fits inside a thick wing and reads it as a rod
    cand = np.where(np.isfinite(wall) & (wall < max_wall_mm))[0]
    if not len(cand):
        return floor
    tree = cKDTree(vertices)
    for start in range(0, len(cand), chunk):
        ids = cand[start:start + chunk]
        nbrs = tree.query_ball_point(vertices[ids], np.minimum(radius_scale * wall[ids], max_radius_mm), workers=-1)
        counts = np.array([len(n) for n in nbrs])
        seg = np.repeat(np.arange(len(ids)), counts)
        flat = np.concatenate(nbrs).astype(int)
        p = vertices[flat]
        mean = np.zeros((len(ids), 3))
        np.add.at(mean, seg, p)
        mean /= counts[:, None]
        d = p - mean[seg]
        cov = np.zeros((len(ids), 3, 3))
        np.add.at(cov, seg, d[:, :, None] * d[:, None, :])
        cov /= counts[:, None, None]
        # A rod's second spread is its own cross-section, about a third of its thickness; a sheet's is about half the ball's radius, over a wall
        second = np.sqrt(np.clip(np.linalg.eigvalsh(cov)[:, 1], 0, None))
        # One ray can read a voxel staircase a fifth thin, so compare with the mean wall around the vertex
        wsum = np.zeros(len(ids))
        np.add.at(wsum, seg, np.where(np.isfinite(wall[flat]), wall[flat], wall[ids][seg]))
        rodness = np.clip((sheet_ratio - second / (wsum / counts)) / (sheet_ratio - rod_ratio), 0, 1)
        # A sheet's rim is as narrow as a rod but faces mostly the sheet's two sides, while a rod faces every way round its axis
        nm = np.zeros((len(ids), 3, 3))
        nf = normals[flat]
        np.add.at(nm, seg, nf[:, :, None] * nf[:, None, :])
        round_ = np.linalg.eigvalsh(nm / counts[:, None, None])[:, 1]
        rodness *= np.clip((round_ - round_lo) / (round_hi - round_lo), 0, 1)
        floor[ids] = min_print_mm - rodness * (min_print_mm - rod_print_mm)
    return floor


def taubin(v, L, free, passes, lamb=0.5, nu=0.53):
    """Taubin smoothing of the free vertices: a shrinking step then a slightly larger growing one, which removes vertex-scale noise without shrinking the solid."""
    v = v.copy()
    for _ in range(passes):
        v[free] += lamb * (L @ v - v)[free]
        v[free] -= nu * (L @ v - v)[free]
    return v


def smooth_surface(mesh, *, passes, bed_fade_mm, folded, hold=None, lamb=0.5, nu=0.53, max_attempts=20):
    """Taubin smoothing, which removes vertex-scale spikes without shrinking the solid; the bed and held vertices stay put, and vertices around any fold it causes are put back; returns (vertices, report)."""
    y = mesh.vertices[:, 1]
    fixed = y < y.min() + bed_fade_mm
    if hold is not None:
        fixed |= hold
    L = trimesh.smoothing.laplacian_calculation(mesh, equal_weight=True)
    reverted = np.zeros(len(mesh.vertices), bool)
    for _ in range(max_attempts):
        v = taubin(mesh.vertices, L, ~(fixed | reverted), passes, lamb, nu)
        bad = folded(trimesh.Trimesh(v, mesh.faces, process=False))
        if not bad.any():
            break
        around = np.zeros(len(v), bool)
        around[mesh.faces[bad].ravel()] = True
        reverted |= around | ((L @ around.astype(float)) > 0)
    else:
        raise SystemExit(f"smoothing: still folded after {max_attempts} attempts")
    moved = np.linalg.norm(v - mesh.vertices, axis=1)
    return v, {"passes": passes, "reverted": int(reverted.sum()), "moved_median_mm": float(np.median(moved)), "moved_max_mm": float(moved.max())}
