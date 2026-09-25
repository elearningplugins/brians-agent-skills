# linkedin-vertical-captioned-clip

Agent Skill (and human runbook) for turning a horizontal live/multi-cam recording into a **LinkedIn 9:16** MP4 with **TikTok-style one-word captions** timed from speech.

## Contents

```text
linkedin-vertical-captioned-clip/
├── SKILL.md                 # Full workflow for agents and humans
├── README.md                # This file
└── assets/
    ├── CaptionedVideo.tsx   # Crop + one-word captions + 0.5s fade
    └── Composition.tsx      # 1080×1920 composition (id: LinkedInVertical)
```

## Install

```bash
npx skills add elearningplugins/brians-agent-skills
```

Or copy this directory to `~/.cursor/skills/linkedin-vertical-captioned-clip` / `~/.claude/skills/…`.

## Quick start

1. Read `SKILL.md` (prerequisites: ffmpeg, Node, ~640MB Parakeet model, auto-editor release binary).
2. Set `SKILL_DIR` to this folder; create a work directory; bootstrap Remotion with the commands in `SKILL.md`.
3. Copy `assets/*.tsx` into the Remotion `src/` tree.
4. Trim → Parakeet word SRT → `captions.json` → render `LinkedInVertical`.

## License

This skill follows the license of [elearningplugins/brians-agent-skills](https://github.com/elearningplugins/brians-agent-skills). Remotion and auto-editor have their own licenses — check those projects before commercial use.
