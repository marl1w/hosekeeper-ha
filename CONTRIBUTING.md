# Contributing

Issues and pull requests are welcome. Open a pull request with a description of your changes and the use case you are addressing, follow the existing style, and include tests.

Maintained by [marl1w](MAINTAINERS.md).

## Before you open a pull request

```bash
make setup   # once: creates .venv and installs test dependencies
make check   # lint, format, translations, tests, and the frontend checks
```

`make` on its own lists everything there is to run. Every target that needs the virtualenv uses it, so there is nothing to activate.

Home Assistant 2026.3+ needs Python 3.14.2 or newer. If your default `python3` is older:

```bash
make setup PYTHON="$(pyenv root)/versions/3.14.6/bin/python3"
```

## House style

- **No dependencies.** The integration installs with nothing but Home Assistant itself, and the panel has no build step. That is a promise worth keeping.
- **Comments say why, not what.** The code says what it does; a comment earns its place by recording the measurement, the source or the trade-off that made it look like this.
- **Everything user-facing gets a string in `strings.json` and in every file under `translations/`.** `make translations` compares them key by key. Italian and English are both first-class: a change to one is a change to both.
- **The engine has no Home Assistant in it.** Everything under `engine/` takes numbers and returns numbers, so it can be tested without an instance and reasoned about without one.
- **Advice cites its source.** A rule in the knowledge base points at the extension bulletin, paper or manufacturer's data sheet it came from, in `docs/knowledge.md`.

## Seeing the panel without Home Assistant

`scripts/preview.py` serves the real panel modules against an invented lawn, so a change can be
looked at without an instance:

```bash
make preview                        # http://127.0.0.1:8123, an invented lawn
make preview LOCALE=it              # in Italian
make preview ARGS=--open-meteo      # the real weather over the lawn in scripts/example-lawn.json
make preview ARGS="--stats stats.json"   # a real station's own record
make preview DATE=2027-04-10        # pretend it is spring
```

`scripts/example-lawn.json` describes the lawn the preview shows and its zones: their size
and exposure, the soil, when the turf was laid and the measured precipitation rate. Point
`--lawn` at your own copy to see your property. With `--open-meteo` the weather is a reanalysis of what
actually happened over those coordinates, so the advice is the advice you would have had.

```bash
make stats DAYS=60 > stats.json      # your own station, out of Home Assistant
make replay ARGS="--open-meteo --established 2026-06-06 --method sod --rate 20 --fixed 8.3"
```

`make replay` runs a real month through the engine day by day and reports how dry it would
have let the grass get, beside a fixed schedule. It is the check to run before trusting this
with a lawn.

The diary is invented, but the advice, the plan and the fertilizer classes are not: they come
from the same engine the integration ships, so what you see is what those numbers would
produce in Home Assistant. The panel is read-only: rating and logging go through the services.

Modules are served with caching off, so an edit needs a browser reload and nothing else.
Inside Home Assistant the frontend is served under a URL that changes with the directory's
contents, so an edit becomes visible on **Settings → Devices & services → Hosekeeper → ⋮ →
Reload**, not on a browser reload.

## The panel has no build step, and no compiler either

`tests/frontend/test_views.mjs` renders every view in Node against the same invented lawn the
preview serves, through a small DOM shim. It is there because plain DOM fails at runtime, not
at build time: a name that is not in scope, or a `null` appended as a child, blanks a section
of the page and nothing says so until somebody opens the sidebar. The shim throws on both.

Run it with `make frontend`, or `make check`, which runs it too.

## Commits

Conventional subjects, lower case, one line: `feat:`, `fix:`, `docs:`, `ci:`, `test:`. A release is its own commit, `release: x.y.z`, that bumps `version` in `custom_components/hosekeeper/manifest.json`.
