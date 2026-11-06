#!/usr/bin/env python3
"""Merge the baseline into ~/.claude/settings.json and CLAUDE.md, as a dry run unless --write is passed."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from audit_setup import missing_rules

SKILL_DIR = Path(__file__).resolve().parent.parent


def merge(current: dict, baseline: dict, prefix: str = "") -> tuple[dict, list[str]]:
    """Overlay baseline onto current: objects merge, lists gain missing items, and scalars are replaced."""
    merged = dict(current)
    changes = []
    for key, value in baseline.items():
        dotted = f"{prefix}{key}"
        existing = merged.get(key)
        if isinstance(value, dict):
            child, child_changes = merge(existing if isinstance(existing, dict) else {}, value, f"{dotted}.")
            merged[key] = child
            changes.extend(child_changes)
        elif isinstance(value, list):
            present = existing if isinstance(existing, list) else []
            missing = [item for item in value if item not in present]
            if missing:
                merged[key] = [*present, *missing]
                changes.append(f"{dotted}: add {json.dumps(missing)}")
        elif existing != value:
            merged[key] = value
            changes.append(f"{dotted}: {json.dumps(existing)} -> {json.dumps(value)}")
    return merged, changes


def backup(path: Path) -> Path:
    """Copy a file beside itself with a timestamp, keeping its mode."""
    target = path.with_name(f"{path.name}.bak-{int(time.time())}")
    shutil.copy2(path, target)
    return target


def write_atomic(path: Path, text: str) -> None:
    """Replace a file in one step so a failed write cannot truncate it."""
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(text)
    os.chmod(temp_name, mode)
    os.replace(temp_name, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory to update")
    parser.add_argument("--baseline", type=Path, default=SKILL_DIR / "assets" / "baseline.json")
    parser.add_argument("--write", action="store_true", help="apply the changes; omitted means dry run")
    args = parser.parse_args()

    settings_path = args.home / ".claude" / "settings.json"
    claude_md_path = args.home / ".claude" / "CLAUDE.md"
    current = {}
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8"))
        except ValueError as error:
            print(f"refusing to change invalid JSON in {settings_path}: {error}", file=sys.stderr)
            return 2
        if not isinstance(current, dict):
            print(f"refusing to change {settings_path}: top level is not an object", file=sys.stderr)
            return 2

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    merged, changes = merge(current, baseline["settings"])
    existing_md = claude_md_path.read_text(encoding="utf-8") if claude_md_path.exists() else ""
    rules = missing_rules(existing_md, baseline["claude_md_rules"])

    for change in changes:
        print(f"settings.json {change}")
    for rule in rules:
        print(f"CLAUDE.md add: - {rule}")
    if not changes and not rules:
        print("already matches the baseline")
        return 0
    if not args.write:
        print("dry run: nothing changed; pass --write to apply")
        return 0

    if changes:
        if settings_path.exists():
            print(f"backup: {backup(settings_path)}")
        write_atomic(settings_path, json.dumps(merged, indent=2) + "\n")
    if rules:
        if claude_md_path.exists():
            print(f"backup: {backup(claude_md_path)}")
        separator = "" if not existing_md or existing_md.endswith("\n") else "\n"
        heading = "" if existing_md else "# Personal preferences\n\n"
        write_atomic(claude_md_path, existing_md + separator + heading + "".join(f"- {rule}\n" for rule in rules))
    print("applied; new Claude Code sessions pick this up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
