"""Build a player-free spherical panorama of the field from a fixed-centre pan/zoom camera (Trace) and recover each frame's rotation and focal length."""
import argparse
import json
import pickle
import warnings
from pathlib import Path

import cv2
import numpy as np



def centered(H, w, h):
    C = np.array([[1, 0, -w / 2], [0, 1, -h / 2], [0, 0, 1.0]])
    return C @ H @ np.linalg.inv(C)


def rotation_error(Hc, f_ref):
    """How far K_ref^-1 H is from R diag(1/f, 1/f, 1) for a pure rotation plus zoom."""
    A = np.diag([1 / f_ref, 1 / f_ref, 1]) @ Hc
    c0, c1, c2 = A.T
    n0, n1, n2 = np.linalg.norm(A, axis=0)
    return ((n0 - n1) / (n0 + n1)) ** 2 + (c0 @ c1 / (n0 * n1)) ** 2 + (c0 @ c2 / (n0 * n2)) ** 2 + (c1 @ c2 / (n1 * n2)) ** 2


def decompose(Hc, f_ref):
    A = np.diag([1 / f_ref, 1 / f_ref, 1]) @ Hc
    n0, n1, n2 = np.linalg.norm(A, axis=0)
    f = n2 / ((n0 + n1) / 2)
    U, _, Vt = np.linalg.svd(A @ np.diag([f, f, 1]))
    R = U @ Vt
    if np.linalg.det(R) < 0:
        R = -R
    return f, R


def rays_to_angles(d):
    return np.arctan2(d[..., 0], d[..., 2]), np.arctan2(d[..., 1], np.hypot(d[..., 0], d[..., 2]))


def angles_to_rays(th, ph):
    return np.stack([np.sin(th) * np.cos(ph), np.sin(ph), np.cos(th) * np.cos(ph)], -1)


def match(a, b, keep=80):
    """Homography from frame a to frame b plus a sample of its inlier point pairs."""
    ka, da = a
    kb, db = b
    if da is None or db is None or len(ka) < 20 or len(kb) < 20:
        return None, 0, None
    m = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [x for x, y in (p for p in m if len(p) == 2) if x.distance < 0.75 * y.distance]
    if len(good) < 30:
        return None, len(good), None
    pa = np.float32([ka[g.queryIdx].pt for g in good])
    pb = np.float32([kb[g.trainIdx].pt for g in good])
    H, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 2.0)
    if H is None:
        return None, 0, None
    inl = inl.ravel().astype(bool)
    idx = np.where(inl)[0]
    idx = np.random.default_rng(0).choice(idx, min(keep, len(idx)), replace=False)
    return H, int(inl.sum()), (pa[idx], pb[idx])


def register_all(frames, min_inliers=40, loops=2):
    sift = cv2.SIFT_create(2000)
    feats = [sift.detectAndCompute(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), None) for f in frames]
    w, h = frames[0].shape[1], frames[0].shape[0]
    H = [None] * len(frames)
    inl = [0] * len(frames)
    links = []
    H[0] = np.eye(3)
    centres = {0: np.array([w / 2, h / 2])}
    last = 0
    for i in range(1, len(frames)):
        Hp, n, pp = match(feats[i], feats[last])
        cands = [(n, Hp, last, pp)] if Hp is not None and n >= min_inliers else []
        c = None
        if Hp is not None:
            g = H[last] @ Hp @ [w / 2, h / 2, 1]
            c = g[:2] / g[2] if g[2] > 0 else None
        if c is None:
            c = centres.get(last)
        if c is not None:
            older = [k for k in centres if k < last - 3]
            for k in sorted(older, key=lambda k: np.linalg.norm(centres[k] - c))[:loops]:
                Hk, nk, pk = match(feats[i], feats[k])
                if Hk is not None and nk >= min_inliers:
                    cands.append((nk, Hk, k, pk))
        if not cands:
            continue
        n, Hb, k, _ = max(cands, key=lambda x: x[0])
        H[i] = H[k] @ Hb
        inl[i] = n
        links += [(i, kk, pts) for _, _, kk, pts in cands]
        c = H[i] @ [w / 2, h / 2, 1]
        if c[2] > 0:
            centres[i] = c[:2] / c[2]
        last = i
    return H, inl, links


