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

Fields vary, and shared turf can carry lines for other formats. Fit length and width as parameters within the range rather than fixing them.

## What was tried on fixed-pole virtual-camera footage (Trace, U11)

| Attempt | Result |
|---|---|
| PnLCalib/NBJW pretrained (SoccerNet) | 0 lines on 6 frames; keypoints in empty grass |
| Assume a drone and calibrate per frame | Wrong premise; `camera_check.py` showed a fixed camera centre |
| Background SIFT registration, chained at 2 fps | 240 frames, one segment, median 883 inliers; chained vs direct 0.7–3.3 px over 10–60 s at 960 px width |
| Unbounded 9-parameter chamfer fit to all line pixels | Fitted the far touchline to the spectator row; refinement escaped bounds (width 64 yd) |
| Vanishing points from all segments | Cross-field family drowned by clutter; second point inconsistent with the horizon |
| Long segments only, spectator band removed, bounded pose with pole prior | Pending validation by overlay |

## Line detection notes

- White top-hat (kernel about 25 px at 960 px width) on `V − 0.5·S`, with lower saturation than the local neighbourhood, restricted to the largest grass component.
- Remove detected player boxes (with padding) before segment detection.
- Halfway line, near touchline, and penalty-box fronts are detected reliably; the far touchline is often too faint.
- Weight evidence by segment length in the original frame, not in the stitched reference view; reference-view lengths explode near the edges of the camera's sweep.

## Validation

Render the fitted template over at least six frames spread across the sweep. Accept the calibration only when the halfway line, a penalty box and a touchline line up in several of them.
