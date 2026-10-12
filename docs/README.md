# KiLM Documentation

[![Built with Starlight](https://astro.badg.es/v2/built-with-starlight/tiny.svg)](https://starlight.astro.build)
[![Documentation](https://img.shields.io/badge/docs-website-brightgreen.svg)](https://kilm.aristovnik.me)

This repository contains the documentation for [KiLM (KiCad Library Manager)](https://github.com/barisgit/KiLM), a command-line tool for managing KiCad libraries across projects and workstations.

## Documentation Structure

The documentation is organized into the following sections:

- **Guides**: Step-by-step tutorials and how-to guides
- **Reference**: Detailed command and API references
- **Community**: Information about contributing and development

## Commands

Requires Node.js 22.12 or later (Astro 7) and the pnpm version pinned in `package.json` (`corepack enable` provides it). All commands are run from the `docs/` directory:

| Command        | Action                                       |
| :------------- | :------------------------------------------- |
| `pnpm install --frozen-lockfile` | Installs dependencies from the lockfile |
| `pnpm dev`     | Starts local dev server at `localhost:4321`  |
| `pnpm build`   | Build your production site to `./dist/`      |
| `pnpm preview` | Preview your build locally, before deploying |

## Command Reference Pages

Each command's reference page lives next to its code in `kicad_lib_manager/commands/<command>/docs.mdx`. `pnpm build` and `pnpm dev` copy them into `src/content/docs/reference/cli/` (gitignored) through `scripts/sync-embedded-docs.ts`; a `.command` file in the command directory sets the page name when it differs from the directory name. `tests/test_command_docs.py` fails when a page is missing, is not in the sidebar, or disagrees with the command's options.

## Project Structure

```
docs/
├── public/               # Static assets
├── src/
│   ├── assets/           # Images and other assets
│   ├── content/
│   │   ├── docs/         # Documentation content
│   │   │   ├── guides/   # User guides and tutorials
│   │   │   ├── reference/ # Command reference and API docs
│   │   │   └── community/ # Contributing guidelines
│   └── content.config.ts # Content collection config
├── astro.config.mjs      # Astro configuration
├── package.json
└── README.md            # This file
```

## Links

- [KiLM Documentation Website](https://kilm.aristovnik.me)
- [Starlight Documentation](https://starlight.astro.build/)
