#!/usr/bin/env bash
# Slices each STL with Bambu Studio's command line, then checks and summarizes time, grams, coverage, supports and islands: PY=.venv/bin/python ./slice.sh model.stl [more.stl ...]
set -euo pipefail
SCRIPTS="$(cd "$(dirname "$0")" && pwd)"
BAMBU=${BAMBU:-/Applications/BambuStudio.app/Contents/MacOS/BambuStudio}
PY=${PY:-python3}
OUT=${OUT:-slices}
# Profile names exactly as Bambu Studio lists them; PLATE must name the plate actually installed (Cool Plate, Engineering Plate, High Temp Plate, Textured PEI Plate)
MACHINE=${MACHINE:-Bambu Lab P1S 0.4 nozzle}
PROCESS=${PROCESS:-0.20mm Standard @BBL X1C}
FILAMENT=${FILAMENT:-Bambu PLA Basic @BBL P1S 0.4 nozzle}
PLATE=${PLATE:-Textured PEI Plate}
# Extra process settings as key=value words, applied last, for example "sparse_infill_pattern=lightning sparse_infill_density=10%"
EXTRA=${EXTRA:-}
# Directory holding <name>-check.json from check_print.py for each STL
CHECKS=${CHECKS:-checks}
[ $# -gt 0 ] || { echo "usage: PY=<python> $0 model.stl [more.stl ...]"; exit 2; }
mkdir -p "$OUT/profiles"
python3 "$SCRIPTS/flatten_profile.py" machine "$MACHINE" "$OUT/profiles/machine.json"
# Bambu skips support under overhangs it judges small; on a scanned sculpture that left a 0.2 mm2 feather tip starting in mid-air, so small overhangs are supported
# Arachne walls vary line width, so claw and twig tips tapered to about one 0.4 mm line print instead of being dropped; EXTRA=wall_generator=classic turns them off
# shellcheck disable=SC2086
python3 "$SCRIPTS/flatten_profile.py" process "$PROCESS" "$OUT/profiles/process.json" enable_support=1 support_remove_small_overhang=0 wall_generator=arachne "curr_bed_type=$PLATE" $EXTRA
python3 "$SCRIPTS/flatten_profile.py" filament "$FILAMENT" "$OUT/profiles/filament.json"
for stl in "$@"; do
  name=$(basename "$stl" .stl)
  work="$OUT/$name"
  rm -rf "${work:?}" && mkdir -p "$work"
  "$BAMBU" --debug 1 --orient 0 --arrange 1 --load-settings "$OUT/profiles/machine.json;$OUT/profiles/process.json" --load-filaments "$OUT/profiles/filament.json" --slice 0 --export-3mf "$name.3mf" --outputdir "$(cd "$work" && pwd)" "$stl" > "$work/cli.log" 2>&1
  gcode="$work/plate_1.gcode"
  [ -s "$gcode" ] || { echo "$name: Bambu Studio wrote no G-code; see $work/cli.log"; exit 1; }
  plate=$(grep -m1 "^; curr_bed_type = " "$gcode" | cut -d= -f2- | xargs)
  [ "$plate" = "$PLATE" ] || { echo "$name: sliced for '$plate', not '$PLATE'"; exit 1; }
  grams=$($PY "$SCRIPTS/gcode_grams.py" "$gcode")
  # Two independent readings of the same G-code: Bambu's header total and the extrusion the reader sums; a gap means the reader misses moves
  echo "$grams" | python3 -c "import json, sys; r = json.load(sys.stdin)['header_residual_g']; sys.exit(f'grams summed from the G-code differ from Bambu\'s total by {r} g' if abs(r) > 0.5 else 0)"
  # Model surface with no extrusion near it means the G-code and STL disagree on placement or shape, or a thin feature was dropped
  coverage=$($PY "$SCRIPTS/coverage.py" "$gcode" "$work/$name.3mf" "$stl")
  supports=$($PY "$SCRIPTS/count_supports.py" "$gcode")
  islands=$($PY "$SCRIPTS/islands_supported.py" "$gcode" "$CHECKS/$name-check.json" "$work/$name.3mf" "$stl")
  # A region that starts in mid-air with nothing under it prints as loose strands
  echo "$islands" | python3 -c "import json, sys; u = json.load(sys.stdin)['unsupported']; sys.exit(f'{len(u)} islands start in mid-air: {u}' if u else 0)"
  $PY "$SCRIPTS/plot_supports.py" "$gcode" "$OUT/$name-supports.png" "$name, $MACHINE, $PLATE, $PROCESS" > /dev/null
  echo "{\"model\": \"$name\", \"plate\": \"$plate\", \"slice\": $grams, \"supports\": $supports, \"islands\": $islands, \"coverage\": $coverage}" | python3 -m json.tool > "$OUT/$name-summary.json"
  echo "sliced $name on $plate: $grams $supports $islands $coverage"
done
