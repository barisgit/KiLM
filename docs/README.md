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

All commands are run from the root of the project, from a terminal:

| Command        | Action                                       |
| :------------- | :------------------------------------------- |
| `pnpm install` | Installs dependencies                        |
| `pnpm dev`     | Starts local dev server at `localhost:4321`  |
| `pnpm build`   | Build your production site to `./dist/`      |
| `pnpm preview` | Preview your build locally, before deploying |

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
