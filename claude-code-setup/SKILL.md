---
name: claude-code-setup
description: Audits and reproduces a Claude Code setup on any computer - default model, effort levels, the subagent deny rule, global CLAUDE.md rules and MCP servers - and measures where usage goes from local transcripts. Finds config drift, settings that override the baseline, broken or runaway MCP entries such as a Cursor entry that starts bare `claude`, plaintext tokens and context-heavy sessions. Use when setting up Claude Code on a new machine, syncing settings between computers, checking which model or effort is active, asking whether subagents are off, hitting usage limits, or asking why Claude usage is high, even if the user never says "audit".
---

# Claude Code Setup

Bring a machine to a known Claude Code baseline, then measure what is using its limits. The audit exists because the settings that looked like the problem were fine: on the machine this came from the subagent deny rule was working, while a Cursor entry had started `claude` about 250 times a day for weeks, unnoticed. Do not call a setup correct or a cause proven until the numbers below say so, and change nothing until the user has seen the dry run.

## Workflow

```
- [ ] 1. Audit
- [ ] 2. Report, separating measured from inferred
- [ ] 3. Apply the baseline after a dry run
- [ ] 4. Set up MCP servers
- [ ] 5. Verify in a new session
```

Scripts need `python3` and only the standard library. They are tested on macOS. Nothing else has been run yet, so report it if you are on Linux or Windows and a path does not resolve.

