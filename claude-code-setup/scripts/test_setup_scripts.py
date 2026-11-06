"""Tests for the setup audit, baseline merge and transcript cleanup, using a fake home directory."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import apply_baseline  # noqa: E402
import audit_setup  # noqa: E402
import clean_handshake_transcripts  # noqa: E402

# Built by concatenation so secret scanners do not flag a fake token.
FAKE_TOKEN = "ghp_" + "a1B2c3D4" * 5
HANDSHAKE = '{"method":"initialize","params":{"clientInfo":{"name":"some-editor"}},"jsonrpc":"2.0","id":0}'
BASELINE = {"model": "opus", "modelSettings": {"m1": {"effortLevel": "medium"}}, "permissions": {"deny": ["Task", "Agent"]}}


def user_line(text):
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def reply_line(message_id, model="claude-test", cache_read=100, output=10, content=None):
    return json.dumps({"type": "assistant", "message": {"id": message_id, "role": "assistant", "model": model, "content": content or [], "usage": {"input_tokens": 1, "cache_read_input_tokens": cache_read, "output_tokens": output}}})


def write_session(home, name, lines, project="-proj"):
    path = home / ".claude" / "projects" / project / f"{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    old = time.time() - 3600
    os.utime(path, (old, old))
    return path


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True, cwd=SCRIPTS)


def test_drift_reports_mismatch_and_accepts_extra_deny_items():
    settings = {"model": "sonnet", "modelSettings": {"m1": {"effortLevel": "medium"}}, "permissions": {"deny": ["Bash(rm:*)", "Task", "Agent"]}}
    assert audit_setup.config_drift(settings, BASELINE) == [{"key": "model", "expected": "opus", "actual": "sonnet"}]


def test_drift_flags_missing_deny_item():
    settings = {"model": "opus", "modelSettings": {"m1": {"effortLevel": "medium"}}, "permissions": {"deny": ["Task"]}}
    assert [item["key"] for item in audit_setup.config_drift(settings, BASELINE)] == ["permissions.deny"]


@pytest.mark.parametrize("server,flagged", [
    ({"command": "claude"}, True),
    ({"command": "/usr/local/bin/claude", "args": ["--verbose"]}, True),
    ({"command": "claude", "args": ["mcp", "serve"]}, False),
    ({"command": "npx", "args": ["some-mcp"]}, False),
])
def test_bare_claude_command(server, flagged):
    checks = [item["check"] for item in audit_setup.mcp_findings("cursor-user", "s", server)]
    assert ("bare-claude-command" in checks) is flagged


def test_missing_stdio_path_is_reported(tmp_path):
    findings = audit_setup.mcp_findings("x", "s", {"command": "node", "args": [str(tmp_path / "gone.js")]})
    assert [item["check"] for item in findings] == ["missing-path"]


@pytest.mark.parametrize("server,expected", [
    ({"url": "https://x", "headers": {"Authorization": FAKE_TOKEN}}, ["headers.Authorization"]),
    ({"command": "x", "env": {"API_KEY": "abc"}}, ["env.API_KEY"]),
    ({"command": "x", "env": {"NOTES": FAKE_TOKEN}}, ["env.NOTES"]),
    ({"command": "x", "args": ["--token", FAKE_TOKEN]}, ["args[1]"]),
    ({"url": "https://x/mcp?api_key=abc"}, ["url"]),
    ({"command": "x", "env": {"API_KEY": "${API_KEY}"}}, []),
    ({"command": "x", "env": {"SEARCH_PROVIDER": "scrape"}}, []),
])
def test_secret_locations(server, expected):
    assert audit_setup.secret_locations(server) == expected


def test_audit_output_never_contains_secret_values(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text(json.dumps({"mcpServers": {"github": {"url": "https://x", "headers": {"Authorization": FAKE_TOKEN}}}}), encoding="utf-8")
    (tmp_path / ".claude.json").write_text(json.dumps({"oauthAccount": {"emailAddress": "person@example.com", "billingType": "stripe_subscription"}, "mcpServers": {"a": {"command": "x", "env": {"API_KEY": FAKE_TOKEN}}}}), encoding="utf-8")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text(json.dumps({"env": {"API_KEY": FAKE_TOKEN}}), encoding="utf-8")
    result = run_script("audit_setup.py", "--home", str(tmp_path), "--project", str(tmp_path))
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert FAKE_TOKEN not in result.stdout and "person@example.com" not in result.stdout
    assert {item["detail"] for item in report["mcp"]["findings"]} == {"headers.Authorization", "env.API_KEY"}


def test_usage_dedupes_blocks_and_ignores_synthetic(tmp_path):
    line = reply_line("m1", cache_read=1000, output=50)
    write_session(tmp_path, "real", [user_line("hello"), line, line, line, reply_line("s1", model="<synthetic>")])
    usage = audit_setup.usage_report(tmp_path / ".claude" / "projects", 30)
    assert usage["requests"] == 1
    assert usage["requests_by_model"] == {"claude-test": 1}
    assert usage["top_sessions"][0]["context_tokens"] == 1001
    assert usage["top_sessions"][0]["output_tokens"] == 50


def test_usage_keeps_cheap_and_full_price_tokens_separate(tmp_path):
    write_session(tmp_path, "real", [user_line("hello"), reply_line("m1", cache_read=1000, output=50)])
    tokens = audit_setup.usage_report(tmp_path / ".claude" / "projects", 30)["tokens"]
    assert tokens == {"input_tokens": 1, "cache_read_tokens": 1000, "cache_write_tokens": 0, "output_tokens": 50}


def test_unreadable_transcript_is_counted_not_skipped_silently(tmp_path):
    write_session(tmp_path, "real", [user_line("hello"), reply_line("m1")])
    (tmp_path / ".claude" / "projects" / "-proj" / "broken.jsonl").mkdir()
    assert audit_setup.usage_report(tmp_path / ".claude" / "projects", 30)["unreadable_transcripts"] == 1


def test_usage_counts_subagent_calls_and_nested_transcripts(tmp_path):
    call = [{"type": "tool_use", "id": "t1", "name": "Agent", "input": {"subagent_type": "Explore", "model": "haiku"}}]
    line = reply_line("m1", content=call)
    write_session(tmp_path, "main", [user_line("go"), line, line])
    write_session(tmp_path, "sub", [user_line("task"), reply_line("m2")], project="-proj/main/subagents")
    usage = audit_setup.usage_report(tmp_path / ".claude" / "projects", 30)
    assert usage["subagent_calls"] == {"Explore/haiku": 1}
    assert usage["subagent_transcripts"] == 1


def test_usage_window_excludes_old_transcripts(tmp_path):
    path = write_session(tmp_path, "old", [user_line("hello"), reply_line("m1")])
    ancient = time.time() - 40 * 86400
    os.utime(path, (ancient, ancient))
    assert audit_setup.usage_report(tmp_path / ".claude" / "projects", 30)["requests"] == 0


@pytest.mark.parametrize("lines,expected", [
    ([user_line(HANDSHAKE)], True),
    ([user_line(HANDSHAKE), reply_line("s1", model="<synthetic>")], True),
    ([user_line([{"type": "text", "text": HANDSHAKE}])], True),
    ([user_line(HANDSHAKE), reply_line("m1")], False),
    ([user_line("explain how the MCP initialize method and clientInfo work")], False),
    ([user_line(f"why did this message fail? {HANDSHAKE}")], False),
    ([], False),
])
def test_is_handshake_transcript(tmp_path, lines, expected):
    path = write_session(tmp_path, "s", lines)
    assert audit_setup.is_handshake_transcript(audit_setup.read_entries(path)) is expected


def test_cleanup_dry_run_keeps_and_delete_removes_only_handshakes(tmp_path):
    empty = write_session(tmp_path, "empty", [user_line(HANDSHAKE)])
    real = write_session(tmp_path, "real", [user_line(HANDSHAKE), reply_line("m1")])
    dry = run_script("clean_handshake_transcripts.py", "--home", str(tmp_path))
    assert "1 handshake transcripts" in dry.stdout and empty.exists()
    run_script("clean_handshake_transcripts.py", "--home", str(tmp_path), "--delete")
    assert not empty.exists() and real.exists()


def test_cleanup_skips_recent_files(tmp_path):
    path = write_session(tmp_path, "new", [user_line(HANDSHAKE)])
    os.utime(path, None)
    assert clean_handshake_transcripts.find_targets(tmp_path / ".claude" / "projects", 120) == []


def test_merge_keeps_unrelated_keys_and_existing_deny_order():
    current = {"theme": "dark", "modelSettings": {"m2": {"effortLevel": "low"}}, "permissions": {"deny": ["Bash(rm:*)", "Task"], "allow": ["Read"]}}
    merged, changes = apply_baseline.merge(current, BASELINE)
    assert merged["theme"] == "dark"
    assert merged["modelSettings"] == {"m2": {"effortLevel": "low"}, "m1": {"effortLevel": "medium"}}
    assert merged["permissions"] == {"deny": ["Bash(rm:*)", "Task", "Agent"], "allow": ["Read"]}
    assert len(changes) == 3


def test_merge_is_idempotent():
    merged, _ = apply_baseline.merge({}, BASELINE)
    assert apply_baseline.merge(merged, BASELINE) == (merged, [])


def make_assets(tmp_path):
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(BASELINE), encoding="utf-8")
    rules = tmp_path / "rules.md"
    rules.write_text("# Personal preferences\n\n- Keep comments short.\n", encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    return home, ["--home", str(home), "--baseline", str(baseline), "--claude-md", str(rules)]


def test_apply_dry_run_changes_nothing(tmp_path):
    home, args = make_assets(tmp_path)
    settings = home / ".claude" / "settings.json"
    settings.write_text('{"model": "sonnet"}', encoding="utf-8")
    result = run_script("apply_baseline.py", *args)
    assert "dry run" in result.stdout
    assert settings.read_text(encoding="utf-8") == '{"model": "sonnet"}'
    assert not (home / ".claude" / "CLAUDE.md").exists()


def test_apply_write_backs_up_and_second_run_is_clean(tmp_path):
    home, args = make_assets(tmp_path)
    settings = home / ".claude" / "settings.json"
    settings.write_text('{"model": "sonnet", "theme": "dark"}', encoding="utf-8")
    os.chmod(settings, 0o600)
    (home / ".claude" / "CLAUDE.md").write_text("# Mine", encoding="utf-8")
    assert run_script("apply_baseline.py", *args, "--write").returncode == 0
    written = json.loads(settings.read_text(encoding="utf-8"))
    assert written["model"] == "opus" and written["theme"] == "dark"
    assert settings.stat().st_mode & 0o777 == 0o600
    assert (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == "# Mine\n- Keep comments short.\n"
    assert len(list((home / ".claude").glob("settings.json.bak-*"))) == 1
    assert "already matches" in run_script("apply_baseline.py", *args, "--write").stdout
    assert len(list((home / ".claude").glob("*.bak-*"))) == 2


def test_apply_refuses_invalid_settings(tmp_path):
    home, args = make_assets(tmp_path)
    settings = home / ".claude" / "settings.json"
    settings.write_text("{not json", encoding="utf-8")
    assert run_script("apply_baseline.py", *args, "--write").returncode == 2
    assert settings.read_text(encoding="utf-8") == "{not json"


@pytest.mark.parametrize("overrides,used,expected", [
    ({"m1": {}}, {"m1": 5}, []),
    ({}, {"m1": 5}, [("no-effort-override", "m1")]),
    ({"old": {}, "m1": {}}, {"m1": 5}, [("unused-effort-override", "old")]),
    ({"old": {}}, {"m1": 5, "m2": 1}, [("no-effort-override", "m1"), ("unused-effort-override", "old")]),
    ({"m1": {}}, {"m1": 5, "m2": 1}, []),
    ({"m1": {}}, {}, []),
    ({"m1": {}}, {"unknown": 3}, []),
])
def test_effort_findings(overrides, used, expected):
    findings = audit_setup.effort_findings({"modelSettings": overrides}, used)
    assert [(item["check"], item["detail"]) for item in findings] == expected


def test_overrides_report_key_names_only(tmp_path):
    project = tmp_path / "repo"
    (project / ".claude").mkdir(parents=True)
    (project / ".claude" / "settings.local.json").write_text(json.dumps({"model": "sonnet", "env": {"API_KEY": FAKE_TOKEN}}), encoding="utf-8")
    assert audit_setup.settings_overrides(tmp_path, project) == [{"file": str(project / ".claude" / "settings.local.json"), "keys": ["model"]}]


def test_overrides_flag_corrupt_file_and_skip_the_user_file_itself(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text('{"model": "opus"}', encoding="utf-8")
    assert audit_setup.settings_overrides(tmp_path, tmp_path) == []
    (tmp_path / ".claude" / "settings.local.json").write_text("{bad", encoding="utf-8")
    assert audit_setup.settings_overrides(tmp_path, tmp_path)[0]["keys"] == ["unreadable"]


def test_corrupt_mcp_config_fails_instead_of_reading_as_empty(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".cursor" / "mcp.json").write_text("{bad", encoding="utf-8")
    result = run_script("audit_setup.py", "--home", str(tmp_path), "--project", str(tmp_path))
    assert result.returncode == 2
    assert json.loads(result.stdout)["unreadable_configs"] == [str(tmp_path / ".cursor" / "mcp.json")]


def test_new_computer_goes_from_failing_audit_to_clean_after_apply(tmp_path):
    audit_args = ["--home", str(tmp_path), "--project", str(tmp_path)]
    assert run_script("audit_setup.py", *audit_args).returncode == 1
    assert run_script("apply_baseline.py", "--home", str(tmp_path), "--write").returncode == 0
    result = run_script("audit_setup.py", *audit_args)
    assert result.returncode == 0, result.stdout
    assert json.loads(result.stdout)["settings"]["drift"] == []
    assert "single line" in (tmp_path / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
