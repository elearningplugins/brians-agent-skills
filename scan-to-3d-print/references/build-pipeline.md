# Build pipeline

Measured on a 1.63 m bronze owl in flight, scanned with Scaniverse (149,267 vertices, 273,067 faces, 623 components) and built at 120 and 210 mm tall for a 0.4 mm nozzle. The numbers are from that project; re-measure on a new scan.

## Stages and defaults

| Stage | Setting | Default | Why |
|---|---|---|---|
| Ground cut | `--ground-cut-m` | 0.02 m above the base's foot | Removes the flat ground skirt fused to the base |
| Rejoin | `--rejoin-labels` | explicit reviewed IDs | A distance rule would join debris too |
| Voxel size | `--voxel-mm` | 0.35 at 120 mm, 0.4 at 210 mm | Under a nozzle line; memory grows with the cube |
| Thickening | `--min-wall-mm` | 1.6 (1.2 tried) | Every scanned sheet becomes a wall this thick |
| Hole closing | `--close-scan-mm` | 8.5 mm on the real object | Sized on the object, not the print, so scale does not change what is closed |
| Cavity seal | `--seal-scan-mm` | 30 mm on the real object | Used only to find and fill a body cavity, not as closing |
| Base cap | `--cap-band-scan-mm` | 20 mm band | Two voxels thick; one was erased by smoothing |
| Printable minimum | `--min-print-mm` | 1.2 (0.8 tried) | Three or two 0.4 mm lines |
| Pull margin | `--pull-margin-mm` | 0.2 | The pull leaves walls this much over the minimum |
| Bed fade | `--bed-fade-mm` | 2.0 | First layer stays flat |
| Hold ramp | `--hold-ramp-mm` | 3.0 | Pull fades in near held regions instead of stepping |
| Smoothing | `--smooth-passes` | 5 Taubin passes | After the pull, before relief |
| Stage budgets | guard, folds, thin | 5%, 15%, 10% | Build stops if a safety stage cancels more |

## Solidify

1. Sample the scan densely (keep each sample's UV if relief will be added).
2. Mark voxels within half the minimum wall of a sample, close holes with a structuring element sized on the real object, fill the interior, cap the base, and run marching cubes. Pad the grid first: heavy closing eroded the bottom of an unpadded grid and left the base an open cup.
3. Fill gaps between the base cap and the body above column by column; a thin unfilled pocket above the cap survived otherwise.
4. Keep only the largest body, check that the volume is positive, and rebuild the mesh from scratch after fixing normals.
5. Log the area of output surface farther than 1.5 × the minimum wall from the scan. At 120 mm it was only the base cap; at 240 mm it showed about 1,050 mm² of patches sealing holes under the wings, which is the honest cost of sealing.

## Pull back to the true surface (`true_surface.pull_back`)

Each vertex of the thickened solid sits about half the wall plus half a voxel outside the scan.

1. Measure each vertex's depth to the nearest scan sample along a normal smoothed over 8 Laplacian passes; fall back to the nominal offset where the nearest sample lies off to the side.
2. Each side of a wall may give up half of whatever the wall has beyond the printable minimum plus the margin, so thin features return toward their scanned size without going under the minimum.
3. Fade the pull out near the bed, and near held vertices over `hold_ramp_mm`.
4. Guard: walls the pull would thin are left alone. The guard's margin must be the pull's own margin; given the full offset it blocked every wall under 3.35 mm, 61% of the vertices.
5. Fold loop: move, relax with a few Taubin passes, check for flipped or crossing faces, cut the pull around each one with a ramp, repeat. Relaxing inside the loop is what stopped thin round parts (branches, talons) crumpling when shrunk; folds fell from 27% of vertices to under 1%.
6. Thin rounds: measure walls after the move; where a wall ended under the minimum because both sides read it obliquely, halve the pull nearest it, searching up to six rings outward for lips that are thin because of their neighbours.
7. Report per stage the share of wanting vertices that lost pull, and masks of where.

Rejected, in order, each measured: voxel erosion with a thin-sheet residue (lumpy); neighbourhood-thickness erosion (too thin); voxel minimum-wall restore (lumpy); mesh pull without fold control (folded in creases); cancelling the pull outright around folds with a 0.7 mm taper (309 bumps); a 2.5 mm ramp (97 bumps but the face moved 0.66 mm off the scan); relaxing only around folds (shaved box edges and thinned walls).

## Hold regions

Some scanned surfaces are invented by the scanner, such as flat plates with thin flaps folded over the tops of wings it could not see. Pulling those in gains no accuracy and thins them, so they are held at full thickness. A hold that ends at a line leaves a step as tall as the pull; it showed as a 1.5× roughness failure along a straight seam. Fade the pull in over a few millimetres from held vertices.

## Mirroring a missing part

1. Mirror the scan across X and register the mirrored lower body onto the original to find the symmetry plane (2 cm median fit on the real object).
2. Take the mirrored part beyond the scanned stub's end and shift it linearly from root to tip so it meets the stub (1.5 cm median) and any loose tip piece (1.8 cm).
3. Drop mirrored faces within 8 mm of scanned surface so the two do not stack into a ridge; thickening joins the small gap.
4. Check against a photo: on the owl the wing's outline overlap with a photo rose from 0.30 to 0.50 intersection over union. A convex-hull bridge, tried first, printed as a stick ending in a knob.

## Cutting gaps the scan bridged

A wing's outer primary feathers scanned as one sheet with faint grooves between them.

1. Fit the part's plane by SVD of its points and fix the axis signs to a known orientation (SVD signs are arbitrary).
2. Find the grooves as darkness peaks along rays from the wrist in a face-on render.
3. Cut a six-corner wedge per groove from part way along it to past the edge, through the sheet, from the voxel solid after hole sealing. Map the wedges through the mirror for the mirrored side.
4. Hold the cut walls during the pull: they have no scan to pull toward, and their sharp edges fold under a normal-direction pull.
5. Remove scan samples inside the gaps so the pull does not aim for the bridged sheet, and report the bridged sheet and the gap walls apart in the comparison.

An earlier attempt to rebuild wing tops from one photo (homography to a rectangle, DeepBump height, refit surfaces, cut fingers) was rejected by the owner: the fingers looked like a comb cut into a square end.

## Texture relief

DeepBump turns the scan's texture into normals; integrate them to height in tiles (Frankot-Chellappa), high-pass at about 60 texels, and displace along vertex normals by the height at each vertex's UV. Shadows baked into the texture survive the high-pass. Feather scallop outlines were about 2 mm wide on the real object, 0.35 mm at 17% scale, under a nozzle line. DeepBump is GPL-3.0: clone it beside the project, do not vendor it.