Set `SKILL_DIR` to this skill's folder first:

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.claude/skills/claude-code-setup}"
test -f "$SKILL_DIR/scripts/audit_setup.py" || { echo "Set SKILL_DIR to this skill folder"; exit 1; }
```

## The baseline

| Setting | Value | Why |
|---|---|---|
| `model` | `opus` | The alias follows the current Opus release. |
| `effortLevel` | `xhigh` | Fallback for models with no override, such as Fable. |
| `modelSettings.claude-opus-5-5.effortLevel` | `medium` | The everyday default. This key names one model ID, so it stops applying when Opus moves on and effort silently rises to `xhigh`. The audit flags that as `no-effort-override`. |
| `permissions.deny` | `Task`, `Agent` | Added after a usage report attributed 96% of usage to subagent-heavy sessions. Other deny rules are kept. |
| `tui` | `fullscreen` | Terminal layout preference. |
| `~/.claude/CLAUDE.md` | Single-line comments rule | Applies across every repository. |

The values live in `assets/baseline-settings.json` and `assets/global-CLAUDE.md`. When the preferred setup changes, change those files and this table together.

## Protect secrets

MCP configs often hold plaintext tokens. Do not `Read` or `cat` `~/.cursor/mcp.json`, `~/.claude.json` or project `.mcp.json` files. Reading one copies the token into the session transcript, and the `Edit` tool keeps pre-edit copies in `~/.claude/file-history`. Both happened while this skill was being written. The audit reports where a secret sits and never its value, and project `.mcp.json` files are not audited at all.

- To change a config that holds a token, use a script that prints nothing from the file, or have the user edit it.
- Have the user run commands containing tokens in a separate terminal. The `!` prefix does not help, because the command and its output land in the conversation.
- Deleting a file does not make a token safe. If a token may be exposed, tell the user plainly, have them revoke it, and name the remaining copies.

## 1. Audit

```bash
python3 "$SKILL_DIR/scripts/audit_setup.py"
```

It is read-only, prints JSON and exits with:

| Exit | Meaning |
|---|---|
| 0 | No findings in anything it checks |
| 1 | Drift, an override or an MCP finding needs attention |
| 2 | A config or transcript could not be read, so the report is incomplete |

Treat 2 as a failed audit, not a clean one. Run it from the project in question or pass `--project`, because project settings can override the user file. `--days 7` narrows the usage window.

## 2. Report

Lead with the verdict, then cover each area below. Mark each claim as **measured** or **inferred**.

- **Config:** `settings.drift`, `settings.overrides` and `settings.effort_findings`. Also check `env.values`, because `ANTHROPIC_MODEL` or `CLAUDE_EFFORT` can change what runs without appearing as drift.
- **Subagents:** `usage.subagent_calls` and `usage.subagent_transcripts`. Both empty shows none ran in the window. It does not show the rule is why.
- **MCP:** each item in `mcp.findings`.
- **Usage:** `usage.tokens` by type, `requests_by_model`, `average_context_per_request`, and the top sessions with their `cumulative_share_pct`.

| Finding | Meaning | Fix |
|---|---|---|
| `bare-claude-command` | A client starts `claude` as an MCP server, which needs the args `mcp serve`. The client retries indefinitely. About 6,100 such runs on one machine got no model reply but left 729 MB of transcripts. | Remove the entry, or set args to `mcp`, `serve`. |
| `missing-path` | A stdio server points at a file that does not exist here, which is common on a new machine. | Clone and build it, then correct the path. |
| `plaintext-secret` | A token is stored in a config file. | Move it to an environment variable. Revoke it if exposed. |
| `no-effort-override` | The most-used model has no override, so it runs at the `effortLevel` fallback. | Add its model ID to the baseline. |
| `unused-effort-override` | An override matches no model used in the window. | Remove it if that model is retired. It may just be unused lately. |
| `settings.overrides` | Another settings file sets a baseline key and can win. | Ask whether it is deliberate. |
| `handshake_transcripts` above 0 | Leftovers from a bare `claude` entry. | Fix the entry. The files are harmless, and Claude Code appears to prune them after about 30 days. Delete them only if the user asks. |

### Limits of the numbers

- Transcripts cover only what Claude Code has not pruned, about 30 days by default. Do not confirm or deny a figure older than that.
- `context_tokens` adds cheap cache reads to full-price tokens, so its shares show where context piled up, not cost or limit use. Use `usage.tokens` when the difference matters.
- The audit reads config files. It does not see managed settings or what a running session loaded, so only step 5 shows a setting is in effect.

## 3. Apply the baseline

Show the dry run, then ask before writing:

```bash
python3 "$SKILL_DIR/scripts/apply_baseline.py"
python3 "$SKILL_DIR/scripts/apply_baseline.py" --write
```

Unrelated keys stay. Scalars are replaced, deny lists only grow, and each changed file gets a timestamped `.bak-` copy. If a machine has deliberately different values, ask rather than overwrite them.

## 4. Set up MCP servers

Add servers with the CLI rather than by editing `~/.claude.json`:

```bash
claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp
```

Ask which other servers this machine needs. A local server needs its repository cloned and built first:

```bash
claude mcp add --scope user <name> -- node /absolute/path/to/server.js
```

## 5. Verify

1. Run the audit again and confirm it exits 0, or that every remaining finding is one the user chose to keep.
2. Start a new session, because running sessions keep their old settings. Confirm the `Agent` tool is unavailable and the model and effort are as expected.
3. For a removed MCP entry, reload the client (in Cursor, **Developer: Reload Window**), then count new handshake transcripts over a period longer than the old retry gap. On the original machine that gap was usually under 2 minutes, but 10% of gaps ran past 20 minutes.

## Advising on usage

Tie advice to this machine's numbers. Every request re-reads the context, so these are the levers, but this skill has not measured how much each one saves. Say so, and compare the same audit window before and after if the user wants proof.

- Run `/clear` between unrelated tasks, and `/compact` when a long session must continue.
- Start Claude in the repository the work belongs to, which keeps sessions shorter and project memory separate.
- Use `/model sonnet` for mechanical work such as applying a known fix or running tests.
- Keep subagents denied unless a task needs them. To allow them again, prefer one read-only agent on a smaller model over removing the rule.

Do not quote dollar amounts unless the user is on API billing and you have current pricing.

## Honesty rules

- Say which window a usage number covers.
- Never report "no findings" from an audit that exited 2.
- Do not attribute a usage drop to one change unless that was the only change and you compared the same window.
- Do not paste audit output into public places: it holds local paths, server names and session IDs.

## Tests

```bash
cd "$SKILL_DIR/scripts" && python3 -m pytest test_setup_scripts.py
```

Tests use a fake home directory and need `pytest`. When a real setup problem gets past the audit, add the check that would have caught it.
