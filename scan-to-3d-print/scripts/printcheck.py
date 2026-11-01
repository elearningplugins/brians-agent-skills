"""Print measurements shared by check_print.py and a build script's wall guard, so both measure walls the same way: wall thickness, support, islands, self-intersections, roughness and the relief wall guard."""
import numpy as np
import scipy.sparse
import trimesh
from shapely.strtree import STRtree


CONE_DEG = 20.0
CONE_RAYS = 6


def _first_hits(mesh, origins, dirs, skip, max_dist=None, rounds=6):
    """Distance and face of each ray's first hit that skip(rays, faces) does not reject, re-casting past rejected hits; inf and -1 when there is none (within max_dist, per ray)."""
    limit = np.full(len(origins), np.inf) if max_dist is None else max_dist
    dist = np.full(len(origins), np.inf)
    face = np.full(len(origins), -1)
    start, travelled, todo = origins.copy(), np.zeros(len(origins)), np.arange(len(origins))
    for _ in range(rounds):
        if not len(todo):
            break
        locs, ri, ti = mesh.ray.intersects_location(start[todo], dirs[todo], multiple_hits=False)
        rays = todo[ri]
        d = travelled[rays] + np.linalg.norm(locs - start[rays], axis=1)
        inside = d < limit[rays]
        rejected = skip(rays, ti) & inside
        keep = ~rejected & inside
        dist[rays[keep]], face[rays[keep]] = d[keep], ti[keep]
        travelled[rays[rejected]] = d[rejected]
        # A step under float32 resolution re-hits the same face, so step 0.1 micrometre past it
        start[rays[rejected]] = locs[rejected] + dirs[rays[rejected]] * 1e-4
        todo = rays[rejected]
    return dist, face


def _near_faces(mesh):
    """Sorted keys vertex * n_faces + face for every face within two rings of each vertex, the faces a ray from that vertex can clip in a crease."""
    v_f = scipy.sparse.csr_matrix((np.ones(mesh.faces.size), (mesh.faces.ravel(), np.repeat(np.arange(len(mesh.faces)), 3))), shape=(len(mesh.vertices), len(mesh.faces)))
    ring = ((v_f @ v_f.T) @ v_f).tocoo()
    return np.unique(ring.row.astype(np.int64) * len(mesh.faces) + ring.col)


def wall_thickness(mesh):
    """Shortest of a cone of inward rays from each vertex to where it exits the opposite wall, median over neighbours; returns (thickness, hit face or -1)."""
    n = mesh.vertex_normals
    # A cone around the normal: an oblique vertex normal reads a wall long, and the ray nearest the true wall normal reads it closest to true
    helper = np.where(np.abs(n[:, :1]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]])
    u = np.cross(n, helper)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    w = np.cross(n, u)
    tilt = np.radians(CONE_DEG)
    dirs = [-n] + [-(np.cos(tilt) * n + np.sin(tilt) * (np.cos(a) * u + np.sin(a) * w)) for a in np.linspace(0, 2 * np.pi, CONE_RAYS, endpoint=False)]
    dirs = np.concatenate(dirs)
    owner = np.tile(np.arange(len(mesh.vertices)), CONE_RAYS + 1)
    origins = mesh.vertices[owner] - n[owner] * 1e-3
    near = _near_faces(mesh)
    # A ray that clips a face beside its own vertex is grazing a crease, not crossing the wall, so it carries on past that face
    own = lambda rays, faces: np.isin(owner[rays].astype(np.int64) * len(mesh.faces) + faces, near, assume_unique=False)
    dist, face = _first_hits(mesh, origins, dirs, own)
    # Only trust hits that exit through an outward-facing wall
    exits = np.einsum("ij,ij->i", mesh.face_normals[np.maximum(face, 0)], dirs) > 0
    dist[(face < 0) | ~exits] = np.inf
    per_vertex = dist.reshape(CONE_RAYS + 1, -1)
    best = per_vertex.argmin(0)
    raw = per_vertex[best, np.arange(len(mesh.vertices))]
    hit = np.where(np.isfinite(raw), face.reshape(CONE_RAYS + 1, -1)[best, np.arange(len(mesh.vertices))], -1)
    # Median over each vertex and its neighbours suppresses single-ray noise from surface relief
    thickness = np.array([np.median(np.append(raw[nbrs], raw[v])) for v, nbrs in enumerate(mesh.vertex_neighbors)])
    # A corner can read thin from its neighbours while its own ray crosses the whole part, and the guard would then freeze a face deep across it, so name the hit face only when it lies across the wall reported
    hit[raw > 1.5 * thickness + 0.1] = -1
    return thickness, hit


