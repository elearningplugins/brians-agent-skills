#!/usr/bin/env bash
# Extract frames from a water-meter video and build contact sheets in both orientations.
set -euo pipefail

usage() {
  echo "usage: $0 <video> <out_dir> [fps] [crop]" >&2
  echo "  fps   frames per second to extract (default 2)" >&2
  echo "  crop  optional ffmpeg crop w:h:x:y applied after rotation, e.g. 440:300:140:420" >&2
  exit 2
}

[[ $# -lt 2 ]] && usage
video=$1
out=$2
fps=${3:-2}
crop=${4:-}

command -v ffmpeg >/dev/null || { echo "ffmpeg is required (brew install ffmpeg)" >&2; exit 1; }
[[ -f $video ]] || { echo "no such video: $video" >&2; exit 1; }

mkdir -p "$out/upright" "$out/rotated"

ffprobe -v error -show_entries format=duration:stream=width,height:format_tags=creation_time \
  -of default=noprint_wrappers=1 "$video" | tee "$out/info.txt"

crop_filter=""
[[ -n $crop ]] && crop_filter=",crop=$crop"

ffmpeg -v error -y -i "$video" -vf "fps=$fps$crop_filter" -q:v 2 "$out/upright/f_%04d.jpg"
ffmpeg -v error -y -i "$video" -vf "fps=$fps,hflip,vflip$crop_filter" -q:v 2 "$out/rotated/f_%04d.jpg"

for dir in upright rotated; do
  ffmpeg -v error -y -i "$out/$dir/f_%04d.jpg" \
    -vf "select='not(mod(n\,4))',scale=320:-1,tile=4x6" -fps_mode vfr "$out/sheet_${dir}_%02d.jpg"
done

echo "frames: $out/upright, $out/rotated"
echo "sheets: $out/sheet_upright_NN.jpg, $out/sheet_rotated_NN.jpg (every 4th frame, 24 per sheet; read whichever orientation is legible)"
