# Prior art

Checked for amateur, small-sided, CPU-only use. Licence matters: unlicensed code can be studied but not copied.

| Project | Licence | Use it for | Do not expect |
|---|---|---|---|
| [roboflow/sports](https://github.com/roboflow/sports) | Code MIT; YOLO models AGPL | Player/ball detector, pitch drawing, radar | Pitch keypoints that fit small-sided fields; SigLIP on old PyTorch |
| [SoccerNet/sn-gamestate](https://github.com/SoccerNet/sn-gamestate) | GPL-3.0 | Ideas: confidence-weighted jersey vote per tracklet, team side from mean position, EasyOCR/MMOCR modules | CPU-friendly install (Python 3.9, torch 1.13, MMOCR); calibration that works on amateur fields |
| [mguti97/PnLCalib](https://github.com/mguti97/PnLCalib) | GPL-2.0 | Pro broadcast calibration | Lines on faint amateur markings |
| [NikolasEnt/soccernet-calibration-sportlight](https://github.com/NikolasEnt/soccernet-calibration-sportlight) | None | Ideas: line-line and line-conic intersections as extra points, voting over keypoints (2023 SoccerNet winner) | Pretrained models that fit amateur small-sided fields |
| [MM4SPA/tvcalib](https://github.com/MM4SPA/tvcalib) | MIT | Fitting a camera directly to line segments with a differentiable reprojection error | A line segmenter trained on anything but broadcast |
| [ericsujw/KpSFR](https://github.com/ericsujw/KpSFR) | MIT | Dense keypoint-grid registration idea | Weights beyond World Cup broadcast |
| [martinjolif/yolo-football-pitch-detection](https://huggingface.co/martinjolif/yolo-football-pitch-detection) | AGPL-3.0 | Roboflow 32-point pitch keypoints, runs on CPU through Ultralytics | Keypoints that stay put on a fixed amateur camera; it assumes midfield is centred |
| "Calibrating Cameras in Poor-Conditioned Pitch-Based Sports Games" (paper) | n/a | The key idea for sideline footage: stitch a panorama first, then find the field there | Code |
| [SoccerNet/sn-reid](https://github.com/SoccerNet/sn-reid) | MIT | Appearance re-identification to join track fragments | Modern PyTorch support out of the box |
| [AtomScott/SoccerTrack-v2](https://github.com/AtomScott/SoccerTrack-v2) | Code MIT; data CC BY 4.0 | Amateur panoramic dataset; TrackNet ball tracker and ball-action-spotting training kits | Released trained weights (none found); training needs gated data and a GPU |
| [rondo-labs/Tactix](https://github.com/rondo-labs/Tactix) | GPL-3.0 | Design reference: manual calibration plus optical-flow mode | Running on Intel Mac (needs `transformers>=5`, Python 3.12) |
| [duarteprazeres/falcon](https://github.com/duarteprazeres/falcon) | None | Design reference for Veo footage | Reusable code |
| [antoinekeller/soccer_tracker](https://github.com/antoinekeller/soccer_tracker) | None | Ideas: classical line detection, solve focal with pose, seed from previous frame, reject implausible poses | A detector that works when the near touchline is out of view |
| [AnshChoudhary/Football-Tracking](https://github.com/AnshChoudhary/Football-Tracking) | No licence file | Ideas: shirt colour via 2-colour KMeans with corner pixels as background; nearest-player possession; windowed speed | Calibration (four hard-coded pixels) or zooming-camera motion |

## Feature gaps no project filled

Spacing to nearest teammate, drift from an assigned role, recovery time to goal-side, and per-player identification on small-sided amateur footage all had to be written for the target player.
