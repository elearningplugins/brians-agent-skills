#!/usr/bin/env python3
"""Delete transcripts left by MCP handshakes that no model answered, as a dry run unless --delete is passed."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from audit_setup import is_handshake_transcript, read_entries, transcript_files


def find_targets(projects: Path, min_age_seconds: int) -> list[Path]:
    """Return handshake transcripts old enough that no running process still writes them."""
    now = time.time()
    targets = []
    for path in transcript_files(projects):
        if now - path.stat().st_mtime >= min_age_seconds and is_handshake_transcript(read_entries(path)):
            targets.append(path)
    return targets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory to clean")
    parser.add_argument("--min-age-seconds", type=int, default=120)
    parser.add_argument("--delete", action="store_true", help="delete the matches; omitted means dry run")
    args = parser.parse_args()
    targets = find_targets(args.home / ".claude" / "projects", args.min_age_seconds)
    size = sum(path.stat().st_size for path in targets)
    print(f"{len(targets)} handshake transcripts, {size / 1_000_000:.1f} MB")
    if args.delete:
        for path in targets:
            path.unlink()
        print(f"deleted {len(targets)}")
    else:
        print("dry run: nothing deleted; pass --delete to remove them")


if __name__ == "__main__":
    main()
