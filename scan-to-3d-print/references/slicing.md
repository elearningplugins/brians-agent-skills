# Slicing with Bambu Studio and reading the G-code

Tested with Bambu Studio 2.08.02.61 on macOS (`brew install --cask bambu-studio`).

## Command line

```bash
PY=.venv/bin/python OUT=slices CHECKS=checks scripts/slice.sh model.stl
EXTRA="sparse_infill_pattern=lightning sparse_infill_density=10%" PY=.venv/bin/python scripts/slice.sh model.stl
EXTRA="wall_generator=classic" PY=.venv/bin/python scripts/slice.sh model.stl
```

- `flatten_profile.py` merges a system profile's `inherits` chain from `/Applications/BambuStudio.app/Contents/Resources/profiles/BBL` into one JSON and applies `key=value` overrides; the CLI does not resolve inheritance itself.
- The CLI is `BambuStudio --orient 0 --arrange 1 --load-settings "machine.json;process.json" --load-filaments filament.json --slice 0 --export-3mf name.3mf --outputdir dir model.stl`. The 3MF opens in the app and can be sent to the printer.
- Arranging can rotate the model. Read the placement back from the 3MF (`gcode_paths.plate_transform`) rather than assuming it.
- A support-material interface filament (AMS) could not be set from the CLI with a bare STL; set it up in the app.

## Reading the G-code

- Moves without X or Y are unretracts, not extrusion. Counting them inflated support contact pads from about 25 to 57–149.
- Follow G2/G3 arcs along the circle. Reading them as chords misplaced paths.
- The P1S writes paths offset by `extruder_offset` (0, 2) from the 3MF plate coordinates; apply it when comparing G-code with the model.
- Grams from summed extrusion, using the G-code's own filament diameter and density, matched Bambu's header within 0.05 g once the above were fixed. Keep the comparison as a gate.

## Settings study (`monte_carlo.py`)

Slice the actual model with random settings and score each G-code for time, filament, layer-step height, lost detail (surface with no extrusion within a line width), support scarring, unsupported overhang and unsupported islands. Speeds and temperatures stay at profile values; their effect is not measurable from geometry. Three identical baseline slices gave identical results, so differences are the settings.

On the 120 mm owl:

| Profile | Time | Filament | Lost detail | Unsupported islands |
|---|---|---|---|---|
| 0.20 mm Standard, classic walls, grid 15% | 4 h 16 min | 66.5 g | 0.071% | 0 |
| Arachne walls | 4 h 00 min | 65.1 g | 0.003% | 0 |
| Arachne + lightning 10% | 3 h 51 min | 58.8 g | 0.003% | 0 |
| ...and 0.24 mm layers | 3 h 23 min | 58.8 g | 0.005% | 5 |
| ...and 0.16 mm layers | 4 h 40 min | 60.3 g | 0.005% | 2 |

- Arachne varies line width, so thin features (claw tips, feather edges) print instead of being dropped. Every random sample with Arachne at 0.20 mm had 0.003% lost detail.
- A 25° support threshold saved 19 more minutes but left 28% more unsupported overhang.
- Top shells and support top gap made no difference on an organic model with almost no flat tops.

## Supports

- Tree(auto) supports on the owl used 19 g and 56 contact pads against 72 g and 287 for normal supports.
- Tilting the model 10–30° either added support or left nothing flat on the bed; print organic models with a base upright.
- Turn off "Remove small overhangs" (`support_remove_small_overhang=0`). It cost 40 min and 11 g at 120 mm and 2 h 25 min and 48 g at 210 mm, and left no island unsupported.
- For a single spot, painting a support enforcer in the app costs far less than the global setting.

## Results on the owl, small overhangs supported

| Model | Size (mm) | Time | Filament | Support | Islands supported |
|---|---|---|---|---|---|
| 120 mm, smooth | 140 × 77 × 120 | 4 h 05 min | 69.6 g | 33.7 g | 31 of 31 |
| 120 mm, 0.8 mm printable minimum | 140 × 77 × 120 | 3 h 51 min | 64.2 g | 32.1 g | 23 of 23 |
| 120 mm, 0.8 mm, Arachne, tapered feathers, trimmed claws | 138 × 76 × 120 | 3 h 41 min | 63.0 g | 31.7 g | 25 of 25 |
| 210 mm, same | 242 × 133 × 209 | 13 h 52 min | 277.0 g | 151.4 g | 63 of 63 |
| 210 mm, texture relief | 244 × 134 × 210 | 14 h 31 min | 287.8 g | 150.5 g | 65 of 65 |
