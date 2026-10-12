# KiLM

KiLM (KiCad Library Manager) is the `kilm` command-line tool for managing KiCad
symbol, footprint, 3D-model, and project-template libraries across projects and
workstations. It is published to PyPI as `kilm`, supports Python 3.10+ on
Windows, macOS, and Linux, and primarily targets KiCad 9 and 8. User documentation lives
at https://kilm.aristovnik.me and is built from `docs/`.

## Commands

Prerequisites: [uv](https://docs.astral.sh/uv/), [just](https://just.systems),
and pnpm with the Node version in `docs/.node-version` (setup installs the docs
dependencies too). On Windows, `just` runs recipes with the `sh` from Git for
Windows.

| Command | Purpose |
| --- | --- |
| `just` | List the commands. |
| `just setup` | Install the locked Python and docs dependencies and the git hooks. Safe to rerun, including in a new worktree. |
| `just check` | Everything CI requires: `ruff format --check`, `ruff check`, `ty check`, and the tests (which include the module-size and suppression gates). Never modifies files. |
| `just test [args]` | Fast test run without coverage; arguments go to pytest. |
| `just cov` | Tests with coverage; fails below `fail_under` in `pyproject.toml`. |
| `just fix` | Format and apply safe lint fixes. |
| `just docs` / `just docs-dev` | Build the docs site / serve it with live reload. |

The recipes run tools through `uv run` with `UV_LOCKED=1`, so they fail instead
of silently rewriting `uv.lock`. Change dependencies with `uv add` or by editing
`pyproject.toml` and running `uv lock`, then commit `uv.lock`. Dev tools belong
in the `dev` dependency group. The pre-commit hook runs ruff and ty on staged
files; tests run in `just check`.

## Layout

- `kicad_lib_manager/main.py`: Typer app and command registration. Register
  leaf commands with `app.command(...)` and only real groups (`config`,
  `template`) with `add_typer`; otherwise help shows a spurious
  `COMMAND [ARGS]...` (issue #13).
- `kicad_lib_manager/commands/<name>/`: one package per command, with
  `command.py` and a collocated `docs.mdx`. `docs/scripts/sync-embedded-docs.ts`
  copies each `docs.mdx` into the site's CLI reference, so update it in the same
  change as the command.
- `kicad_lib_manager/services/`: configuration, KiCad, library, and
  self-update services.
- `kicad_lib_manager/utils/`: file operations, backups, metadata, templates,
  environment variables, git helpers.
- `tests/`: pytest suite.
- `docs/`: Astro Starlight site; guides in `docs/src/content/docs/`.
- `flake.nix`, `pkgs/kilm.nix`: Nix package, built and tested by CI. It reads
  name, version, and dependencies from `pyproject.toml`, so a new runtime
  dependency must exist in nixpkgs under the same name.
- `.github/workflows/`: `ci.yml` (checks, coverage, docs, Nix) and `release.yml`.
- `.github/scripts/`: Python steps of `release.yml`, tested like the package
  (pytest and ty resolve them as top-level modules).

## Standards

- `pyproject.toml` holds the ruff rules (`select = ["ALL"]` with complexity
  limits) and the ty configuration (every rule at error). Never weaken a rule,
  threshold, or type to make a check pass; fix the code.
- Modules stay within 600 lines; `tests/test_repository_limits.py` enforces it
  because no lint rule does. Split a module rather than raising the limit.
- Every suppression names the rule and states why, for example
  `# noqa: S603 -- arguments are a fixed git command` or
  `# ty: ignore[invalid-assignment] -- <reason>`. Blanket `# noqa` and
  `# type: ignore` are not allowed; `tests/test_repository_limits.py` rejects
  suppressions without a rule and reason.
- Full type hints. Do not add `Any`; use precise types, `TypedDict`, protocols,
  or generics.
- A module whose heavy third-party import (questionary, requests, jinja2,
  yaml, ...) is used only inside functions lists it in `__lazy_modules__`
  before its imports, so Python 3.15+ loads it on first use (PEP 810). Keep
  imports at module top level; the `lazy import` syntax needs Python 3.15.
- Use `pathlib.Path` for paths and keep behavior identical on Windows, macOS,
  and Linux.
- No emojis in code, comments, or CLI output. Put fixed values in
  `utils/constants.py` rather than inline literals.
- Give public modules, classes, and functions a docstring that states their
  contract. Comment intent and invariants, not mechanics.

## Tests

Add tests at contracts and the main path. A bug fix starts with a failing test
that reproduces it. Tests must not touch the real KiCad configuration or home
directory; use `tmp_path` and monkeypatching.

## Releases

1. Bump `version` in `pyproject.toml`, run `uv lock`, and merge that change to
   `main` through a pull request.
2. After CI passes on that commit, `release.yml` builds the sdist and wheel
   once, checks and smoke-tests them, publishes to PyPI through trusted
   publishing, then creates the `v<version>` tag and GitHub release with the
   same files. Commits whose version is already released do nothing.
3. If a run fails part way, use "Re-run failed jobs" on that run. Each job
   checks its own target, so the rerun finishes what is missing. A new run for
   a later commit refuses to create a GitHub release for a version it did not
   publish.

PyPI trusts the workflow file name `release.yml`; renaming it breaks
publishing.

## Pull requests

- Use conventional commit subjects (`feat:`, `fix:`, `docs:`, `chore:`).
  Pull requests are squash-merged.
- CI must pass on the final head commit. For first-time contributors GitHub
  holds workflows for approval: read the diff first, and do not approve runs
  that change `.github/workflows/`, hooks, or build configuration without
  understanding them, because `main` publishes releases.
- Review external pull requests against these standards. Ask for a failing
  test with each bug fix and for `docs.mdx` updates with behavior changes. When
  only small fixes remain and the contributor allows maintainer edits, push
  them to the branch rather than asking for another round.

## Agent notes

Keep working notes under `.claude/doc/` (gitignored): tasks in
`tasks/YYYY-MM-DD-SEQ-slug.md`, decisions in `adr/ADR-####-title.md`, and agent
reports in `agent-reports/`. Pass the current task file to any delegated agent.
