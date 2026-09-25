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

Public, reusable workflow for **1080×1920** LinkedIn clips with **one-word captions** timed from real speech (not evenly spaced transcript guesses).

Works with Cursor, Claude Code, Codex, or by hand. Install this skill directory, then follow the steps below (or ask an agent to follow them).

**Goal:** one shareable MP4 — synced captions, faces/lower-thirds clear, optional 0.5s fade-out. Preview cuts in a player as you go.

**Default:** free **local** ASR (no cloud API key). Use a hosted Whisper API only if you choose to.

## Install this skill

```bash
# Option A — Cursor / Claude Code skill installer
npx skills add elearningplugins/brians-agent-skills

# Option B — clone and copy
git clone https://github.com/elearningplugins/brians-agent-skills.git
cp -R brians-agent-skills/linkedin-vertical-captioned-clip ~/.cursor/skills/
# or: …/.claude/skills/linkedin-vertical-captioned-clip
```

Templates live in `assets/` next to this `SKILL.md`. Resolve that directory portably:

```bash
# After install, typical locations:
SKILL_DIR="${SKILL_DIR:-$HOME/.cursor/skills/linkedin-vertical-captioned-clip}"
# or: $HOME/.claude/skills/linkedin-vertical-captioned-clip
# or: /path/to/clone/brians-agent-skills/linkedin-vertical-captioned-clip
test -f "$SKILL_DIR/assets/Composition.tsx" || { echo "Set SKILL_DIR to this skill folder"; exit 1; }
```

## Hard rules

1. **Never** invent caption times by evenly spacing words from a transcript — that drifts.
2. **Always** get word timestamps from the cut audio via Parakeet (`auto-editor whisper … --split-words`). Bench ~15s before the full cut.
3. Burn captions in **Remotion**, not ffmpeg — many ffmpeg builds lack `ass` / `subtitles` / `drawtext`.
4. Lock the trim (start + duration) before the final vertical — preview horizontally first; iterate ±seconds.
5. Copy `assets/Composition.tsx` rather than reinventing caption Sequence math.
6. If Remotion is already rendering when you change `captions.json` or TSX, **stop it and re-render**.

## Prerequisites

