---
name: claude-code-setup
description: Audits and reproduces a Claude Code setup on any computer - default model, effort levels, the subagent deny rule, global CLAUDE.md rules and MCP servers - and measures where usage goes from local transcripts. Finds config drift, settings that override the baseline, broken or runaway MCP entries such as a Cursor entry that starts bare `claude`, plaintext tokens and context-heavy sessions. Use when setting up Claude Code on a new machine, syncing settings between computers, checking which model or effort is active, asking whether subagents are off, hitting usage limits, or asking why Claude usage is high, even if the user never says "audit".
---

# Claude Code Setup

Bring a machine to a known Claude Code baseline, then measure what is using its limits. The audit exists because the settings that looked like the problem were fine: on the machine this came from the subagent deny rule was working, while a Cursor entry had started `claude` about 250 times a day for weeks, unnoticed. Do not call a setup correct or a cause proven until the numbers say so, and change nothing until the user has seen the planned changes.

This skill is one file. Build the audit script from the spec below each time it is needed, and do not commit it anywhere.

## Workflow

```
- [ ] 1. Build the audit script and pass the acceptance checks
- [ ] 2. Run it and report, separating measured from inferred
- [ ] 3. Apply the baseline after showing the planned changes
- [ ] 4. Set up MCP servers
- [ ] 5. Verify in a new session
```

## The baseline

This block is the only copy of the baseline. When the preferred setup changes, edit it here.