def rodrigues(v):
    return cv2.Rodrigues(np.asarray(v, float))[0]


def bundle_adjust(cams, links, w, h, fixed):
    """Jointly refine every frame's rotation and focal length so matched points from all links agree (rotation-only camera)."""
    from scipy.optimize import least_squares
    from scipy.sparse import lil_matrix

    ids = sorted(cams)
    pos = {i: n for n, i in enumerate(ids)}
    x0 = np.concatenate([np.r_[cv2.Rodrigues(cams[i][1])[0].ravel(), np.log(cams[i][0])] for i in ids])
    c = np.array([w / 2, h / 2])
    pairs = [(pos[i], pos[k], (pi - c).astype(float), (pk - c).astype(float)) for i, k, (pi, pk) in links if i in pos and k in pos]
    n_res = sum(2 * len(p[2]) for p in pairs)
    sp = lil_matrix((n_res, 4 * len(ids)), dtype=np.uint8)
    r = 0
    for a, b, pa, _ in pairs:
        rows = slice(r, r + 2 * len(pa))
        sp[rows, 4 * a:4 * a + 4] = 1
        sp[rows, 4 * b:4 * b + 4] = 1
        r += 2 * len(pa)
    fa = pos[fixed]

    def residuals(x):
        x = x.copy()
        x[4 * fa:4 * fa + 3] = x0[4 * fa:4 * fa + 3]
        out = []
        for a, b, pa, pb in pairs:
            Ra, fa_ = rodrigues(x[4 * a:4 * a + 3]), np.exp(x[4 * a + 3])
            Rb, fb_ = rodrigues(x[4 * b:4 * b + 3]), np.exp(x[4 * b + 3])
            d = np.column_stack([pa / fa_, np.ones(len(pa))]) @ Ra.T @ Rb
            out.append((fb_ * d[:, :2] / d[:, 2:3] - pb).ravel())
        return np.concatenate(out)

    before = np.median(np.abs(residuals(x0)))
    lo = np.tile([-np.pi, -np.pi, -np.pi, np.log(150)], len(ids))
    hi = np.tile([np.pi, np.pi, np.pi, np.log(8000)], len(ids))
    sol = least_squares(residuals, np.clip(x0, lo + 1e-6, hi - 1e-6), jac_sparsity=sp, bounds=(lo, hi), loss="huber", f_scale=2.0, method="trf", max_nfev=60)
    after = np.abs(residuals(sol.x))
    print(f"bundle adjustment: median residual {before:.2f}px -> {np.median(after):.2f}px (90th pct {np.percentile(after, 90):.2f}px)")
    x = sol.x
    x[4 * fa:4 * fa + 3] = x0[4 * fa:4 * fa + 3]
    return {i: (float(np.exp(x[4 * pos[i] + 3])), rodrigues(x[4 * pos[i]:4 * pos[i] + 3])) for i in ids}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--step", type=float, default=5.0, help="seconds between extracted frames")
    ap.add_argument("--out", required=True)
    ap.add_argument("--median-frames", type=int, default=90)
    args = ap.parse_args()

    paths = sorted(Path(args.frames_dir).glob("*.jpg"))
    frames = [cv2.imread(str(p)) for p in paths]
    h, w = frames[0].shape[:2]
    cache = Path(args.out).with_suffix(".registration.pkl")
    if cache.exists():
        H, inl, links = pickle.loads(cache.read_bytes())
    else:
        H, inl, links = register_all(frames)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pickle.dumps((H, inl, links)))
    ok = [i for i, x in enumerate(H) if x is not None]
    print(f"registered {len(ok)}/{len(frames)} frames over {len(links)} links, median inliers {np.median([inl[i] for i in ok[1:]]):.0f}")

    Hc = {i: centered(H[i], w, h) for i in ok}
    informative = [i for i in ok if np.abs(Hc[i] - np.eye(3) * Hc[i][2, 2]).max() > 0.05 * abs(Hc[i][2, 2])]
    grid = np.geomspace(300, 6000, 400)
    errs = [np.median([rotation_error(Hc[i], f) for i in informative]) for f in grid]
    f_ref = float(grid[int(np.argmin(errs))])
    print(f"f_ref={f_ref:.0f} rotation-model error {min(errs):.2e} over {len(informative)} frames")

    cams = {i: decompose(Hc[i], f_ref) for i in ok}
    bad = [i for i, (f, R) in cams.items() if not (np.isfinite(f) and 0.2 * f_ref < f < 8 * f_ref and np.isfinite(R).all())]
    for i in bad:
        del cams[i]
    print(f"dropped {len(bad)} frames with an implausible zoom; focal range {min(c[0] for c in cams.values()):.0f}-{max(c[0] for c in cams.values()):.0f}")
    cams = bundle_adjust(cams, links, w, h, fixed=0)
    ok = sorted(cams)
    f_ref = cams[0][0]
    border = np.vstack([np.column_stack([np.linspace(-w / 2, w / 2, 20), np.full(20, y)]) for y in (-h / 2, h / 2)]
                       + [np.column_stack([np.full(20, x), np.linspace(-h / 2, h / 2, 20)]) for x in (-w / 2, w / 2)])
    th_all, ph_all = [], []
    for f, R in cams.values():
        d = (R @ np.column_stack([border / f, np.ones(len(border))]).T).T
        th, ph = rays_to_angles(d)
        th_all.append(th); ph_all.append(ph)
    th_all, ph_all = np.concatenate(th_all), np.concatenate(ph_all)
    th0, th1 = np.percentile(th_all, [0.5, 99.5])
    ph0, ph1 = np.percentile(ph_all, [0.5, 99.5])
    res = max(1 / f_ref, (th1 - th0) / 3200)
    W, Hh = int((th1 - th0) / res), int((ph1 - ph0) / res)
    print(f"panorama {W}x{Hh}, pan {np.degrees(th1 - th0):.0f} deg, tilt {np.degrees(ph1 - ph0):.0f} deg")

    th, ph = np.meshgrid(th0 + np.arange(W) * res, ph0 + np.arange(Hh) * res)
    d = angles_to_rays(th, ph).astype(np.float32)
    use = ok[:: max(1, len(ok) // args.median_frames)]
    stack, masks = [], []
    for i in use:
        f, R = cams[i]
        v = d @ R.astype(np.float32)
        front = v[..., 2] > 1e-3
        mx = np.where(front, f * v[..., 0] / np.maximum(v[..., 2], 1e-3) + w / 2, -1).astype(np.float32)
        my = np.where(front, f * v[..., 1] / np.maximum(v[..., 2], 1e-3) + h / 2, -1).astype(np.float32)
        stack.append(cv2.remap(frames[i], mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT))
        masks.append((mx >= 0) & (mx < w - 1) & (my >= 0) & (my < h - 1))
    pano = np.zeros((Hh, W, 3), np.uint8)
    count = np.sum(masks, axis=0)
    for r0 in range(0, Hh, 64):
        chunk = np.stack([s[r0:r0 + 64] for s in stack]).astype(np.float32)
        m = np.stack([k[r0:r0 + 64] for k in masks])
        chunk[~m] = np.nan
        with np.errstate(all="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            pano[r0:r0 + 64] = np.nan_to_num(np.nanmedian(chunk, axis=0)).astype(np.uint8)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out.with_suffix(".jpg")), pano)
    cv2.imwrite(str(out.with_suffix(".coverage.png")), np.clip(count * 255 // max(1, count.max()), 0, 255).astype(np.uint8))
    json.dump({"width": w, "height": h, "f_ref": f_ref, "theta0": float(th0), "phi0": float(ph0), "res": float(res),
               "pano_width": W, "pano_height": Hh,
               "frames": [{"file": paths[i].name, "t": i * args.step, "inliers": inl[i], "f": cams[i][0], "R": cams[i][1].tolist()} for i in ok]},
              open(out.with_suffix(".json"), "w"))
    print(f"wrote {out.with_suffix('.jpg')} from {len(use)} frames")


if __name__ == "__main__":
    main()