| Need | Notes |
|------|--------|
| `ffmpeg` / `ffprobe` | macOS: Homebrew. Linux: distro packages. Windows: winget/choco or full build. |
| auto-editor **release binary** | [WyattBlue/auto-editor releases](https://github.com/WyattBlue/auto-editor/releases) — prefer the binary over compiling from source. |
| Parakeet GGUF (~640MB disk) | [ggml-org/parakeet-GGUF](https://huggingface.co/ggml-org/parakeet-GGUF) `ggml-parakeet-tdt-0.6b-v3-q8_0.bin` |
| Node.js + npm | For Remotion |
| Remotion | Free for individuals / orgs under Remotion’s current revenue threshold — see [remotion.dev/license](https://www.remotion.dev/docs/license). First render may download a headless browser. |

Optional: `npx skills add remotion-dev/skills` (official caption docs). WhisperX / [agent-caption](https://github.com/ahkamboh/agent-caption) only if Parakeet quality fails. GUI backup: any local Whisper app that exports **word-level** SRT → `parseSrt`.

**CPU note:** On slower Intel Macs, Remotion’s Whisper / brew `whisper-cli` can take hours for a few minutes of audio. Parakeet via auto-editor is the intended default on all platforms. Raw `parakeet-cli -ps` can hang after printing text — use **auto-editor** instead.

## Layout

```text
$WORK/                            # any folder you choose for this job
  01-horizontal-cut.mp4           # versioned previews
  05-vertical-speakers-nocaptions.mp4
  06-vertical-captioned.mp4       # final
  cut.mp4 / final.wav / words.srt
  remotion/
    public/source.mp4             # same as locked cut.mp4
    public/captions.json
    public/words.srt
    src/Composition.tsx           # from assets/ (crop + captions + registration)
```

## End-to-end workflow

### 0. Bootstrap Remotion

```bash
export WORK="${WORK:-$HOME/Downloads/linkedin-vertical-clip}"
mkdir -p "$WORK" && cd "$WORK"
npx create-video@latest --yes --blank remotion
cd remotion
npx remotion add @remotion/captions
cp "$SKILL_DIR/assets/Composition.tsx" src/Composition.tsx
# Ensure src/Root.tsx renders <MyComposition /> from ./Composition (create-video blank does).
```

Composition id in the template: **`LinkedInVertical`**. Use that id in `remotion render`, or change both the template and the render command.

### 1. Source + narrative beat

Set `SOURCE` to your recording. Probe:

```bash
ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$SOURCE"
ffprobe -v quiet -select_streams v:0 -show_entries stream=width,height,r_frame_rate -of csv=p=0 "$SOURCE"
```

The crop template defaults to **1280×720** sources. For other sizes, edit `SOURCE_WIDTH` / `SOURCE_HEIGHT` / `CROP_X` at the top of `Composition.tsx`.

Find the beat (topic phrase, shout-out, Q&A): chunk-transcribe **for discovery only**, or scrub with `ffmpeg -ss` previews. Convert clock times with `seconds = mm*60+ss`.

### 2. Iterative trim (horizontal first)

Do not jump straight to vertical captions.

1. Cut a horizontal preview; open it in a player (`open` on macOS, `xdg-open` on Linux, or your file manager).
2. Version files as you nudge start/end (`:25` into the cut, ± seconds on the exit).
3. Lock `START` (abs seconds in `SOURCE`) and `DUR` when the story sounds right.

```bash
START=0      # abs seconds — locked
DUR=120      # seconds — locked
ffmpeg -y -ss "$START" -i "$SOURCE" -t "$DUR" -c:v libx264 -c:a aac "$WORK/cut.mp4"
ffmpeg -y -i "$WORK/cut.mp4" -ar 16000 -ac 1 "$WORK/final.wav"
cp "$WORK/cut.mp4" "$WORK/remotion/public/source.mp4"
```

Set `DURATION_SEC` near the top of `Composition.tsx` from ffprobe of `public/source.mp4` (`frames = round(sec * 30)` at 30fps).

**Black flash at t=0?** Often the player (audio ~1 frame early), not a missing frame. Check:

```bash
ffmpeg -y -ss 0 -i "$WORK/cut.mp4" -frames:v 1 /tmp/frame0.jpg
```

### 3. Vertical crop

Typical ask: speaking stack only (often **left** cams); one word on screen; clear of faces and lower-thirds.

Default math for 1280×720 → 1080×1920: `scale = 1920/720`, `CROP_X = 0` (≈405px of source width visible). Change `CROP_X` if speakers are elsewhere. Optional: render a no-caption vertical to approve crop before ASR finishes.

### 4. Word-level ASR (Parakeet via auto-editor)

```bash
TOOLS="${TOOLS:-/tmp/linkedin-clip-tools}"
mkdir -p "$TOOLS" && cd "$TOOLS"
AE_VER=31.6.0   # bump to latest release tag if needed

uname_s="$(uname -s | tr '[:upper:]' '[:lower:]')"
uname_m="$(uname -m)"
case "${uname_s}-${uname_m}" in
  darwin-arm64|darwin-aarch64) AE_BIN=auto-editor-macos-arm64 ;;
  darwin-*)                    AE_BIN=auto-editor-macos-x86_64 ;;
  linux-aarch64|linux-arm64)   AE_BIN=auto-editor-linux-aarch64 ;;
  linux-*)                     AE_BIN=auto-editor-linux-x86_64 ;;
  msys*|cygwin*|mingw*|windows*)
    echo "Download auto-editor-windows-x86_64.exe (or arm64) from GitHub releases"; exit 1 ;;
  *) echo "Unsupported uname: ${uname_s}-${uname_m}"; exit 1 ;;
esac

curl -L --fail -o auto-editor \
  "https://github.com/WyattBlue/auto-editor/releases/download/${AE_VER}/${AE_BIN}"
chmod +x auto-editor

MODEL="$TOOLS/ggml-parakeet-tdt-0.6b-v3-q8_0.bin"
curl -L --fail -o "$MODEL" \
  "https://huggingface.co/ggml-org/parakeet-GGUF/resolve/main/ggml-parakeet-tdt-0.6b-v3-q8_0.bin"
```

Bench ~15s, then full cut:

```bash
ffmpeg -y -i "$WORK/final.wav" -t 15 "$WORK/bench15.wav"
"$TOOLS/auto-editor" whisper "$WORK/bench15.wav" "$MODEL" \
  --format srt --split-words -o "$WORK/bench-words.srt" --threads 8
# Confirm a distinctive spoken word lands on the right second in the SRT.

"$TOOLS/auto-editor" whisper "$WORK/final.wav" "$MODEL" \
  --format srt --split-words -o "$WORK/words.srt" --threads 8
cp "$WORK/words.srt" "$WORK/remotion/public/words.srt"
```

Parakeet rejects `--prompt`, `--translate`, `--language`. Expect roughly real-time or better on modern CPUs; slower machines take longer — still far better than Whisper.cpp grinding for hours.

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
console.log('captions', normalized.length);
JS
```

Optional — drop filler cues **without retiming** neighbors:

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

### 6. Look + fade

Already in `assets/Composition.tsx`:

- One word: `combineTokensWithinMilliseconds: 0`
- Style: uppercase, heavy sans, `#39E508` highlight, black outline
- Placement: `paddingBottom: '9%'` — nudge after frame grabs if faces/tags are covered
- Fade: last **0.5s** opacity + audio volume → 0

### 7. Render + QA

```bash
cd "$WORK/remotion"
npx remotion render LinkedInVertical ../06-vertical-captioned.mp4 --codec=h264 --concurrency=2
```

```bash
ffmpeg -y -ss 5.0 -i ../06-vertical-captioned.mp4 -frames:v 1 /tmp/cap-check.jpg
ffmpeg -y -sseof -0.15 -i ../06-vertical-captioned.mp4 -frames:v 1 /tmp/fade-end.jpg
```

Confirm: sync, faces/lower-thirds clear, fade, trim matches the locked story.

## Failure modes

| Symptom | Fix |
|---------|-----|
| Captions drift | Re-run `--split-words` Parakeet on `final.wav` — do not even-space words |
| Whisper grinding for hours | Stop; use Parakeet + auto-editor binary |
| Compiling auto-editor from source forever | Use the GitHub release binary for your OS/arch |
| `--prompt is not supported` | Omit `--prompt` with Parakeet |
| Model 404 | Use `ggml-org/parakeet-GGUF` …`q8_0.bin` |
| Wrong auto-editor binary | Match `uname` table (macOS/Linux arm64 vs x86_64; Windows `.exe` on releases) |
| Faces / lower-thirds covered | Adjust `paddingBottom` / crop; re-render |
| Black flash at t=0 | Check frame0; often player A/V skew |
| Stale captions | Stop Remotion; render again after writing JSON |
| Composition not found | Pass the id from `Composition.tsx` |
| Non-720p source | Edit `SOURCE_WIDTH` / `SOURCE_HEIGHT` / `CROP_X` in `Composition.tsx` |
| ffmpeg cannot burn subs | Expected — use Remotion |
| Wrong length | Sync `DURATION_SEC` to ffprobe of `public/source.mp4` |

## Checklist

1. Skill installed; `SKILL_DIR` points at this folder’s `assets/`.
2. Trim locked; `cut.mp4` = `public/source.mp4`; `DURATION_SEC` matches.
3. Crop approved (optional no-caption render).
4. Bench SRT synced; full `--split-words` → `captions.json`.
5. Optional filler strip without shifting neighbors.
6. Captions clear of faces/lower-thirds; 0.5s fade.
7. Final MP4 QA’d (sync + fade frames).

## Privacy (when publishing)

Keep guest names, private chat handles, and raw long-form recordings out of **public** git repos and skill docs. Your local `$WORK` folder can hold whatever you need to edit.
