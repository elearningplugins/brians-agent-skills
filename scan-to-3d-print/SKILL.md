---
name: scan-to-3d-print
description: >-
  Turns a phone 3D scan (Scaniverse, Polycam, KIRI or any textured mesh) of a
  sculpture or object into a faithful, printable FDM model, verified against
  the scan, reference photos and the sliced G-code. Use when the user wants to
  3D print something they scanned, asks why a printed scan looks noisy, lumpy,
  fat or wrong, wants a scan made watertight, scaled to a printer, compared
  with photos, or sliced with Bambu Studio and checked before printing.
---

# Scan to 3D print

The goal is a print that looks like the original, not just a mesh that slices. A phone scan is a noisy, open, fragmented sheet with invented patches, and every step that makes it printable (cropping, thickening, smoothing, supports) also moves it away from the original. So each step is measured against the scan, and the finished print against the photos and the G-code. Do not call a model printable or faithful until the checks below say so with numbers.

## Workflow

```
- [ ] 1. Preserve the sources and audit the scan
- [ ] 2. Ask the owner for the facts the scan cannot give
- [ ] 3. Segment: separate the object from ground and debris, and keep detached real parts
- [ ] 4. Choose the scale from the printer's bed
- [ ] 5. Build a watertight solid
- [ ] 6. Pull the thickened solid back onto the scanned surface
- [ ] 7. Restore what the scan missed or bridged, and label it invented
- [ ] 8. Smooth, add relief only if it survives the checks, guard thin walls
- [ ] 9. Check the solid: walls, crossings, islands, support
- [ ] 10. Compare with the scan from every side and with the photos
- [ ] 11. Slice, and check the G-code itself
- [ ] 12. Show the user, and keep every gate in the build
```

### 1. Preserve and audit

