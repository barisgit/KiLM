# KiLM developer commands. Bare `just` lists them; AGENTS.md explains the workflow.

# Recipes run in just's default `sh` (Git for Windows provides it) so they work on every OS.
set positional-arguments

# Every uv command asserts that uv.lock matches pyproject.toml instead of rewriting it.
export UV_LOCKED := "1"

[private]
default:
    @just --list --unsorted

# Install the locked Python and docs dependencies and the git hooks; safe to rerun.
setup: _require-tools
    uv sync
    pnpm --dir docs install --frozen-lockfile
    uv run pre-commit install
    @echo "Ready. Next: just check (everything CI runs), just test, just docs-dev"

# Run every required check without modifying files; CI runs this.
check: lint test

# Check formatting, lint, and types without modifying files.
lint:
    uv run ruff format --check
    uv run ruff check
    uv run ty check

# Run the tests without coverage; arguments go to pytest (e.g. just test -k sync).
test *args:
    uv run pytest "$@"

# Run the tests with coverage and enforce the threshold in pyproject.toml.
cov *args:
    uv run pytest --cov "$@"

# Format the code and apply safe lint fixes.
fix:
    uv run ruff format
    uv run ruff check --fix

# Install the locked docs dependencies and build the site.
docs:
    pnpm --dir docs install --frozen-lockfile
    pnpm --dir docs build

# Serve the docs with live reload.
docs-dev:
    pnpm --dir docs dev

_require-tools:
    @command -v uv >/dev/null || { echo "uv is missing: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
    @command -v pnpm >/dev/null || { echo "pnpm is missing: https://pnpm.io/installation (Node: docs/.node-version)" >&2; exit 1; }
