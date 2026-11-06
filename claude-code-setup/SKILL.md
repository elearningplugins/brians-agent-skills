---
name: claude-code-setup
description: Sets up Claude Code on a new computer so it works like the one the user is used to - default model, effort levels, the subagent deny rule, global CLAUDE.md rules and MCP servers - then audits the result for drift, overrides, broken MCP entries and plaintext tokens. Use when starting on a new or reinstalled computer, getting Claude Code configured the way the user likes it, or checking that a computer still matches that setup, even if the user never says "setup".
---

# Claude Code Setup

Take a new computer from a fresh Claude Code install to the setup the user is used to, then prove it took effect. The audit is there because a setup can look right and not be: on the machine this came from, a Cursor entry had started `claude` about 250 times a day for weeks, unnoticed. Do not call the setup finished until the audit says so, and change nothing until the user has seen the planned changes.

This skill is one file. Build the audit script from the spec in step 3 each time it is needed, and do not commit it anywhere.

## Before you start

- Claude Code must already be installed and signed in.
- Run `python3 --version` before step 3. On a fresh Mac, `python3` may first need the Xcode command line tools, so have the user install them if it prompts or fails.
- Only macOS has been used so far. On Linux or Windows, say so and check that each path resolves.

## Workflow

```
- [ ] 1. Apply the baseline after showing the planned changes
- [ ] 2. Set up MCP servers
- [ ] 3. Build the audit script and pass the acceptance checks
- [ ] 4. Run it and report, separating measured from inferred
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
- `modelSettings`: medium is the everyday default. The key names one model ID, so it stops applying when Opus moves on and effort silently rises to `xhigh`. Update it when the Opus model ID changes.
- `permissions.deny`: added after a usage report attributed 96% of usage to subagent-heavy sessions.

## Protect secrets

MCP configs often hold plaintext tokens. Do not `Read` or `cat` `~/.cursor/mcp.json`, `~/.claude.json`, `~/.claude/settings.json` or project `.mcp.json` files. Reading one copies the token into the session transcript, and the `Edit` tool keeps pre-edit copies in `~/.claude/file-history`. Both happened while this skill was being written.

- To change a file that may hold a token, use a small script that prints nothing from it, or have the user edit it.
- Have the user run commands containing tokens in a separate terminal. The `!` prefix does not help, because the command and its output land in the conversation.
- Deleting a file does not make a token safe. If a token may be exposed, tell the user plainly, have them revoke it, and name the remaining copies.

## 1. Apply the baseline

Plan the change with a small script that prints only baseline keys, because `settings.json` can hold secrets. Show the planned changes and ask before writing.

- Keep every key the baseline does not name.
- Replace scalars, merge objects, and add missing list items after the existing ones, so other deny rules stay.
- Refuse to touch a `settings.json` that is not valid JSON.
- Copy each changed file beside itself as `<name>.bak-<unix-time>`, keeping its mode, and replace the original in one step so a failed write cannot truncate it.
- Add each missing rule to `~/.claude/CLAUDE.md` as a `- ` bullet under a `# Personal preferences` heading, creating the file if needed.

If this machine has deliberately different values, ask rather than overwrite them. Running the same apply twice must change nothing.

## 2. Set up MCP servers

Add servers with the CLI rather than by editing `~/.claude.json`:

```bash
claude mcp add --scope user --transport http context7 https://mcp.context7.com/mcp
```

Ask which other servers this machine needs. A local server needs its repository cloned and built first:

```bash
claude mcp add --scope user <name> -- node /absolute/path/to/server.js
```

## 3. Build the audit script

