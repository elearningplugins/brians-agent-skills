# Field template and calibration

## 9v9 (U11–U12) markings, U.S. Soccer small-sided standard

Source: U.S. Soccer Player Development Initiatives, 9v9 Standards of Play, and US Youth Soccer Small-Sided Games Manual.

| Marking | Size |
|---|---|
| Field | 70–80 yd long × 45–55 yd wide |
| Penalty area | 14 yd deep × 36 yd wide |
| Goal area | 5 yd deep × 16 yd wide |
| Penalty mark | 10 yd from the goal line |
| Centre circle and penalty arc radius | 8 yd |
| Goal | 6.5 × 18.5 ft recommended, 7 × 21 ft maximum |
| Match length | 2 × 30 minutes |

Fields vary, and shared turf can carry lines for other formats. Fit length and width as parameters within the range rather than fixing them. Check the local league's rules of competition: they usually confirm the field range, circle radius, penalty spot, goal size, half length and halftime, and where substitutions happen.

## What was tried on fixed-pole virtual-camera footage (Trace, U11, 54-minute game)

| Attempt | Result |
|---|---|
| PnLCalib/NBJW pretrained (SoccerNet) | 0 lines on 6 frames; keypoints in empty grass |
| Assume a drone and calibrate per frame | Wrong premise; `camera_check.py` showed a fixed camera centre |
| Background SIFT registration, chained at 2 fps | 240 frames, one segment, median 883 inliers; chained vs direct 0.7–3.3 px over 10–60 s at 960 px width |
| Unbounded 9-parameter chamfer fit to all line pixels | Fitted the far touchline to the spectator row; refinement escaped bounds (width 64 yd) |
| Vanishing points from all segments | Cross-field family drowned by clutter; second point inconsistent with the horizon |
| Long segments from 115 frames, spectator band removed, bounded pose, differential evolution | Wrong: 45° tilt and 3766 px focal; overlay missed every line |
| Roboflow-style 32-point pitch keypoints across the game, kept only if they land on the same panorama spot | No vertex was consistent; midfield points spread over ~100° of pan because the model assumes each view is centred on midfield |
| Spherical panorama from 645 frames (one per 5 s), bundle-adjusted rotation + zoom | Works: 560 frames, 1637 links, median error 2.93 → 0.91 px, 90th percentile 24.18 → 5.32 px; players vanish in the median |
| Line-pixel chamfer on the panorama, differential evolution (four variants) | Wrong every time: halfway line and near touchlines fit, depth does not |
| Ten features read off the panorama by eye, least squares (diagnostic) | All within ~0.2–0.5°: camera ~3 yd behind the near touchline, ~3 yd high, field ~73 × 49 yd |

## Why whole-panorama chamfer fails

- The far touchline is faint, and spectators sit several yards behind it; assuming it sits just below them pulled the field upward.
- Excluding the spectator band let the fit hide 80% of the template there at no cost; score those points as unexplained.
- Even then the cost barely separates poses (correct 5.40 vs. wrong 5.47–5.58), and a local refine from the correct pose drifted away.
- Detected line pixels are dominated by the halfway line and clutter near the camera, so "pixels explained" also favoured a wrong pose.

Fit to the halfway line, goal frames, centre circle and near touchlines instead, then refine with a chamfer term only near them.

## Line detection notes

- White top-hat (kernel about 25 px at 960 px width) on `V − 0.5·S`, with lower saturation than the local neighbourhood, restricted to the largest grass component.
- Remove detected player boxes (with padding) before segment detection.
- Halfway line, near touchline, and penalty-box fronts are detected reliably; the far touchline is often too faint.
- Weight evidence by segment length in the original frame, not in the stitched reference view; reference-view lengths explode near the edges of the camera's sweep.

On the median panorama, use a smaller top-hat (about 15 px at half scale) and a lower threshold; the median is smooth, so faint markings such as penalty boxes and goal frames appear. Grass-texture grain near the camera appears too.

To find the spectator row, do not use the HSV grass mask: it includes trees. Learn the pitch's own colour (Lab mean and covariance from the middle of the panorama), scan each column upward from mid-field until the colour stops, then median-filter across columns.

## Validation

Render the fitted template over the panorama and over at least six frames spread across the sweep. Accept the calibration only when the halfway line, a goal or penalty box and a touchline line up in several of them.
