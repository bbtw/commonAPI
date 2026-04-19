# commonAPI

Home for **`yourco-observability`** and **`yourco-fastapi`** — a small set of
libraries that standardize the edges of FastAPI services (request correlation,
structured logs, tracing, metrics, health, and error envelopes) without turning
the platform into a framework. See
[`docs/fastapi-platform-toolkit-final.md`](docs/fastapi-platform-toolkit-final.md)
for the design, and [`docs/toolkit-roadmap.md`](docs/toolkit-roadmap.md) for
what's built and what's still outstanding.

## Layout

```
libs/
  yourco-observability/   # structured logging, tracing, metrics, request context
  yourco-fastapi/         # apply_* toolkit functions for a FastAPI app
examples/
  demo-service/           # reference service wiring both libs together
```

Managed as a [uv workspace](https://docs.astral.sh/uv/concepts/workspaces/).
Each library under `libs/` is independently publishable and owns its own
dependencies, dev deps, and tests. Examples under `examples/` are reference
consumers, not shipped artifacts.

## Why it's set up this way

A few deliberate choices shape the repo. They're here so future changes don't
quietly undo them.

- **uv workspace, not separate repos.** The two libraries co-evolve while the
  toolkit's shape is still forming — one repo keeps the PR and refactor loop
  tight. If/when a second team consumes them externally and they need
  independent release cadences, splitting becomes cheap. Doing it earlier
  would pay coordination cost for little benefit.

- **`libs/` + `examples/` split.** `libs/` holds things meant to be
  published to an index. `examples/` holds reference consumers that exercise
  the libs but are not themselves products. Separate trees make the intent
  obvious: a new contributor shouldn't wonder whether `demo-service` is
  something to ship.

- **Thin root `pyproject.toml`.** The root carries workspace glue (members)
  and cross-cutting tool config (`ruff`, `mypy`, `pytest` asyncio mode) and
  nothing else. It is not a meta-package and is not installed. Each library
  declares its own runtime and dev dependencies, so you could lift any one
  out of the repo and publish it as-is.

- **Per-package dev dependency groups.** Every library owns the test tooling
  it needs (pytest, httpx, etc.). This means:
  - `cd libs/<name> && uv sync && uv run pytest` works without reading the
    root pyproject.
  - CI can run a package-per-job matrix; a broken dep in one lib can't mask
    failures in another.
  - There's no single list of members to keep in sync — `libs/*` and
    `examples/*` globs auto-discover new packages.

- **No `testpaths`.** pytest's default discovery walks the repo and finds
  `**/tests/test_*.py`, which is exactly what we want. Adding testpaths
  would turn a new package into a one-line README change instead of a
  zero-change addition.

- **Cross-library deps use `workspace = true` at the call site.**
  `libs/yourco-fastapi/pyproject.toml` declares `yourco-observability` as a
  workspace source in its own file, not the root's. That keeps each
  package's dependency graph readable from inside the package.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) 0.6+

## Working with the whole workspace

```bash
uv sync --all-packages --all-groups   # install every member + all dev groups, editable
uv run pytest                         # runs all tests across libs/ and examples/
uv run ruff check                     # lint
uv run mypy libs examples             # strict typecheck
```

## Working on a single library

Each library is self-contained — `cd` in and develop it without caring about
the rest of the workspace:

```bash
cd libs/yourco-observability
uv sync
uv run pytest
```

## Running the demo service

```bash
uv run uvicorn demo_service.main:app --reload
# in another shell
curl -i http://localhost:8000/health
curl -i http://localhost:8000/version
curl -i -H 'X-Request-ID: my-id' 'http://localhost:8000/hello?name=world'
```

The process emits JSON logs to stdout; each request gets an `X-Request-ID`
response header that matches the `request_id` in the log line.

## Adding a new package

1. Create `libs/<new-lib>/` or `examples/<new-thing>/` with a `pyproject.toml`.
2. Add a `[dependency-groups] dev` entry with the package's own test tooling.
3. Run `uv sync --all-packages --all-groups` — the `libs/*` / `examples/*`
   globs in the root workspace config pick it up automatically.

There is no central list of members to update.
