#!/usr/bin/env python3
"""Read-only audit of a local Claude Code setup that prints JSON and never prints secret values."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SECRET_NAME = re.compile(r"key|token|secret|password|passwd|credential|authorization|cookie", re.I)
SECRET_VALUE = re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|sk-[A-Za-z0-9_-]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|Bearer\s+\S{12,}")
SECRET_QUERY = re.compile(r"[?&][^=&]*(key|token|secret)[^=&]*=[^&]+", re.I)
INITIALIZE = re.compile(r'"method"\s*:\s*"initialize"')
VISIBLE_ENV = {"ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_EFFORT"}
ENV_PREFIXES = ("ANTHROPIC_", "CLAUDE_")
SYNTHETIC_MODEL = "<synthetic>"


def load_json(path: Path) -> dict | None:
    """Return parsed JSON, or None when the file is missing or invalid."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def lookup(data: dict, dotted: str):
    """Follow a dotted key path, returning None when any part is absent."""
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def flatten(baseline: dict, prefix: str = "") -> dict:
    """Flatten nested baseline objects into dotted keys, keeping lists whole."""
    flat = {}
    for key, value in baseline.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{dotted}."))
        else:
            flat[dotted] = value
    return flat


def config_drift(settings: dict, baseline: dict) -> list[dict]:
    """List baseline values that the settings do not match; a list only needs its baseline items present."""
    drift = []
    for key, expected in flatten(baseline).items():
        actual = lookup(settings, key)
        if isinstance(expected, list):
            present = actual if isinstance(actual, list) else []
            if any(item not in present for item in expected):
                drift.append({"key": key, "expected": expected, "actual": actual})
        elif actual != expected:
            drift.append({"key": key, "expected": expected, "actual": actual})
    return drift


def secret_locations(server: dict) -> list[str]:
    """Name where a server config holds a plaintext secret, without returning the value."""
    found = []
    for section in ("headers", "env"):
        for name, value in (server.get(section) or {}).items():
            text = str(value)
            references_env = text.startswith("$") or "${" in text
            if not references_env and (SECRET_NAME.search(name) or SECRET_VALUE.search(text)):
                found.append(f"{section}.{name}")
    for index, arg in enumerate(server.get("args") or []):
        if SECRET_VALUE.search(str(arg)):
            found.append(f"args[{index}]")
    url = str(server.get("url") or "")
    if SECRET_QUERY.search(url) or SECRET_VALUE.search(url):
        found.append("url")
    return found


def mcp_findings(source: str, name: str, server: dict) -> list[dict]:
    """Check one MCP server definition for a bare claude command, missing paths and plaintext secrets."""
    findings = []
    command = str(server.get("command") or "")
    args = [str(arg) for arg in server.get("args") or []]
    if Path(command).name == "claude" and args[:2] != ["mcp", "serve"]:
        findings.append({"source": source, "server": name, "check": "bare-claude-command", "detail": "claude is not an MCP server without the args mcp serve; each client retry starts a failed session"})
    for value in [command, *args]:
        if value.startswith("/") and not Path(value).exists():
            findings.append({"source": source, "server": name, "check": "missing-path", "detail": value})
    for location in secret_locations(server):
        findings.append({"source": source, "server": name, "check": "plaintext-secret", "detail": location})
    return findings


def mcp_report(home: Path) -> dict:
    """Summarize Claude Code and Cursor MCP servers by name and transport only."""
    claude_json = load_json(home / ".claude.json") or {}
    cursor_json = load_json(home / ".cursor" / "mcp.json") or {}
    sources = [("claude-user", claude_json.get("mcpServers") or {}), ("cursor-user", cursor_json.get("mcpServers") or {})]
    for project, config in (claude_json.get("projects") or {}).items():
        if isinstance(config, dict) and config.get("mcpServers"):
            sources.append((f"claude-project:{project}", config["mcpServers"]))
    servers, findings = [], []
    for source, entries in sources:
        for name, server in entries.items():
            if not isinstance(server, dict):
                continue
            transport = server.get("type") or ("http" if server.get("url") else "stdio")
            servers.append({"source": source, "server": name, "transport": transport})
            findings.extend(mcp_findings(source, name, server))
    return {"servers": servers, "findings": findings}


def read_entries(path: Path) -> list[dict]:
    """Parse a JSONL transcript, skipping lines that are not JSON objects."""
    entries = []
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    entries.append(entry)
    except OSError:
        return []
    return entries


def first_user_text(entries: list[dict]) -> str:
    """Return the first user message as plain text."""
    for entry in entries:
        message = entry.get("message")
        if entry.get("type") == "user" and isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
            return " ".join(block.get("text", "") for block in content or [] if isinstance(block, dict))
    return ""


def has_real_reply(entries: list[dict]) -> bool:
    """Report whether a model replied, since synthetic messages are local placeholders."""
    for entry in entries:
        message = entry.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant" and message.get("model") != SYNTHETIC_MODEL:
            return True
    return False


def is_handshake_transcript(entries: list[dict]) -> bool:
    """Match a session whose whole first prompt is an MCP handshake and that no model answered."""
    text = first_user_text(entries).strip()
    return text.startswith("{") and bool(INITIALIZE.search(text)) and "clientInfo" in text and not has_real_reply(entries)