Write one Python 3 script, standard library only, to a temporary folder as `audit_setup.py`. It must be read-only: it writes no files and prints only the JSON report. It takes `--home` (default the user's home) and `--project` (default the current folder), and it embeds the baseline above.

### Exit code

| Exit | Meaning |
|---|---|
| 0 | No findings in anything it checks |
| 1 | Any of `settings.drift`, `settings.overrides`, `claude_md.missing_rules` or `mcp.findings` is non-empty |
| 2 | `unreadable_configs` is non-empty, so the report is incomplete. This wins over 1. |

### Report fields

- `version`: output of `claude --version`, or null if it is not installed.
- `billing_type`: `oauthAccount.billingType` from `~/.claude.json`. Print nothing else from `oauthAccount`, which holds the email address.
- `unreadable_configs`: paths among `~/.claude/settings.json`, `~/.claude.json` and `~/.cursor/mcp.json` that exist but do not parse as a JSON object. A corrupt file must never read as an empty one.
- `settings.model`, `settings.effortLevel`, `settings.modelSettings`, `settings.deny`: taken from `~/.claude/settings.json`. Never dump the whole file, because its `env` block can hold secrets.
- `settings.hook_events`: names of the configured hook events only.
- `settings.drift`: a list of `{key, expected, actual}` using dotted keys such as `permissions.deny`. A scalar must be equal. A baseline list only needs its items present, so extra deny rules are not drift.
- `settings.overrides`: for each of `~/.claude/settings.local.json`, `<project>/.claude/settings.json` and `<project>/.claude/settings.local.json` that exists and is not the user settings file itself, `{file, keys}`, where `keys` lists which of `model`, `effortLevel`, `modelSettings` and `permissions` it sets. Use `["unreadable"]` if it does not parse. Omit files that set none. Report key names only, never values.
- `claude_md.missing_rules`: baseline rules whose text does not appear in `~/.claude/CLAUDE.md`.
- `custom_agents`: file stems in `~/.claude/agents/*.md`.
- `env.values`: values of `ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL` and `CLAUDE_EFFORT` when set.
- `env.other_names`: names, never values, of other variables starting with `ANTHROPIC_` or `CLAUDE_`.
- `mcp.servers`: `{source, server, transport}`. Sources are `claude-user` (`mcpServers` in `~/.claude.json`), `cursor-user` (`mcpServers` in `~/.cursor/mcp.json`) and `claude-project:<path>` (each `projects.<path>.mcpServers` in `~/.claude.json`). Transport is `type`, or `http` if there is a `url`, otherwise `stdio`.
- `mcp.findings`: `{source, server, check, detail}`, using the checks below.

### MCP checks

- `bare-claude-command`: the file name of `command` is `claude` and the first two args are not `mcp`, `serve`.
- `missing-path`: `command` or any arg starts with `/` and does not exist. The detail is that path.
- `plaintext-secret`: the detail says where the secret is, never its value, as `headers.<name>`, `env.<name>`, `args[<index>]` or `url`.
  - For `headers` and `env`, flag an entry if its name matches `key|token|secret|password|passwd|credential|authorization|cookie` (case-insensitive) or its value matches a token pattern. Skip values that start with `$` or contain `${`, which reference the environment.
  - Flag an arg if it matches a token pattern.
  - Flag the URL if it matches a token pattern or has a query parameter whose name contains `key`, `token` or `secret`.
  - Token patterns: `gh[pousr]_[A-Za-z0-9]{20,}`, `github_pat_\w{20,}`, `sk-[A-Za-z0-9_-]{20,}`, `xox[abp]-[A-Za-z0-9-]{10,}`, `AKIA[0-9A-Z]{16}`, `Bearer\s+\S{12,}`.

### Acceptance checks

Do not run the script on real config until it passes these on fake homes in the temporary folder. A rebuilt script is untested code, and the first one to read a real token decides whether it leaks. Build the fake token by joining strings so that it is never one literal.

1. An empty home exits 1. A home matching the baseline exactly, including `CLAUDE.md`, exits 0 with empty `settings.drift`.
2. A fake token in a Cursor header and a fake email in `oauthAccount` do not appear anywhere in the output, and a `plaintext-secret` finding names `headers.Authorization`.
3. An `env` value of `${API_KEY}` is not flagged.
4. A corrupt `~/.cursor/mcp.json` exits 2 and is listed in `unreadable_configs`.
5. `claude` with no args is flagged, and `claude mcp serve` is not.
6. A project override reports key names and no values.
7. A home matching the baseline except for a missing `CLAUDE.md` rule exits 1.

## 4. Run and report

Run the script from the project in question. Treat exit 2 as a failed audit, not a clean one.

Lead with the verdict, then cover each area. Mark each claim as **measured** or **inferred**.

- **Config:** `settings.drift`, `settings.overrides` and `claude_md.missing_rules`. Also check `env.values`, because `ANTHROPIC_MODEL` or `CLAUDE_EFFORT` can change what runs without appearing as drift.
- **MCP:** each item in `mcp.findings`.

| Finding | Meaning | Fix |
|---|---|---|
| `bare-claude-command` | A client starts `claude` as an MCP server, which needs the args `mcp serve`. The client retries indefinitely. About 6,100 such runs on one machine got no model reply but left 729 MB of transcripts. | Remove the entry, or set args to `mcp`, `serve`. |
| `missing-path` | A stdio server points at a file that does not exist here, which is common on a new machine. | Clone and build it, then correct the path. |
| `plaintext-secret` | A token is stored in a config file. | Move it to an environment variable. Revoke it if exposed. |
| `settings.overrides` | Another settings file sets a baseline key and can win. | Ask whether it is deliberate. |

The audit reads config files. It does not see managed settings, project `.mcp.json` files or what a running session loaded, so only step 5 shows a setting is in effect.

## 5. Verify

1. Fix what the audit found, then run it again and confirm it exits 0, or that every remaining finding is one the user chose to keep.
2. Start a new session, because running sessions keep their old settings. Confirm the `Agent` tool is unavailable and the model and effort are as expected.
3. For a removed MCP entry, reload the client (in Cursor, **Developer: Reload Window**).

## Honesty rules

- Never report "no findings" from an audit that exited 2.
- Do not paste audit output into public places: it holds local paths and server names.
- When a real setup problem gets past the audit, add the check and an acceptance case to this file.
