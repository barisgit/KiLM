# Contributing to KiLM

Bug reports, feature requests, documentation fixes, and code are welcome.
Search the [issues](https://github.com/barisgit/KiLM/issues) first; for a bug,
include `kilm --version`, your KiCad version and operating system, the steps
to reproduce, and the full error output.

## Development

Install [uv](https://docs.astral.sh/uv/), [just](https://just.systems), and
[pnpm](https://pnpm.io) with the Node version in `docs/.node-version` (setup also
installs the docs dependencies).

```bash
git clone https://github.com/<your-username>/KiLM.git
cd KiLM
just setup   # locked dependencies and git hooks; safe to rerun
just check   # everything CI runs
```

`just` lists the other commands (`test`, `cov`, `fix`, `docs`, `docs-dev`).
[AGENTS.md](AGENTS.md) describes the layout, coding standards, and release
process; it applies to human and AI contributors alike.

## Pull requests

1. Branch from `main` and keep each pull request to one change.
2. Add a test with each feature, and a failing test first with each bug fix.
3. Update the command's collocated `docs.mdx` when behavior changes.
4. Run `just check`, then open the pull request with a conventional commit
   title (`feat:`, `fix:`, `docs:`, `chore:`) and link the issue it closes.

By contributing, you agree that your contributions are licensed under the MIT
License.
