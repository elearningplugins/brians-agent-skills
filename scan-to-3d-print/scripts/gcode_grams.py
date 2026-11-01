"""Sums filament extruded per G-code feature, using the density and diameter the G-code was sliced with, and checks the sum against the header total."""
import json
import re
import sys

from gcode_paths import config_value

path = sys.argv[1]
density = float(config_value(path, "filament_density").split(",")[0])
diameter = float(config_value(path, "filament_diameter").split(",")[0])
area = 3.14159265 * (diameter / 2) ** 2
grams = {}
feature = None
header = {}
for line in open(path):
    if line.startswith("; FEATURE: "):
        feature = line[11:].strip()
    elif line.startswith("; total estimated time") or line.startswith("; model printing time"):
        header["time"] = line.split("total estimated time:")[-1].strip()
    elif line.startswith("; total filament weight"):
        header["filament_g"] = line.split(":")[-1].strip()
    # Moves with E but no XY are unretracts, which only refill what a retract pulled back
    elif line.startswith(("G1 ", "G2 ", "G3 ")) and " E" in line and (" X" in line or " Y" in line):
        m = re.search(r" E(-?[\d.]+)", line.split(";")[0])
        if m and float(m.group(1)) > 0:
            grams[feature] = grams.get(feature, 0) + float(m.group(1)) * area / 1000 * density
sup = sum(v for k, v in grams.items() if k and k.startswith("Support"))
total = sum(grams.values())
print(json.dumps({**header, "support_g": round(sup, 1), "interface_g": round(grams.get("Support interface", 0), 1), "model_g": round(sum(v for k, v in grams.items() if k and not k.startswith("Support") and k not in ("Prime tower", "Brim", "Custom")), 1), "summed_g": round(total, 2), "header_residual_g": round(float(header.get("filament_g", "nan")) - total, 2), "density_g_cm3": density}))
