# Environment

## Intel Mac pins (verified on macOS, Intel i5-8257U, 16 GB)

```bash
uv venv --python 3.11 .venv && source .venv/bin/activate
uv pip install "torch==2.2.2" "torchvision==0.17.2" "numpy<2"
git clone https://github.com/roboflow/sports.git
uv pip install -e ./sports ultralytics gdown pandas scipy "numba==0.60.0" "llvmlite==0.43.0"
```

- `torch==2.2.2` is the last release with Intel-Mac wheels; `numpy<2` is required with it.
- The newest `llvmlite` (pulled in by `umap-learn` → `numba`) has no Intel-Mac wheel and fails to build; pin `numba==0.60.0` and `llvmlite==0.43.0`.
- Current `transformers` needs PyTorch ≥ 2.5, so the SigLIP team classifier in `sports` does not run here. Kit-colour clustering replaces it.
- OpenVINO dropped macOS x86 in 2026.0; 2025.4 is the last Intel-Mac release.
- `easyocr` installs on this stack and may upgrade OpenCV to 4.11; that worked.
- Homebrew `ffmpeg` may lack `drawtext`; build contact sheets without text overlays.

Download the Roboflow models with `sports/examples/soccer/setup.sh` or the `gdown` lines inside it (player and ball models are about 130 MB each).

## Measured timings (same machine, CPU only)

| Step | Time |
|---|---|
| Player detector, `imgsz=1280` | 3.4 s/frame |
| Player detector, `imgsz=960` | 1.9 s/frame |
| Player detector, `imgsz=640` | 1.0 s/frame, misses distant players |
| Detection + BoT-SORT on 2 min at 5 fps | about 30 min |
| SIFT registration, 240 frames at 960 px | about 1 min |
| PnLCalib keypoint + line models | about 9 s/frame |
| Roboflow-style pitch keypoint model (YOLOv8x-pose, `imgsz=640`) | about 1.2 s/frame |
| Team split colour pass over 2 min of detections | about 2.5 min |
| EasyOCR jersey reads, 1840 torso crops | about 15 min |
| ffmpeg, one frame per 5 s from a 54-minute 1080p game | about 3 min |
| `build_panorama.py`, 645 frames (registration about 3 min, then bundle adjustment and median) | about 5 min |
| Differential-evolution field fit on the panorama (popsize 30, 250 generations) | about 11 min |

Run long stages in the background and check progress from their output files instead of blocking.
