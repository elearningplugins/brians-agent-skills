---
name: linkedin-vertical-captioned-clip
description: >-
  Cut a horizontal live/stream recording into a LinkedIn-ready 9:16 vertical clip
  with TikTok-style one-word captions synced to real audio timestamps (not evenly
  spaced guesses). Use when making LinkedIn verticals, Remotion captioned shorts
  from multi-cam Zoom-style sources, or when the user asks for one-word captions
  that stay clear of faces and on-screen lower-thirds.
---

# LinkedIn vertical captioned clip

Reusable path for LinkedIn 9:16 clips with word-synced captions. Prefer this over raw Whisper on Intel Macs and over evenly spacing transcript words.

**Home for this skill:** `elearningplugins/brians-agent-skills` (portable). Not project-local skills under a single app repo's `.cursor/skills/`.

**Goal deliverable:** one shareable MP4 (1080×1920) with one-word captions synced to speech, faces/lower-thirds clear, 0.5s fade-out. **Open each preview** for the user when they ask to hear/see a trim.

**Default constraint:** no cloud ASR API key unless the user provides one. Use the free local Parakeet path below.

**Privacy:** Do not put guest names, chat handles, full source filenames, or other session-specific PII into this skill, commits, or PR bodies. Keep personal details in the local work folder only.

## Hard rules

1. **Never** invent caption times by evenly spacing words from a transcript (or old chunk transcripts) — that drifts and looks unsynced.
2. **Always** get word timestamps from the cut's audio via Parakeet (`auto-editor whisper … --split-words`). Bench ~15s before the full cut.
3. Burn captions in **Remotion**, not ffmpeg — many Homebrew ffmpeg builds lack `ass` / `subtitles` / `drawtext`.
4. Lock absolute trim times **with the user** — propose a range, open a horizontal preview, then apply their ±s / end trims before the final vertical.
5. Copy templates from this skill's `assets/` rather than reinventing caption Sequence math.
6. If a Remotion render is already running when you change `captions.json` or TSX, **kill it and re-render** — otherwise you ship a stale bundle.

## Prerequisites

