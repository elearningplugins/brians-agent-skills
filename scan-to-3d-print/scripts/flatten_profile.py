"""Flattens a Bambu Studio system profile by merging its inherits chain, then applies key=value overrides."""
import json
import pathlib
import sys

root = pathlib.Path("/Applications/BambuStudio.app/Contents/Resources/profiles/BBL")
kind, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
by_name = {}
for f in (root / kind).glob("*.json"):
    try:
        d = json.loads(f.read_text())
    except Exception:
        continue
    by_name[d.get("name", f.stem)] = d
chain = []
cur = by_name[name]
while True:
    chain.append(cur)
    parent = cur.get("inherits")
    if not parent:
        break
    cur = by_name[parent]
merged = {}
for d in reversed(chain):
    merged.update(d)
merged.pop("inherits", None)
merged["name"] = name
merged["from"] = "system"
for kv in sys.argv[4:]:
    k, v = kv.split("=", 1)
    merged[k] = v
pathlib.Path(out).write_text(json.dumps(merged, indent=2))
print(out, len(merged), "keys from", " <- ".join(d["name"] for d in chain))