- Treat the original scan and photos as read-only. Checksum them and work on derived files only.
- Parse the file with a real importer ([ufbx](https://github.com/ufbx/ufbx) reads FBX without Blender) and record units, axes, vertex and face counts, and connected components. Scaniverse FBX is metres, +Y up, +Z toward the camera.
- **The raw bounding box is not the object's size.** Scans include sparse ground and background. Crop, then measure.
- Photograph the subject from every side, plus close-ups of the face or fine parts, with even light. The photos are the judge of the print, not a source of geometry.

### 2. Ask the owner

Ask for one physical measurement (height, span or base width) to confirm the scan's scale, and for the printer, installed nozzle, build plate, filament, AMS, indoor or outdoor use, finish, and whether splitting into parts is acceptable. Record anything unconfirmed as provisional.

### 3. Segment

- Merge duplicate vertices first; 623 audited components became 6.
- Cut the ground a little above where it meets the object, then keep the largest connected piece. Ground patches just above the cut survive as loose flakes, and one printed as a bead on the bed.
- **Do not discard a detached piece because it is detached.** A "floating arc" above one wing was the wing tip, cut off by a 17 cm strip the scanner missed; dropping it made the wing a third short. Check each loose piece against the photos and keep reviewed ones by explicit ID, never by a distance threshold alone.

### 4. Scale

Scale by the dimension that hits the bed limit, after the crop and any restored parts. Keep some clearance from the nominal build volume. Note the cost: a 210 mm owl sliced to 13 h 52 min and 277 g, a 120 mm one to 3 h 41 min and 63 g.

### 5. Build a watertight solid

Voxelize at print scale (0.35 mm for a 0.4 mm nozzle), thicken every scanned sheet to a minimum wall, close holes, fill the interior, cap the base, and run marching cubes. Details and measured failures are in [references/build-pipeline.md](references/build-pipeline.md). The ones that shipped before a check caught them:

- A 2–3 cm scan hole opened the body cavity and the fill leaked through it, leaving a hollow body. Size hole closing on the real object, and seal cavities separately so gaps between branches are not webbed over.
- After `fix_normals()`, trimesh's cached vertex normals pointed inward on two thirds of the vertices. Rebuild the mesh from scratch after fixing normals and check the volume's sign.
- Keep only the largest body after marching cubes; slivers flipped the whole model's normals.

### 6. Pull back to the true surface

Thickening moves every surface about 1 mm outward, about 12 mm on a 1.6 m sculpture. Pull each vertex back by its own measured depth to the scan along a smoothed normal, as far as the wall can spare. [scripts/true_surface.py](scripts/true_surface.py) does this with Taubin relaxing against folds, a measured give-back where the pull thinned a wall, and a faded hold for regions that must not move. It reports what each safety stage cancelled; **make the build stop when a stage cancels more than its budget** (guard 5%, folds 15%, thin 10%). A wall guard that silently blocked 61% of the pull is what made one print look noisy: a patchwork of pulled and unpulled surface.

### 7. Restore and label invented geometry

- Fill a missing symmetric part with its mirror: register the mirrored body onto itself to find the symmetry plane, then blend the mirrored part into the scanned stub and the loose tip.
- Cut gaps the scanner bridged (separate feathers, fingers) where the scan kept grooves, as wedges in the part's best-fit plane, after hole sealing so sealing cannot bridge them again. Start them part way out and taper each finger's end: straight wedges left square-ended feathers that a photo from below showed were pointed.
- Report invented material apart from scanned material in every comparison, so it cannot flatter the accuracy figures. Show the owner a preview before making it the default.
- Generative image-to-3D tools invent plausible detail; they were evaluated and rejected. A close-up rescan is the honest fix for detail the scan lacks.

### 8. Smooth, relief, wall guard

Taubin smoothing (not Laplacian) removes vertex-scale spikes without shrinking the solid. Texture-derived relief (DeepBump height from the scan's texture) can add feather and fabric texture, but at small scale its finest detail is below a nozzle line and reads as noise: 0.35 mm of relief on a 120 mm print measured 1.6–2× the scan's roughness and failed; the same relief scaled to 210 mm passed at 1.05×. Guard walls so relief never thins one below the printable minimum.

**Thin features are the main detail trade-off.** The printable minimum pads every claw, twig and ear tuft. At 1.2 mm (three 0.4 mm lines) talons printed as blunt sausages; at 0.8 mm the scan surface within 1 mm of the print rose from 93.9% to 99.4% and claws, twigs and blades matched the scan, at the cost of 19% of the surface being 0.8–1.2 mm thick. Show the owner both and let them choose strength or detail.

Claws stay blunter than the photos even at 0.8 mm. What was tried, measured on the legs of the 120 mm owl:

- **Diagnose the direction first.** Every leg spot more than 0.3 mm off the scan was scan lying *inside* the print: the claws were too fat, not too short. That rules out fixes that add resolution.
- **A lower minimum on rods** (`rod_floor` in [scripts/true_surface.py](scripts/true_surface.py), 0.45 mm on claws and twigs, found by a PCA spread test plus normals facing round the axis so sheet rims keep the full minimum) cut the fat surface by only 6%: the pull-back cannot take the thickening off a rounded tip without folding it.
- **Finer voxels** (0.25 mm against 0.35 mm) cut it by 2.5% for twice the build time. Not worth it.
- **Trimming the thickening off rods in the voxels** ([scripts/rod_shell.py](scripts/rod_shell.py): keep only voxels within one voxel of the scan or inside it, sealing scan holes first so a holed claw is not left hollow) cut it by 9% and raised the thinnest wall from 0.38 to 0.47 mm. It costs talon roughness (1.01× to 1.18× the scan) and needs exclusions: the base's ragged bottom rim reads as rods, and trimming it roughened the base and took support islands from 23 to 54; feather tips on held wing tops went to 0.48 mm. Keep the bed band and every held region out of the trim.
- Claw tips under a nozzle line print only with Arachne walls (step 11). The honest limit is the scan: a close-up rescan of the feet would do more than any of these.

### 9. Check the solid

Run [scripts/check_print.py](scripts/check_print.py) on every build (see [references/checks.md](references/checks.md)): wall thickness from a cone of inward rays, exact self-intersection, overhangs past the support angle, and islands (cross-sections that start in mid-air). The build itself must fail on crossings, a non-watertight result, or a stage over budget, not just log them.

### 10. Compare with the scan and the photos

- Measure distance both ways: print to scan (material added) and scan to print (detail lost), by region. A one-way number hides one kind of error.
- Compare roughness by region against the scan's own (99th percentile of how far each vertex stands off the mean of its neighbours, along its normal) and fail above 1.5×. This catches voxel steps, pull patchworks and seams that distance medians average away.
- Render fixed close-ups and a 24-view turntable of print beside scan, and heat maps of both distances ([scripts/compare_views.py](scripts/compare_views.py)). Look at them: a dent in an ear tuft's tip showed only in a render, and the roughness check's failure was traced to a hard seam only by marking the roughest vertices on one.
- Put each photo beside the print and scan from the same camera. Pick cameras by hand: automatic silhouette registration of 16 phone photos was multimodal and unreliable. When the print matches the scan but not the photo, the scan is the limit; say so instead of inventing detail.

### 11. Slice and check the G-code

[scripts/slice.sh](scripts/slice.sh) slices with the Bambu Studio CLI, then reads the G-code back. See [references/slicing.md](references/slicing.md).

- **The plate the G-code names** matches the plate installed.
- **Grams:** the summed extrusion matches Bambu's header within 0.5 g, which proves the reader sees every move.
- **Coverage:** model surface with no extrusion within a line width is under 1%, which catches placement errors and dropped thin features.
- **Islands:** every island from step 9 has support or model under it in the G-code. Bambu's default "remove small overhangs" left a 0.2 mm² feather tip in mid-air; the script supports small overhangs and fails on any unsupported island.

Run [scripts/monte_carlo.py](scripts/monte_carlo.py) to compare settings on the actual model. On the owl, Arachne walls plus lightning infill at 10% saved 10% time and 12% filament and cut dropped thin detail from 0.071% to 0.003%. `slice.sh` now uses Arachne walls by default; they also saved 12–32 min and 2–4 g per model over classic walls at a 0.8 mm minimum.

### 12. Show the user and keep the gates

- Open the sliced 3MF in Bambu Studio and confirm the app actually started: `open -a` returned success once while nothing launched.
- Every bug in this skill was found because a user saw something a check did not catch. When that happens, fix it, then add the check that would have caught it and wire it into the build or slice so it fails.
- Keep one script that rebuilds everything from the committed scan, and test it from a fresh clone. Generated files are not committed, so the clone is the only proof the result can be reproduced: the owl's first fresh-clone run found that nothing extracted the scan's texture from the FBX. Name the recommended print and the slicer version beside it.
- Try a geometry change on one model in a scratch folder first, then rerun every check and compare each number with the last build, not just the one the change targets. The claw trim improved the claws and quietly broke the base; only the roughness and island counts showed it.

## Honesty rules

- State provisional facts (scale, invented parts) as provisional in every report.
- Report time, grams and support from the sliced G-code, never from estimates.
- Report what each check measures and its limit; never say "looks good" without the numbers behind it.
- Respect the rights in the original: keep scans and photos of someone else's sculpture private unless the owner has confirmed permission.

## Additional resources

- [references/build-pipeline.md](references/build-pipeline.md): every build stage, its parameters, and the approaches tried and rejected
- [references/checks.md](references/checks.md): what each check measures, its thresholds, and the bugs it caught
- [references/slicing.md](references/slicing.md): Bambu Studio CLI, G-code reading, the settings study and results
- [references/environment.md](references/environment.md): install, tests, and timings
- [scripts/printcheck.py](scripts/printcheck.py), [scripts/check_print.py](scripts/check_print.py): wall thickness, crossings, support, islands, roughness, wall guard
- [scripts/true_surface.py](scripts/true_surface.py): pull-back onto the scan, fold-safe Taubin smoothing, and the lower printable minimum on rods
- [scripts/rod_shell.py](scripts/rod_shell.py): trims the thickening off claws and twigs in the voxel solid
- [scripts/compare_views.py](scripts/compare_views.py): print, scan and photo side by side, plain or as distance heat maps
- [scripts/slice.sh](scripts/slice.sh) and the G-code readers it calls: `gcode_paths.py`, `gcode_grams.py`, `coverage.py`, `islands_supported.py`, `count_supports.py`, `plot_supports.py`, `flatten_profile.py`, `monte_carlo.py`
