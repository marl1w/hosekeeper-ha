# Every way of running this project, in one place. `make` on its own lists what there is.
#
#   make setup     once, or after a Python upgrade
#   make check     what CI runs
#
# Home Assistant 2026.3+ needs Python 3.14.2 or newer. If the default python3 is older:
#
#   make setup PYTHON=$$(pyenv root)/versions/3.14.6/bin/python3

VENV    ?= .venv
PYTHON  ?= python3
PY      := $(VENV)/bin/python
ARGS    ?=
PORT    ?= 8123
SEED    ?= 1
LOCALE  ?= en
DATE    ?=

ifneq ($(shell test -t 1 && echo tty),)
  BOLD := \033[1m
  DIM  := \033[2m
  OFF  := \033[0m
else
  BOLD :=
  DIM  :=
  OFF  :=
endif

.DEFAULT_GOAL := help
.PHONY: help setup check lint format format-check translations test frontend preview replay stats validate clean distclean venv-check

help: ## List the targets
	@printf '$(BOLD)Hosekeeper$(OFF)\n\n'
	@grep -hE '^[a-z][a-z-]*:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "} {printf "  $(BOLD)%-16s$(OFF) %s\n", $$1, $$2}'
	@printf '\n$(DIM)Variables: ARGS=<extra pytest args> PORT=%s SEED=%s LOCALE=%s DATE=YYYY-MM-DD$(OFF)\n\n' "$(PORT)" "$(SEED)" "$(LOCALE)"

setup: ## Create the virtualenv and install the test dependencies
	@scripts/check.sh --setup

venv-check:
	@test -x $(PY) || { \
	  printf '$(BOLD)No virtualenv at $(VENV)$(OFF)\n  Run: make setup\n'; exit 1; }

check: ## Everything CI runs: lint, format, translations, tests, frontend
	@scripts/check.sh

lint: venv-check ## Ruff lint
	@$(PY) -m ruff check .

format: venv-check ## Ruff format, writing the files
	@$(PY) -m ruff format .

format-check: venv-check ## Ruff format, reporting only
	@$(PY) -m ruff format --check .

translations: venv-check ## strings.json and every translation agree
	@$(PY) scripts/check_translations.py && printf '  translations agree\n'

test: venv-check ## The Python test suite (ARGS passes through to pytest)
	@$(PY) -m pytest tests -q $(ARGS)

frontend: ## The panel's own checks: modules parse, pure-logic suites
	@command -v node >/dev/null 2>&1 || { echo "node is not installed"; exit 1; }
	@set -e; for file in $$(find custom_components/hosekeeper/frontend -name '*.js' 2>/dev/null); do \
	  cp "$$file" "/tmp/$$(basename $${file%.js}).mjs"; \
	  node --check "/tmp/$$(basename $${file%.js}).mjs"; \
	done; printf '  modules parse\n'
	@for suite in tests/frontend/test_*.mjs; do [ -e "$$suite" ] && node "$$suite"; done; true

replay: venv-check ## Replay real weather: make replay ARGS="--open-meteo --established 2026-06-06"
	@$(PY) scripts/replay.py $(if $(STATS),"$(STATS)") $(ARGS)

stats: venv-check ## Save Home Assistant's own weather history: make stats DAYS=60 > stats.json
	@$(PY) scripts/pull_stats.py $(or $(DAYS),45)

preview: venv-check ## Serve the real panel: make preview LOCALE=it ARGS=--open-meteo
	@$(PY) scripts/preview.py --port $(PORT) --seed $(SEED) --lang $(LOCALE) $(if $(DATE),--date $(DATE)) $(ARGS)

validate: ## The HACS and hassfest checks CI runs, if Docker is here to run them
	@command -v docker >/dev/null 2>&1 || { \
	  printf 'Docker is not installed — these two only run in CI.\n'; exit 1; }
	@docker run --rm -v $(PWD):/github/workspace -e INPUT_CATEGORY=integration \
	  ghcr.io/hacs/action:main
	@docker run --rm -v $(PWD):/github/workspace ghcr.io/home-assistant/hassfest:latest

clean: ## Remove caches and compiled files, keeping the virtualenv
	@find . -path ./$(VENV) -prune -o -name '__pycache__' -type d -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache
	@printf '  caches gone\n'

distclean: clean ## Also remove the virtualenv
	@rm -rf $(VENV)
	@printf '  $(VENV) gone — run make setup\n'
