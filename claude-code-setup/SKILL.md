---
name: claude-code-setup
description: Audits and reproduces a Claude Code setup on any computer - default model, effort levels, the subagent deny rule, global CLAUDE.md rules and MCP servers - and measures where usage really goes from local transcripts. Finds config drift, broken or runaway MCP entries such as a Cursor entry that starts bare `claude`, plaintext tokens and context-heavy sessions. Use when setting up Claude Code on a new machine, syncing settings between computers, checking which model or effort is active, asking whether subagents are off, hitting usage limits, or asking why Claude usage is high, even if the user never says "audit".
---

# Claude Code Setup

Bring a machine to a known Claude Code baseline, then show from evidence what is costing usage. Report measurements, not impressions, and change nothing until the user has seen the dry run.

Run the scripts with `python3`. They use only the standard library and work on macOS and Linux. `SKILL_DIR` below means this skill's directory.

## The baseline

| Setting | Value | Why |
|---|---|---|
| `model` | `opus` | The alias follows the current Opus release. |
| `effortLevel` | `xhigh` | Fallback for models with no override, such as Fable. |
| `modelSettings.claude-opus-5-5.effortLevel` | `medium` | The everyday default. Update this key when the Opus model ID changes. |
| `permissions.deny` | `Task`, `Agent` | Subagents each run their own requests, and heavy use drained limits. Other deny rules are kept. |
| `tui` | `fullscreen` | Terminal layout preference. |
| `~/.claude/CLAUDE.md` | Single-line comments rule | Applies across every repository. |

The values live in `assets/baseline-settings.json` and `assets/global-CLAUDE.md`. The baseline is meant to be edited: when the preferred setup changes, change those files and this table together.

## Protect secrets

MCP configs often hold plaintext tokens. Do not `Read` or `cat` `~/.cursor/mcp.json`, `~/.claude.json` or project `.mcp.json` files, because anything printed lands in the session transcript. Use the audit, which reports where a secret sits and never its value.

If an edit needs the raw file, change it with a script that prints nothing from it. If a token is exposed anyway, tell the user plainly and recommend rotating it.

## Workflow

### 1. Audit

```bash
python3 SKILL_DIR/scripts/audit_setup.py
```

It is read-only and prints JSON. Pass `--days 7` to narrow the usage window.

### 2. Report

Lead with the verdict, then cover:

- **Config:** each item in `settings.drift`. Also check `env.values`, because `ANTHROPIC_MODEL` or `CLAUDE_EFFORT` overrides settings without showing up as drift.
- **Subagents:** `usage.subagent_calls` and `usage.subagent_transcripts` should both be empty while the deny rule is active. Non-empty means the rule is missing, was added recently, or is being bypassed.
- **MCP:** each item in `mcp.findings`.
- **Usage:** `average_context_per_request`, the top sessions and their `cumulative_share_pct`, and `requests_by_model`.

| Finding | Meaning | Fix |
|---|---|---|
| `bare-claude-command` | A client starts `claude` as an MCP server, which is never a server without `mcp serve`. The client retries all day. It usually costs no tokens but creates transcripts endlessly. | Remove the entry, or set args to `mcp`, `serve`. |
| `missing-path` | A stdio server points at a file that does not exist here, which is common on a new machine. | Clone and build it, then correct the path. |
| `plaintext-secret` | A token is stored in a config file. | Move it to an environment variable. Rotate it if it has been exposed. |
| `handshake_transcripts` above 0 | Leftovers from a bare `claude` entry. | Fix the entry first, then clean up in step 5. |

Transcripts only cover what Claude Code has not pruned, about 30 days by default, so say which window a number covers. Do not confirm or deny an older figure the transcripts cannot reach.

### 3. Apply the baseline

Show the dry run, then ask before writing:

```bash
python3 SKILL_DIR/scripts/apply_baseline.py
python3 SKILL_DIR/scripts/apply_baseline.py --write
```

Unrelated keys stay. Scalars are replaced, deny lists only grow, and each changed file gets a timestamped `.bak-` copy. If a machine has deliberately different values, ask rather than overwrite them. Running sessions keep their old settings until restarted.

### 4. Set up MCP servers

Add servers with the CLI rather than by editing `~/.claude.json`:

```bash
claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp
```

Ask the user which other servers this machine needs. A local server needs its repository cloned and built first, then:

```bash
claude mcp add --scope user <name> -- node /absolute/path/to/server.js
```

Have the user supply tokens themselves, for example with `! claude mcp add ...`, so the value stays out of the conversation where possible.

### 5. Clean up handshake transcripts

Only after the broken entry is gone, and with the user's go-ahead:

```bash
python3 SKILL_DIR/scripts/clean_handshake_transcripts.py
python3 SKILL_DIR/scripts/clean_handshake_transcripts.py --delete
```

It matches only transcripts whose first prompt is an MCP `initialize` message and that no model answered. A session with any real reply is kept, and so is anything changed in the last 2 minutes.

### 6. Verify

Run the audit again and confirm that `settings.drift` and `mcp.findings` no longer list what you fixed. For a removed MCP entry, reload the client (in Cursor, **Developer: Reload Window**), then check that no new handshake transcripts appear over at least 10 minutes. Start a new session to check that the `Agent` tool is unavailable and the expected model and effort are active.

## Advising on usage

Every request re-reads the context, so in long sessions context size outweighs model choice and subagents combined. In order of typical impact:

1. Run `/clear` between unrelated tasks.
2. Run `/compact` once a session passes roughly 200-300K tokens. This is a rule of thumb, not a limit.
3. Start Claude in the repository the work belongs to, which keeps sessions short and project memory separate.
4. Use `/model sonnet` for mechanical work such as applying a known fix or running tests.
5. Keep subagents denied unless a task needs them. To allow them again, prefer one read-only agent on a smaller model over removing the rule entirely.

Tie advice to this machine's numbers. Do not quote dollar amounts unless the user is on API billing and you have current pricing.