def _cells(lo, hi, size, max_cells):
    """Grid cells each box covers, as (box index, cell key) pairs, for boxes covering at most max_cells; also returns the boxes covering more."""
    first, last = np.floor(lo / size).astype(np.int64), np.floor(hi / size).astype(np.int64)
    span = last - first + 1
    count = span.prod(1)
    small = np.flatnonzero(count <= max_cells)
    box = np.repeat(small, count[small])
    local = np.arange(len(box)) - np.repeat(np.cumsum(count[small]) - count[small], count[small])
    sy, sz = span[box, 1], span[box, 2]
    cell = first[box] + np.stack([local // (sy * sz), (local // sz) % sy, local % sz], 1)
    # Cell coordinates stay within about a million of zero for any model on a print bed, so 21 bits each pack into one key
    key = ((cell[:, 0] + 2**20) << 42) | ((cell[:, 1] + 2**20) << 21) | (cell[:, 2] + 2**20)
    return box, key, np.flatnonzero(count > max_cells)


def _crossing(mesh, a, b, edge, face, tol):
    """For each (edge, face) pair, whether the segment a-b passes through the face's interior, its ends more than tol on opposite sides of the plane."""
    tri = mesh.triangles[face]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    norm = np.linalg.norm(n, axis=1)
    da = np.einsum("ij,ij->i", a[edge] - tri[:, 0], n)
    db = np.einsum("ij,ij->i", b[edge] - tri[:, 0], n)
    ok = (da * db < 0) & (np.minimum(np.abs(da), np.abs(db)) > tol * norm)
    x = a[edge] + (b[edge] - a[edge]) * (da / np.where(ok, da - db, 1.0))[:, None]
    for i in range(3):
        ok &= np.einsum("ij,ij->i", np.cross(tri[:, (i + 1) % 3] - tri[:, i], x - tri[:, i]), n) > 0
    return ok


def self_intersections(mesh, tol=1e-6):
    """Faces that an edge of the mesh passes through, other than the faces at that edge's own ends, plus the faces along each such edge; a clean surface has none."""
    # Exact segment-triangle tests in double precision: rays cast along an edge graze that edge's own faces, which left about half the edges of a printed model unchecked
    e = mesh.edges_unique
    a, b = mesh.vertices[e[:, 0]], mesh.vertices[e[:, 1]]
    tri = mesh.triangles
    flo, fhi = tri.min(1), tri.max(1)
    elo, ehi = np.minimum(a, b), np.maximum(a, b)
    size = 2 * float(np.median(np.linalg.norm(b - a, axis=1)))
    fbox, fkey, fbig = _cells(flo, fhi, size, 64)
    ebox, ekey, ebig = _cells(elo, ehi, size, 64)
    order = np.argsort(fkey, kind="stable")
    fbox, fkey = fbox[order], fkey[order]
    crossing_edges, crossed = [], []

    def test(edge, face):
        # Faces sharing a vertex with the edge meet it at that vertex, not across the surface
        shared = (mesh.faces[face] == e[edge, 0][:, None]).any(1) | (mesh.faces[face] == e[edge, 1][:, None]).any(1)
        overlap = ((elo[edge] <= fhi[face]) & (ehi[edge] >= flo[face])).all(1)
        keep = ~shared & overlap
        edge, face = edge[keep], face[keep]
        hit = _crossing(mesh, a, b, edge, face, tol)
        crossing_edges.append(edge[hit])
        crossed.append(face[hit])

    chunk = 2_000_000
    for i in range(0, len(ebox), chunk):
        eb, ek = ebox[i:i + chunk], ekey[i:i + chunk]
        left, right = np.searchsorted(fkey, ek, "left"), np.searchsorted(fkey, ek, "right")
        count = right - left
        edge = np.repeat(eb, count)
        face = fbox[np.repeat(left, count) + np.arange(count.sum()) - np.repeat(np.cumsum(count) - count, count)]
        # A pair sharing several cells is tested once per cell; deduplicating costs more than the repeat tests
        test(edge, face)
    # Boxes too large for the grid are tested against everything whose box they overlap
    for f in fbig:
        edge = np.flatnonzero(((elo <= fhi[f]) & (ehi >= flo[f])).all(1))
        test(edge, np.full(len(edge), f))
    for g in ebig:
        face = np.flatnonzero(((flo <= ehi[g]) & (fhi >= elo[g])).all(1))
        test(np.full(len(face), g), face)
    crossing_edges, crossed = np.concatenate(crossing_edges), np.concatenate(crossed)
    along = np.flatnonzero(np.isin(mesh.faces_unique_edges, crossing_edges).any(1))
    return np.union1d(crossed, along)


def needs_support(mesh, support_angle_deg, layer_mm):
    """Faces flatter than the slicer's support threshold (degrees from horizontal) that are not on the bed."""
    return (mesh.face_normals[:, 2] < -np.cos(np.radians(support_angle_deg))) & (mesh.triangles_center[:, 2] > layer_mm * 1.5)


def find_islands(mesh, layer_mm, min_area_mm2):
    """Slices like a slicer and returns each cross-section with nothing beneath it in the previous layer."""
    heights = np.arange(layer_mm / 2, mesh.bounds[1][2] - mesh.bounds[0][2], layer_mm) + mesh.bounds[0][2]
    sections = mesh.section_multiplane(plane_origin=[0, 0, 0], plane_normal=[0, 0, 1], heights=heights)
    islands = []
    prev = None
    for z, sec in zip(heights, sections):
        layer = list(sec.polygons_full) if sec is not None else []
        polys = [p for p in layer if p.area >= min_area_mm2]
        if prev is not None and polys:
            tree = STRtree(prev) if prev else None
            for p in polys:
                if tree is None or not any(p.intersects(prev[i]) for i in tree.query(p)):
                    islands.append({"z_mm": round(float(z), 2), "xy_mm": [round(c, 1) for c in p.centroid.coords[0]], "area_mm2": round(p.area, 2)})
        # Every section, even one too small to report, supports the next layer; an empty layer supports nothing
        prev = layer
    return islands


def roughness(mesh):
    """How far each vertex stands off the mean of its neighbours, along its normal, in mesh units: zero on a flat or evenly curved surface, the spike height at a lone spike."""
    L = trimesh.smoothing.laplacian_calculation(mesh, equal_weight=True)
    return np.abs(np.einsum("ij,ij->i", mesh.vertices - L @ mesh.vertices, mesh.vertex_normals))


def guard_relief(amount, wall, hit, faces, min_print_mm, relief_mm):
    """Limits relief displacement so no wall drops below min_print_mm; returns (amount, outward_only mask)."""
    # Both faces of a thin wall move, so each side may give up at most half of the spare thickness, and a wall already under target gains half the shortfall per side
    floor_amount = (min_print_mm - wall) / 2
    # Near the limit, relief may only push outward, on this side and on the far side its ray hit, because a far-side ray running obliquely reads thick and would let it push in
    near_limit = wall < min_print_mm + 2 * relief_mm
    outward_only = near_limit.copy()
    outward_only[faces[hit[near_limit & (hit >= 0)]].ravel()] = True
    floor_amount[outward_only] = np.maximum(floor_amount[outward_only], 0.0)
    return np.maximum(amount, floor_amount), outward_only
