# Environment

Measured on a 2019 Intel MacBook Pro (quad-core i5), Python 3.12.11.

## Install

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r scripts/requirements.txt
```

- Read FBX with [ufbx](https://github.com/ufbx/ufbx): a single C file, compiled with `cc -std=c99 -O2 -I ufbx export.c ufbx/ufbx.c -lm`. Pin the commit. macOS Quick Look could not open the Scaniverse FBX; that says nothing about the file.
- Texture relief needs [DeepBump](https://github.com/HugoTini/DeepBump) (GPL-3.0) and `onnxruntime`; it took about 9 minutes on CPU for an 8192 px texture. Clone it outside the skill, do not vendor it.
- Bambu Studio for slicing: `brew install --cask bambu-studio`.
- Free at least 8 GB of disk: a full slicer run with three models and their working files filled the disk once mid-run.

## Tests

```bash
cd scripts && ../.venv/bin/python -m pytest -q -p no:cacheprovider
```

About 10 minutes. The true-surface tests build real marching-cubes shapes and dominate the time. Tests never skip; leave out a file that does not apply rather than skipping inside it.

## Timings

From file timestamps of one full run on the owl:

| Step | 120 mm, 0.35 mm voxels | 210 mm, 0.4 mm voxels |
|---|---|---|
| Build with pull-back and rod trim | 30 min | 90 min |
| Build at 0.25 mm voxels instead | 56 min | not tried |
| Solid check, scan comparison, close-ups and turntable | 5 min | 14 min |
| One Bambu CLI slice and G-code checks | 5 min | 18 min |

Run long builds in the background and check them when they finish. Building, checking and slicing all three owl models took about 3 hours.
