# Checks

Each check exists because a defect shipped without it. Wire every one into the build or slice so it fails; a logged warning nobody reads is not a check.

## On the solid (`check_print.py`, `printcheck.py`)

| Check | How | Threshold | Caught |
|---|---|---|---|
| Wall thickness | A cone of seven inward rays per vertex (normal plus six at 20°), shortest exit through the far wall, hits within two rings skipped, median over neighbours | Fail under 2 nozzle widths, warn under 3, "slender" under 2.5 mm | Relief thinning 240 mm wing tips to 0.4 mm |
| Hit face | A ray's hit face is reported only if that ray's length is within 1.5 × the median thickness + 0.1 mm | | A guard blocking faces far from the thin wall at corners |
| Self-intersection | Every edge tested exactly, in double precision, against nearby faces | Zero crossings | 19–160 crossings per build that a ray-based test missed by grazing edges |
| Overhang | Down-facing faces flatter than the support angle (30°) | Reported | |
| Islands | Slice at layer height; a cross-section with nothing under it in the previous layer | Each must be supported in the G-code | A finder that skipped empty layers, found by Hypothesis |
| Roughness | How far each vertex stands off the mean of its neighbours along its normal, 99th percentile per region | Print ÷ scan ≤ 1.5 | Pull patchworks (4–8×), a hold seam (1.59×), relief too fine for the scale (1.6–2×) |

Test with shapes whose answers are known: a slab of any thickness at any rotation, scale and position reads as that thickness; a block floating anywhere is exactly one island; a clean box has no crossings; the wall guard is idempotent and never leaves a wall under the minimum. Hypothesis property tests found a real bug the examples missed. A hand mutation pass planting nine bugs was caught by all.

## Against the scan (`compare_to_scan` in the project)

Record the exact scan-to-print transform in the build's JSON, so the check uses the same mapping as the build.

- **Print to scan:** distance from each printed sample to the scan; material added.
- **Scan to print:** distance from each scanned sample to the print; detail lost.
- By region, with medians, 95th percentiles and the share over 1 mm.
- Invented material reported apart: bridges, the mirrored part (measured against the mirrored surface it came from), and gap walls (within 1 mm of a cut, measured against scan or mirror, whichever is nearer). The bridged sheet inside a gap is reported apart from lost detail.
- Stage budgets from the pull-back are the build's own check: a stage that cancels more than its share stops the build.

On the owl at 120 mm after the fixes, scan to print had a 0.21 mm median, 93.9% within 1 mm at a 1.2 mm minimum and 99.4% at 0.8 mm. The wings sat about 1 mm off by design (held invented flaps, thickened single sheets).

## Visual checks

- **Close-ups:** fixed spots (face, feet, base, back, part joins, invented parts), print beside scan at the same camera and scale as a slicer preview.
- **Turntable:** 8 azimuths × 3 elevations. Mark print-only outline red and scan-only blue; outline differences show missing or added parts at a glance.
- **Heat maps:** print coloured by distance to scan, scan coloured by distance to print, 0 blue to 1 mm red. Read the scan side for lost detail: on the owl it showed claws and twig tips lost to the printable minimum.
- **Photos:** each photo beside print and scan from a hand-picked camera. Automatic registration from silhouettes was multimodal (IoU 0.56–0.62 for very different poses); landmark picking mistook a tail for a wing tip.

## In the G-code (`slice.sh` and readers)

| Check | Threshold | Caught |
|---|---|---|
| Plate type in the G-code | Equals the installed plate | |
| Summed extrusion vs Bambu's header | Within 0.5 g | Unretract moves read as extrusion (support contact pads counted 57–149 instead of about 25) |
| Surface with no extrusion within a line width | Under 1% | A 2 mm placement error: P1S `extruder_offset` (0, 2) and arcs read as chords |
| Islands supported | All | A 0.2 mm² feather tip left in mid-air by "remove small overhangs" |
| Support structures, contact pads, tallest support | Reported | Support scarring and removal effort |
