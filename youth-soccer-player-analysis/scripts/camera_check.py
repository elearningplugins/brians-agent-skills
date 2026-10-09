"""Tell a fixed-centre camera (pan/zoom only, e.g. Trace or Veo) from a moving one by fitting one homography between frame pairs."""
import argparse

import cv2
import numpy as np


def grab(cap, t):
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit(f"could not read frame at {t}s")
    return frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--pairs", nargs="+", default=["60:65", "60:90"], help="start:end seconds")
    ap.add_argument("--background-rows", type=float, default=0.2, help="top fraction of the frame treated as background")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    sift = cv2.SIFT_create(4000)
    for pair in args.pairs:
        a, b = (float(x) for x in pair.split(":"))
        A, B = grab(cap, a), grab(cap, b)
        ka, da = sift.detectAndCompute(cv2.cvtColor(A, cv2.COLOR_BGR2GRAY), None)
        kb, db = sift.detectAndCompute(cv2.cvtColor(B, cv2.COLOR_BGR2GRAY), None)
        good = [m for m, n in (p for p in cv2.BFMatcher().knnMatch(da, db, k=2) if len(p) == 2) if m.distance < 0.75 * n.distance]
        if len(good) < 30:
            print(f"{pair}: only {len(good)} matches; views may not overlap or there is a cut")
            continue
        pa = np.float32([ka[g.queryIdx].pt for g in good])
        pb = np.float32([kb[g.trainIdx].pt for g in good])
        H, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 3.0)
        err = np.linalg.norm(cv2.perspectiveTransform(pa[None], H)[0] - pb, axis=1)
        bg = pa[:, 1] < args.background_rows * A.shape[0]
        bg_err = np.median(err[bg]) if bg.any() else float("nan")
        note = "  (low overlap; ignore this pair)" if inl.mean() < 0.3 else ""
        print(f"{pair}: matches={len(good)} inliers={inl.mean():.0%} background n={bg.sum()} median_err={bg_err:.1f}px{note}")
    print("Background error under ~1 px on overlapping pairs suggests a fixed camera centre (pan/zoom only).")


if __name__ == "__main__":
    main()
