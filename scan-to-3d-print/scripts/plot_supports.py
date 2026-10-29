"""Plots model and support extrusion from a Bambu G-code file in front, side and top views."""
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from gcode_paths import read_paths  # noqa: E402

paths = read_paths(sys.argv[1], 0.5)
pts = {"model": paths["model"][:, [0, 1, 3]], "support": np.concatenate([paths["support"], paths["interface"]])[:, [0, 1, 3]]}
fig, axes = plt.subplots(1, 3, figsize=(21, 7.5), dpi=110)
for ax, (i, j, title) in zip(axes, [(0, 2, "front (X-Z)"), (1, 2, "side (Y-Z)"), (0, 1, "top (X-Y)")]):
    for key, color, size in (("model", "#9a9a9a", 0.15), ("support", "#e4572e", 0.3)):
        p = np.array(pts[key])
        p = p[np.random.default_rng(0).choice(len(p), min(len(p), 250_000), replace=False)]
        ax.scatter(p[:, i], p[:, j], s=size, c=color, linewidths=0, label=key)
    ax.set_aspect("equal")
    ax.set_title(title)
axes[0].legend(markerscale=30, loc="upper left")
fig.suptitle(sys.argv[3])
plt.tight_layout()
plt.savefig(sys.argv[2])
print("wrote", sys.argv[2])
