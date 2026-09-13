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


def _advice_codes() -> tuple[str, ...]:
    """Return the advice codes the rules can emit, read without importing Home Assistant."""
    sys.path.insert(0, str(ROOT.parent.parent))
    from custom_components.hosekeeper.engine.rules import ADVICE_CODES

    return ADVICE_CODES


def _next_action_states(path: Path) -> set[str]:
    data = json.loads(path.read_text())
    return set(data["entity"]["sensor"]["next_action"]["state"])


def main() -> int:
    """Return 1 when any translation disagrees with strings.json."""
    source = _keys(json.loads((ROOT / "strings.json").read_text()))
    failed = False

    # Every code the rules can emit has to be a state the sensor can name. The sensor declares
    # ADVICE_CODES as its options, so a code with no entry here reaches a dashboard and a
    # notification as its raw identifier -- "mow_by_hand_while_seed_roots", in front of
    # somebody who wanted to know what to do this afternoon. Three had slipped through.
    states = _next_action_states(ROOT / "strings.json")
    for missing in sorted(set(_advice_codes()) - states):
        print(f"  strings.json: next_action has no state for advice code {missing}")
        failed = True

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
