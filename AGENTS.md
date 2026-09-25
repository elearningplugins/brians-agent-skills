# Agent guidance for this repository

This repo publishes reusable Agent Skills (`SKILL.md`), not an application.

## Layout

- `pr-quality/` — PR preparation and review skill
- `qa-unit-testing/` — TypeScript unit / property / mutation testing skill
- `linkedin-vertical-captioned-clip/` — LinkedIn 9:16 Remotion clip with Parakeet word captions

Each skill directory is self-contained. Prefer editing inside one skill at a time.

## When changing a skill

1. Keep claims honest: only document workflows the skill actually encodes.
2. Prefer concrete evidence requirements over aspirational advice.
3. Update the root `README.md` skills table if you add, remove, or rename a skill.
4. Keep the repository description aligned with skills that exist on `main`.

## Validation

- Skill front matter and referenced paths should remain valid for tools that consume `SKILL.md`.
- Do not invent installation commands that the supporting CLIs do not provide.

## Voice

Write like an experienced engineer: specific, concise, low-hype. No generic "passionate developer" language.
