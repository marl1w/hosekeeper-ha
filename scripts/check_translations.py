"""Compare strings.json with every translation file, key by key.

The two must have exactly the same shape: Home Assistant renders a missing key as its raw
identifier, and a key only a translation knows about is a string nobody will ever see.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "hosekeeper"


def _keys(node: object, prefix: str = "") -> set[str]:
    if not isinstance(node, dict):
        return {prefix}
    out: set[str] = set()
    for key, value in node.items():
        out |= _keys(value, f"{prefix}.{key}" if prefix else key)
    return out


def main() -> int:
    """Return 1 when any translation disagrees with strings.json."""
    source = _keys(json.loads((ROOT / "strings.json").read_text()))
    failed = False
    for path in sorted((ROOT / "translations").glob("*.json")):
        keys = _keys(json.loads(path.read_text()))
        for missing in sorted(source - keys):
            print(f"  {path.name}: missing {missing}")
            failed = True
        for extra in sorted(keys - source):
            print(f"  {path.name}: not in strings.json: {extra}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
