"""Renders a print STL beside its reference scan, and optionally a photo, from hand-picked cameras, plain or as distance heat maps: python compare_views.py print.stl reference.ply views.json out.jpg [--heat]."""
import argparse
import json

import numpy as np
import trimesh
from PIL import Image, ImageDraw
from scipy.spatial import cKDTree


def camera(elev, azim):
    """Right, up and toward-camera unit vectors for a camera at elev and azim degrees, Z up; azim -90 looks from -Y."""
    e, a = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    right = np.cross([0, 0, 1], view)
    right /= np.linalg.norm(right)
    return right, np.cross(view, right), view


def distance_to(points, mesh, samples=2_000_000):
    """Distance from each point to the nearest of a dense sample of the mesh surface."""
    pts, _ = trimesh.sample.sample_surface(mesh, samples, seed=0)
    return cKDTree(pts).query(points, workers=-1)[0]


def render(mesh, centre, rad, elev, azim, px, two_sided, values=None, vmax=1.0):
    """Z-buffered point splat of the mesh inside a square of half-width rad around centre, as (image, mask of covered pixels); values per vertex colour it blue (0) to red (vmax); an open scan sheet is shaded from either side."""
    right, up, view = camera(elev, azim)
    light = 0.5 * right + 0.4 * up + 0.75 * view
    light /= np.linalg.norm(light)
    near = np.linalg.norm(mesh.triangles_center - centre, axis=1) < rad * 1.5
    faces = mesh.faces[near]
    sub = trimesh.Trimesh(mesh.vertices, faces, process=False)
    img = np.full((px, px, 3), 245, np.uint8)
    mask = np.zeros((px, px), bool)
    if not len(faces):
        return img, mask
    # Enough samples for several per pixel, so gaps in the splat are real holes rather than sparse sampling
    count = int(min(8_000_000, 6 * px * px * sub.area / (2 * rad) ** 2))
    pts, fi = trimesh.sample.sample_surface(sub, count, seed=0)
    q = pts - centre
    x, y, z = q @ right, q @ up, q @ view
    inside = (np.abs(x) < rad) & (np.abs(y) < rad)
    s = px / (2 * rad)
    cx = np.clip(((x + rad) * s).astype(int)[inside], 0, px - 1)
    cy = np.clip(((rad - y) * s).astype(int)[inside], 0, px - 1)
    z, n = z[inside], sub.face_normals[fi][inside]
    # Nearest sample per pixel wins: sort by pixel, then by depth toward the camera
    order = np.lexsort((-z, cy * px + cx))
    key = (cy * px + cx)[order]
    sel = order[np.r_[True, key[1:] != key[:-1]]]
    facing = n[sel] @ light
    shade = np.clip(np.abs(facing) if two_sided else facing, 0, 1) * 0.85 + 0.15
    colour = np.tile([0.75, 0.75, 0.78], (len(sel), 1))
    if values is not None:
        bary = trimesh.triangles.points_to_barycentric(sub.triangles[fi[inside][sel]], pts[inside][sel])
        heat = np.clip((np.asarray(values)[faces[fi[inside][sel]]] * bary).sum(1) / vmax, 0, 1)
        colour = np.c_[0.2 + 0.75 * heat, 0.25 * np.ones(len(heat)), 0.95 - 0.75 * heat]
    img[cy[sel], cx[sel]] = (colour * shade[:, None] * 255).astype(np.uint8)
    mask[cy[sel], cx[sel]] = True
    return img, mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("print_stl")
    ap.add_argument("reference", help="the scan, already moved into the print's coordinates and units")
    ap.add_argument("views", help='JSON list of {"name", "frac": [x, y, z] of the print bounding box, "rad": share of its height, "elev", "azim", optional "photo" path and "crop": [left, top, right, bottom]}')
    ap.add_argument("out")
    ap.add_argument("--heat", action="store_true", help="colour the print by distance to the reference (added material) and the reference by distance to the print (lost detail)")
    ap.add_argument("--vmax-mm", type=float, default=1.0)
    ap.add_argument("--px", type=int, default=520)
    args = ap.parse_args()
    printed, ref = trimesh.load(args.print_stl), trimesh.load(args.reference)
    lo, ext = printed.bounds[0], printed.extents
    values = (distance_to(printed.vertices, ref), distance_to(ref.vertices, printed)) if args.heat else (None, None)
    rows = []
    for v in json.load(open(args.views)):
        centre, rad = lo + np.array(v["frac"]) * ext, v["rad"] * ext[2]
        tiles = []
        if v.get("photo"):
            photo = Image.open(v["photo"])
            photo = photo.crop(tuple(v["crop"])) if v.get("crop") else photo
            photo.thumbnail((args.px, args.px))
            canvas = Image.new("RGB", (args.px, args.px), (245, 245, 245))
            canvas.paste(photo, ((args.px - photo.width) // 2, (args.px - photo.height) // 2))
            tiles.append(canvas)
        for label, mesh, vals, two in (("print", printed, values[0], False), ("reference", ref, values[1], True)):
            img, _ = render(mesh, centre, rad, v["elev"], v["azim"], args.px, two, vals, args.vmax_mm)
            tile = Image.fromarray(img)
            ImageDraw.Draw(tile).text((8, 8), f"{label}: {v['name']} el {v['elev']} az {v['azim']}", fill=(0, 0, 0))
            tiles.append(tile)
        rows.append(np.hstack([np.array(t) for t in tiles]))
    width = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, width - r.shape[1]), (0, 0)), constant_values=245) for r in rows]
    Image.fromarray(np.vstack(rows)).save(args.out, quality=90)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
