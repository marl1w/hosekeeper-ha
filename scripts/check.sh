#!/usr/bin/env bash
#
# Local stand-in for CI.
#
#   ./scripts/check.sh          # lint + format + tests + frontend parse
#   ./scripts/check.sh --setup  # create .venv and install test dependencies first
#
# Home Assistant 2026.3+ requires Python 3.14.2 or newer. If your default python3 is
# older, point PYTHON at a newer one:
#
#   PYTHON="$(pyenv root)/versions/3.14.6/bin/python3" ./scripts/check.sh --setup

set -euo pipefail

cd "$(dirname "$0")/.."
VENV=".venv"
FAILED=0

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
ok() { printf '\033[32m  ok\033[0m %s\n' "$1"; }
bad() {
  printf '\033[31m  FAILED\033[0m %s\n' "$1"
  FAILED=1
}

if [[ "${1:-}" == "--setup" ]]; then
  PYTHON="${PYTHON:-python3}"
  step "Creating $VENV with $("$PYTHON" --version)"
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip
  "$VENV/bin/pip" install -r requirements-test.txt ruff
  echo
  echo "Done. Now run ./scripts/check.sh"
  exit 0
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "No $VENV found. Run: ./scripts/check.sh --setup"
  exit 1
fi

PY="$VENV/bin/python"

step "Ruff lint"
if "$PY" -m ruff check .; then ok "lint"; else bad "lint"; fi

step "Ruff format"
if "$PY" -m ruff format --check .; then ok "format"; else bad "format"; fi

step "Translations"
# strings.json is the source of truth; a key missing from a translation renders as a raw
# identifier in that language, and a key present only in a translation is dead weight.
if "$PY" scripts/check_translations.py; then ok "translations"; else bad "translations"; fi

step "Tests"
if "$PY" -m pytest tests -q; then ok "tests"; else bad "tests"; fi

step "Frontend modules parse"
FRONTEND="custom_components/hosekeeper/frontend"
if [[ -d "$FRONTEND" ]] && command -v node >/dev/null 2>&1; then
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  PARSE_FAILED=0
  while IFS= read -r file; do
    cp "$file" "$TMP/$(basename "${file%.js}").mjs"
    node --check "$TMP/$(basename "${file%.js}").mjs" || PARSE_FAILED=1
  done < <(find "$FRONTEND" -name '*.js')
  if [[ $PARSE_FAILED -eq 0 ]]; then ok "frontend"; else bad "frontend"; fi
  for suite in tests/frontend/test_*.mjs; do
    [[ -e "$suite" ]] || continue
    if node "$suite"; then ok "$(basename "$suite")"; else bad "$(basename "$suite")"; fi
  done
else
  printf '  skipped (no frontend yet, or node not installed)\n'
fi

echo
if [[ $FAILED -eq 0 ]]; then
  printf '\033[32mAll checks passed.\033[0m\n'
else
  printf '\033[31mSomething failed — see above.\033[0m\n'
  exit 1
fi