| Need | How |
|------|-----|
| `ffmpeg` / `ffprobe` | Homebrew |
| auto-editor **release binary** | GitHub releases (below) — **not** `brew install auto-editor` (pulls Nim, very slow) |
| Parakeet GGUF | [ggml-org/parakeet-GGUF](https://huggingface.co/ggml-org/parakeet-GGUF) `…-q8_0.bin` (other mirror URLs may 404) |
| Node + npm | For Remotion |
| Remotion app | Bootstrap once per clip folder (below) |
| Optional Remotion skills | `npx skills add remotion-dev/skills` → `remotion-captions` |

Related: [WyattBlue/auto-editor `auto-editor-transcribe`](https://github.com/WyattBlue/auto-editor/tree/master/skills/auto-editor-transcribe), [remotion-dev/template-tiktok](https://github.com/remotion-dev/template-tiktok). WhisperX ([ahkamboh/agent-caption](https://github.com/ahkamboh/agent-caption)) only if Parakeet quality fails. GUI backup: MacWhisper → export SRT → `parseSrt`.

**Avoid on Intel Mac for multi-minute clips:** `@remotion/install-whisper-cpp` / brew `whisper-cli` alone (hours; Metal hangs). Prefer Parakeet. Raw `parakeet-cli -ps` can hang after printing text — prefer **auto-editor** wrapping the same model.

## Layout to create

```text
~/Downloads/<clip-name>/          # pick a neutral folder name for this job
  01-horizontal-cut.mp4           # versioned previews as user iterates
  02-….mp4 / 03-….mp4 / 04-….mp4
  05-vertical-speakers-nocaptions.mp4   # crop check before caption burn
  06-vertical-captioned.mp4             # final deliverable
  cut.mp4 / final.wav / words.srt
  remotion/
    public/source.mp4             # === locked cut.mp4
    public/captions.json
    public/words.srt
    src/CaptionedVideo.tsx        # from assets/
    src/Composition.tsx           # from assets/; set DURATION_SEC
```

## End-to-end workflow

### 0. Bootstrap Remotion (once per work folder)

```bash
export WORK="$HOME/Downloads/linkedin-vertical-clip"   # or any new folder for this job
mkdir -p "$WORK" && cd "$WORK"
npx create-video@latest --yes --blank remotion
cd remotion
npx remotion add @remotion/captions
```

```bash
# Skill dir: repo clone or ~/.cursor/skills/linkedin-vertical-captioned-clip
SKILL_DIR="$HOME/Documents/GitHub/brians-agent-skills/linkedin-vertical-captioned-clip"
cp "$SKILL_DIR/assets/CaptionedVideo.tsx" src/CaptionedVideo.tsx
cp "$SKILL_DIR/assets/Composition.tsx" src/Composition.tsx
# Root.tsx must render <MyComposition /> from Composition.tsx
```

Composition id in the template is `LinkedInVertical` — render with that id (or change both).

### 1. Find the source and the narrative beat

Ask the user for the source path (Downloads, Desktop, etc.). Do not hard-code show titles or guest names into reusable docs.

Probe first:

```bash
ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$SOURCE"
ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$SOURCE"
```

Common live layouts are **1280×720** at ~30fps; confirm before setting crop constants.

**Story beat:** use whatever the user describes (topic phrase, shout-out, Q&A moment). How to find it in a long recording:

- Chunk-transcribe with a fast local model **only for discovery** (edit timestamps, not final captions), or scrub with `ffmpeg -ss` previews.
- Propose clock times to the user (e.g. `mm:ss → mm:ss`).
- Convert: `seconds = mm*60+ss`.

### 2. Iterative trim (horizontal first)

Do **not** jump straight to vertical captions.

1. Cut a horizontal preview; `open` it.
2. Apply user feedback, keeping versioned files:
   - "start at :25" of the current cut → re-encode from that offset
   - "add N seconds" at the end
   - "take N seconds off" the end (dead air, cough, false start, etc.)
3. Re-open after each change. Only when they like the **audio story**, lock abs start + duration.

Illustrative iteration pattern (replace with this job's numbers):

| Step | What to do |
|------|------------|
| First propose | Clock range from discovery |
| Nudge start | Offset into that cut (e.g. start at `:25`) |
| Extend / shorten end | ± seconds until the exit is clean |
| Lock | Record `START` (abs seconds) and `DUR` |

```bash
START=0      # abs seconds in SOURCE — locked with user
DUR=120      # seconds — locked with user
ffmpeg -y -ss "$START" -i "$SOURCE" -t "$DUR" -c:v libx264 -c:a aac "$WORK/cut.mp4"
ffmpeg -y -i "$WORK/cut.mp4" -ar 16000 -ac 1 "$WORK/final.wav"
cp "$WORK/cut.mp4" "$WORK/remotion/public/source.mp4"
open "$WORK/cut.mp4"
```

Set `DURATION_SEC` in `Composition.tsx` from ffprobe of `public/source.mp4` (`frames = round(sec * 30)`).

**Black flash at start?** Usually the player (audio starts ~1 frame before video), not a missing first frame. Verify before re-trimming:

```bash
ffmpeg -y -ss 0 -i "$WORK/cut.mp4" -frames:v 1 /tmp/frame0.jpg && open /tmp/frame0.jpg
```

### 3. Vertical crop (multi-cam) — check without captions

Typical ask: crop to the **speaking stack** (often the left cams); captions must not cover faces or existing lower-third text; **one word** at a time.

Template assumes **1280×720** source, left stack, canvas **1080×1920**:

- `scale = 1920/720`; height 1920; `CROP_X = 0` → left ~**405px** of source in the 1080 viewport.
- If speakers are not on the left, change `CROP_X` and verify in Studio.

Optional: render a **no-captions** vertical (`05-…`) so the user can approve the crop before ASR finishes.

### 4. Word-level ASR (Parakeet via auto-editor)

```bash
TOOLS=/tmp/linkedin-clip-tools
mkdir -p "$TOOLS" && cd "$TOOLS"

case "$(uname -m)" in
  arm64|aarch64) AE_BIN=auto-editor-macos-arm64 ;;
  *)             AE_BIN=auto-editor-macos-x86_64 ;;
esac
AE_VER=31.6.0   # bump if release moved
curl -L --fail -o auto-editor \
  "https://github.com/WyattBlue/auto-editor/releases/download/${AE_VER}/${AE_BIN}"
chmod +x auto-editor

MODEL="$TOOLS/ggml-parakeet-tdt-0.6b-v3-q8_0.bin"
curl -L --fail -o "$MODEL" \
  "https://huggingface.co/ggml-org/parakeet-GGUF/resolve/main/ggml-parakeet-tdt-0.6b-v3-q8_0.bin"
```

**Bench first** (~15s) — pick a distinctive word you can hear in that window and confirm the SRT cue lands on the right second:

```bash
ffmpeg -y -i "$WORK/final.wav" -t 15 "$WORK/bench15.wav"
"$TOOLS/auto-editor" whisper "$WORK/bench15.wav" "$MODEL" \
  --format srt --split-words -o "$WORK/bench-words.srt" --threads 8
```

Full cut:

```bash
"$TOOLS/auto-editor" whisper "$WORK/final.wav" "$MODEL" \
  --format srt --split-words -o "$WORK/words.srt" --threads 8
cp "$WORK/words.srt" "$WORK/remotion/public/words.srt"
```

Parakeet rejects `--prompt`, `--translate`, `--language`. Rough Intel timing: ~12s for 15s audio; ~90s for ~2.5 min. If the user asks "status?", report ASR/render progress — do not sit silent on a multi-hour Whisper job.

### 5. SRT → `public/captions.json`

From `remotion/`:

```bash
node --input-type=module << 'JS'
import {parseSrt} from '@remotion/captions';
import fs from 'fs';

const input = fs.readFileSync('public/words.srt', 'utf8');
const {captions} = parseSrt({input});
const normalized = captions.map((c, i) => ({
  ...c,
  text: i === 0 ? c.text.trim() : ' ' + c.text.trim(),
}));
fs.writeFileSync('public/captions.json', JSON.stringify(normalized, null, 2));
console.log('captions', normalized.length, 'span', normalized[0]?.startMs, '→', normalized.at(-1)?.endMs);
JS
```

Strip fillers **without retiming** (delete matching cues only; neighbors keep their `startMs`/`endMs`):

```bash
python3 << 'PY'
import json, re
from pathlib import Path
p = Path('public/captions.json')
caps = json.loads(p.read_text())
filler = re.compile(r'^[\s]*(uh|um|uh+|umm+)[\s\.,!\?]*$', re.I)
kept = [c for c in caps if not filler.match(c['text'].strip())]
print(f'{len(caps)} → {len(kept)}')
p.write_text(json.dumps(kept, indent=2))
PY
```

### 6. Caption look + fade (in `assets/CaptionedVideo.tsx`)

- `createTikTokStyleCaptions({ combineTokensWithinMilliseconds: 0 })` → one word.
- Uppercase, heavy sans, highlight `#39E508`, thick black outline.
- Placement for stacked cams with lower-thirds: `justifyContent: 'flex-end'`, `paddingBottom: '9%'` (clears faces; sits above bottom name tags). Higher values can still cover faces — **nudge and re-render** after a frame grab.
- Fade last **0.5s**: root opacity + `OffthreadVideo` volume → 0.

### 7. Render and QA

```bash
cd "$WORK/remotion"
# If a prior render is running after caption edits: pkill -f 'remotion render' first
npx remotion render LinkedInVertical ../06-vertical-captioned.mp4 --codec=h264 --concurrency=2
open ../06-vertical-captioned.mp4
```

```bash
# Spot-check a mid-clip second where you know a word is spoken
ffmpeg -y -ss 5.0 -i ../06-vertical-captioned.mp4 -frames:v 1 /tmp/cap-check.jpg
# Near end should be nearly black
ffmpeg -y -sseof -0.15 -i ../06-vertical-captioned.mp4 -frames:v 1 /tmp/fade-end.jpg
```

Confirm: sync; faces/name tags clear; fade; story trim matches what the user locked.

## Failure modes

| Symptom | Fix |
|---------|-----|
| Captions drift / "not synced at all" | You even-spaced transcript words or used segment SRT — re-run `--split-words` Parakeet on `final.wav` |
| Whisper/`install-whisper-cpp` grinding for hours | Kill it; Parakeet + auto-editor binary |
| `brew install auto-editor` stuck on Nim | Abort; download release binary |
| `--prompt is not supported` | Drop `--prompt` for Parakeet |
| Parakeet model 404 | Use `ggml-org/parakeet-GGUF` …`q8_0.bin` |
| `parakeet-cli` prints text then hangs | Use auto-editor `whisper` instead of raw `-ps` |
| Captions cover faces / lower-thirds | Lower `paddingBottom` toward ~6–9%; re-render; check frame grabs |
| User sees black at t=0 | Check frame0 with ffmpeg; often player A/V skew, not a bad cut |
| Stale captions after edit | Kill Remotion render; render again after writing `captions.json` |
| Composition id not found | Read `Composition.tsx`; pass that id to `remotion render` |
| ffmpeg cannot burn subs | Expected — Remotion only |
| Wrong length | Sync `DURATION_SEC` to ffprobe of `public/source.mp4` |

## Checklist

1. Found source (path from user); proposed narrative beat; **user-locked** trim with versioned horizontal previews opened.
2. `cut.mp4` = `public/source.mp4`; `DURATION_SEC` matches; frame0 is real video.
3. Speaking-stack vertical crop approved (optional no-caption render).
4. Templates from `assets/`; `@remotion/captions` installed.
5. Bench SRT synced; full `--split-words` → `captions.json` (not even spacing).
6. Optional: strip `uh`/`um` without shifting neighbors.
7. Captions clear of faces + lower-thirds; 0.5s A/V fade-out.
8. Final `06-vertical-captioned.mp4` opened after sync/fade frame checks.
9. No guest names, show titles, or other session PII committed into the skill repo.