```json
{
  "settings": {
    "model": "opus",
    "effortLevel": "xhigh",
    "modelSettings": {
      "claude-opus-5-5": { "effortLevel": "medium" }
    },
    "permissions": { "deny": ["Task", "Agent"] },
    "tui": "fullscreen"
  },
  "claude_md_rules": [
    "Write every code comment on a single line: one `//` line, a one-line `/** ... */`, or one `#` line. Never write a comment that spans lines, even where the surrounding code does, and condense any multi-line comment a change edits."
  ]
}
```

- `model`: the alias follows the current Opus release.
- `effortLevel`: the fallback for models with no override, such as Fable.
- `modelSettings`: medium is the everyday default. The key names one model ID, so it stops applying when Opus moves on and effort silently rises to `xhigh`. The audit flags that as `no-effort-override`.
- `permissions.deny`: added after a usage report attributed 96% of usage to subagent-heavy sessions.

## Protect secrets

MCP configs often hold plaintext tokens. Do not `Read` or `cat` `~/.cursor/mcp.json`, `~/.claude.json`, `~/.claude/settings.json` or project `.mcp.json` files. Reading one copies the token into the session transcript, and the `Edit` tool keeps pre-edit copies in `~/.claude/file-history`. Both happened while this skill was being written.

- To change a file that may hold a token, use a small script that prints nothing from it, or have the user edit it.
- Have the user run commands containing tokens in a separate terminal. The `!` prefix does not help, because the command and its output land in the conversation.
- Deleting a file does not make a token safe. If a token may be exposed, tell the user plainly, have them revoke it, and name the remaining copies.

## 1. Build the audit script

Write one Python 3 script, standard library only, to a temporary folder as `audit_setup.py`. It must be read-only: it writes no files and prints only the JSON report. It takes `--home` (default the user's home), `--project` (default the current folder) and `--days` (default 30), and it embeds the baseline above.

### Exit code

| Exit | Meaning |
|---|---|
| 0 | No findings in anything it checks |
| 1 | Any of `settings.drift`, `settings.overrides`, `settings.effort_findings`, `claude_md.missing_rules` or `mcp.findings` is non-empty |
| 2 | `unreadable_configs` is non-empty or `usage.unreadable_transcripts` is above 0, so the report is incomplete. This wins over 1. |

### Report fields

- `version`: output of `claude --version`, or null if it is not installed.
- `billing_type`: `oauthAccount.billingType` from `~/.claude.json`. Print nothing else from `oauthAccount`, which holds the email address.
- `unreadable_configs`: paths among `~/.claude/settings.json`, `~/.claude.json` and `~/.cursor/mcp.json` that exist but do not parse as a JSON object. A corrupt file must never read as an empty one.
- `settings.model`, `settings.effortLevel`, `settings.modelSettings`, `settings.deny`: taken from `~/.claude/settings.json`. Never dump the whole file, because its `env` block can hold secrets.
- `settings.hook_events`: names of the configured hook events only.
- `settings.drift`: a list of `{key, expected, actual}` using dotted keys such as `permissions.deny`. A scalar must be equal. A baseline list only needs its items present, so extra deny rules are not drift.
- `settings.overrides`: for each of `~/.claude/settings.local.json`, `<project>/.claude/settings.json` and `<project>/.claude/settings.local.json` that exists and is not the user settings file itself, `{file, keys}`, where `keys` lists which of `model`, `effortLevel`, `modelSettings` and `permissions` it sets. Use `["unreadable"]` if it does not parse. Omit files that set none. Report key names only, never values.
- `settings.effort_findings`: use the models in `usage.requests_by_model`, ignoring `unknown`. If there are none, return an empty list. Otherwise add `{check: "no-effort-override", detail: <model>}` when the most-used model has no `modelSettings` key, and `{check: "unused-effort-override", detail: <key>}` for each `modelSettings` key matching no used model.
- `claude_md.missing_rules`: baseline rules whose text does not appear in `~/.claude/CLAUDE.md`.
- `custom_agents`: file stems in `~/.claude/agents/*.md`.
- `env.values`: values of `ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` and `CLAUDE_EFFORT` when set.
- `env.other_names`: names, never values, of other variables starting with `ANTHROPIC_` or `CLAUDE_`.
- `mcp.servers`: `{source, server, transport}`. Sources are `claude-user` (`mcpServers` in `~/.claude.json`), `cursor-user` (`mcpServers` in `~/.cursor/mcp.json`) and `claude-project:<path>` (each `projects.<path>.mcpServers` in `~/.claude.json`). Transport is `type`, or `http` if there is a `url`, otherwise `stdio`.
- `mcp.findings`: `{source, server, check, detail}`, using the checks below.
- `usage`: described under Transcripts.

### MCP checks

- `bare-claude-command`: the file name of `command` is `claude` and the first two args are not `mcp`, `serve`.
- `missing-path`: `command` or any arg starts with `/` and does not exist. The detail is that path.
- `plaintext-secret`: the detail says where the secret is, never its value, as `headers.<name>`, `env.<name>`, `args[<index>]` or `url`.
  - For `headers` and `env`, flag an entry if its name matches `key|token|secret|password|passwd|credential|authorization|cookie` (case-insensitive) or its value matches a token pattern. Skip values that start with `$` or contain `${`, which reference the environment.
  - Flag an arg if it matches a token pattern.
  - Flag the URL if it matches a token pattern or has a query parameter whose name contains `key`, `token` or `secret`.
  - Token patterns: `gh[pousr]_[A-Za-z0-9]{20,}`, `github_pat_\w{20,}`, `sk-[A-Za-z0-9_-]{20,}`, `xox[abp]-[A-Za-z0-9-]{10,}`, `AKIA[0-9A-Z]{16}`, `Bearer\s+\S{12,}`.

### Transcripts

Transcripts are JSONL files found recursively under `~/.claude/projects`. Include those modified within `--days`. Skip lines that are not JSON objects. Count a file that cannot be opened, even a folder named `x.jsonl`, in `unreadable_transcripts` rather than skipping it silently.

A user entry has `type: "user"` and `message.content`, which is a string or a list of blocks. An assistant entry has `message.role: "assistant"`, `message.id`, `message.model`, `message.content` and `message.usage`.

These rules are where hand-written counts go wrong:

- **Dedupe by `message.id`.** Each content block writes its own line and repeats the full usage. Counting lines overstated output tokens about 2.6 times on the original machine.
- **Ignore `message.model` equal to `<synthetic>`.** These are local placeholders, not requests.
- **Dedupe Agent and Task calls by tool-use `id`.** They appear as `tool_use` blocks.
- **A handshake transcript** has a first user prompt, after joining text blocks and trimming, that starts with `{`, matches `"method"\s*:\s*"initialize"` and contains `clientInfo`, and it has no real assistant reply. A prompt that merely quotes one must not match, and any real reply disqualifies it. Count these separately and leave them out of all other usage figures.
- **A subagent transcript** has `subagents` in its path, a file name starting with `agent-`, or any entry with `isSidechain` true.

`usage` holds:

- `window_days`, `sessions` (non-handshake files with at least one request) and `requests`.
- `tokens`: separate totals for `input_tokens`, `cache_read_tokens` (`cache_read_input_tokens`), `cache_write_tokens` (`cache_creation_input_tokens`) and `output_tokens`.
- `average_context_per_request`: the three input types together, divided by requests.
- `requests_by_model`: most used first.
- `subagent_calls`: counts keyed `<subagent_type>/<model>`, using `default` and `inherit` when absent.
- `subagent_transcripts`, `handshake_transcripts` (`{files, bytes}`) and `unreadable_transcripts`.
- `top_sessions`: the five sessions with the most context, each with the first 8 characters of the file name as `session`, plus `requests`, `output_tokens`, `context_tokens`, `average_context`, `peak_context` and `cumulative_share_pct`.

### Acceptance checks

Do not run the script on real config until it passes these on fake homes in the temporary folder. A rebuilt script is untested code, and the first one to read a real token decides whether it leaks. Build the fake token by joining strings so that it is never one literal.

1. An empty home exits 1. A home matching the baseline exactly, including `CLAUDE.md`, exits 0 with empty `settings.drift`.
2. A fake token in a Cursor header and a fake email in `oauthAccount` do not appear anywhere in the output, and a `plaintext-secret` finding names `headers.Authorization`.
3. An `env` value of `${API_KEY}` is not flagged.
4. A corrupt `~/.cursor/mcp.json` exits 2 and is listed in `unreadable_configs`.
5. A folder named `broken.jsonl` under `projects` exits 2.
6. A message repeated on three lines counts as one request, and a `<synthetic>` message adds nothing.
7. Handshake matching follows the rules above in all three cases: no reply, a real reply, and a prompt that only quotes a handshake.
8. `claude` with no args is flagged, and `claude mcp serve` is not.
9. A project override reports key names and no values.
10. A home matching the baseline except for a missing `CLAUDE.md` rule exits 1.

## 2. Run and report

Run the script from the project in question. Treat exit 2 as a failed audit, not a clean one.

Lead with the verdict, then cover each area. Mark each claim as **measured** or **inferred**.

- **Config:** `settings.drift`, `settings.overrides`, `settings.effort_findings` and `claude_md.missing_rules`. Also check `env.values`, because `ANTHROPIC_MODEL` or `CLAUDE_EFFORT` can change what runs without appearing as drift.
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

Limits to state when they matter:

- Transcripts cover only what Claude Code has not pruned, about 30 days by default. Do not confirm or deny a figure older than that.
- `context_tokens` adds cheap cache reads to full-price tokens, so its shares show where context piled up, not cost or limit use.
- The audit reads config files. It does not see managed settings, project `.mcp.json` files or what a running session loaded, so only step 5 shows a setting is in effect.

## 3. Apply the baseline

Plan the change with a small script that prints only baseline keys, because `settings.json` can hold secrets. Show the planned changes and ask before writing.

- Keep every key the baseline does not name.
- Replace scalars, merge objects, and add missing list items after the existing ones, so other deny rules stay.
- Refuse to touch a `settings.json` that is not valid JSON.
- Copy each changed file beside itself as `<name>.bak-<unix-time>`, keeping its mode, and replace the original in one step so a failed write cannot truncate it.
- Add each missing rule to `~/.claude/CLAUDE.md` as a `- ` bullet under a `# Personal preferences` heading, creating the file if needed.

If this machine has deliberately different values, ask rather than overwrite them. Running the same apply twice must change nothing.

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
- When a real setup problem gets past the audit, add the check and an acceptance case to this file.