def session_usage(entries: list[dict]) -> dict:
    """Total one session's usage, deduped by message id because each content block repeats its usage."""
    by_id, models, agent_calls = {}, Counter(), Counter()
    seen_calls = set()
    for entry in entries:
        message = entry.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant" or message.get("model") == SYNTHETIC_MODEL:
            continue
        message_id = message.get("id") or entry.get("uuid")
        by_id[message_id] = message
        for block in message.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in ("Agent", "Task") and block.get("id") not in seen_calls:
                seen_calls.add(block.get("id"))
                tool_input = block.get("input") or {}
                agent_calls[f"{tool_input.get('subagent_type', 'default')}/{tool_input.get('model', 'inherit')}"] += 1
    total = {"requests": len(by_id), "output_tokens": 0, "context_tokens": 0, "peak_context": 0}
    for message in by_id.values():
        models[message.get("model") or "unknown"] += 1
        usage = message.get("usage") or {}
        context = sum(usage.get(key, 0) or 0 for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        total["output_tokens"] += usage.get("output_tokens", 0) or 0
        total["context_tokens"] += context
        total["peak_context"] = max(total["peak_context"], context)
    return {**total, "models": models, "agent_calls": agent_calls}


def transcript_files(projects: Path) -> list[Path]:
    """List every transcript, including subagent transcripts in nested folders."""
    return sorted(projects.rglob("*.jsonl")) if projects.is_dir() else []


def usage_report(projects: Path, days: int) -> dict:
    """Aggregate usage from transcripts changed within the window."""
    cutoff = time.time() - days * 86400
    models, agent_calls = Counter(), Counter()
    sessions = []
    handshake_files = handshake_bytes = subagent_transcripts = 0
    for path in transcript_files(projects):
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime < cutoff:
            continue
        entries = read_entries(path)
        if is_handshake_transcript(entries):
            handshake_files += 1
            handshake_bytes += stat.st_size
            continue
        if "subagents" in path.parts or path.name.startswith("agent-") or any(entry.get("isSidechain") for entry in entries):
            subagent_transcripts += 1
        usage = session_usage(entries)
        models.update(usage.pop("models"))
        agent_calls.update(usage.pop("agent_calls"))
        if usage["requests"]:
            sessions.append({"session": path.stem[:8], **usage})
    sessions.sort(key=lambda item: item["context_tokens"], reverse=True)
    all_context = sum(item["context_tokens"] for item in sessions) or 1
    all_requests = sum(item["requests"] for item in sessions)
    top = []
    running = 0
    for item in sessions[:5]:
        running += item["context_tokens"]
        top.append({**item, "average_context": item["context_tokens"] // item["requests"], "cumulative_share_pct": round(100 * running / all_context)})
    return {
        "window_days": days,
        "sessions": len(sessions),
        "requests": all_requests,
        "average_context_per_request": sum(item["context_tokens"] for item in sessions) // max(all_requests, 1),
        "requests_by_model": dict(models.most_common()),
        "subagent_calls": dict(agent_calls.most_common()),
        "subagent_transcripts": subagent_transcripts,
        "top_sessions": top,
        "handshake_transcripts": {"files": handshake_files, "bytes": handshake_bytes},
    }


def env_report() -> dict:
    """Show model-related env values and only the names of everything else."""
    visible, names = {}, []
    for name, value in sorted(os.environ.items()):
        if name in VISIBLE_ENV:
            visible[name] = value
        elif name.startswith(ENV_PREFIXES):
            names.append(name)
    return {"values": visible, "other_names": names}


def cli_version() -> str | None:
    """Return the installed Claude Code version, or None when it is not on PATH."""
    binary = shutil.which("claude")
    if not binary:
        return None
    try:
        return subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=20).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def audit(home: Path, baseline: dict, days: int) -> dict:
    """Build the full report from one home directory."""
    settings_path = home / ".claude" / "settings.json"
    settings = load_json(settings_path)
    account = (load_json(home / ".claude.json") or {}).get("oauthAccount") or {}
    agents = home / ".claude" / "agents"
    return {
        "version": cli_version(),
        "billing_type": account.get("billingType"),
        "settings": {
            "exists": settings_path.exists(),
            "valid": settings is not None,
            "model": (settings or {}).get("model"),
            "effortLevel": (settings or {}).get("effortLevel"),
            "modelSettings": (settings or {}).get("modelSettings"),
            "deny": lookup(settings or {}, "permissions.deny"),
            "hook_events": sorted((settings or {}).get("hooks") or {}),
            "drift": config_drift(settings or {}, baseline),
        },
        "custom_agents": sorted(path.stem for path in agents.glob("*.md")) if agents.is_dir() else [],
        "env": env_report(),
        "mcp": mcp_report(home),
        "usage": usage_report(home / ".claude" / "projects", days),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory to audit")
    parser.add_argument("--baseline", type=Path, default=SKILL_DIR / "assets" / "baseline-settings.json")
    parser.add_argument("--days", type=int, default=30, help="usage window in days")
    args = parser.parse_args()
    baseline = load_json(args.baseline)
    if baseline is None:
        parser.error(f"cannot read baseline {args.baseline}")
    print(json.dumps(audit(args.home, baseline, args.days), indent=2))


if __name__ == "__main__":
    main()
