---
title: init
description: Initialize the current directory as a KiCad library collection.
---

The `kilm init` command prepares the **current working directory** to be managed by KiLM as a library collection, primarily intended for symbol, footprint, and template libraries (often managed via Git, hence the internal type `github`).

It performs several actions:

1.  Creates standard subdirectories (`symbols/`, `footprints/`, `templates/`) if they don't exist.
2.  Creates a template `library_descriptions.yaml` file if it doesn't exist, used for richer descriptions in KiCad.
3.  Creates or updates a metadata file named `kilm.yaml` within the current directory. This stores the library's name, description, associated environment variable, and detected capabilities (symbols, footprints, templates).
4.  Adds an entry for this library (with its path and type `github`) to the main KiLM configuration file (`~/.config/kicad-lib-manager/config.yaml`).
5.  Optionally sets this library as the `current_library` in the main configuration.

## Usage

Run this command from *within* the directory you want to initialize:

```bash
cd /path/to/your-library
kilm init [OPTIONS]
```

## Options

- `--name TEXT`: 
  Sets a custom name for the library collection. If not provided, a name is generated from the current directory name.
  *Example:* `kilm init --name my-custom-library`

- `--description TEXT`: 
  Adds a description to the library metadata (`kilm.yaml`).
  *Example:* `kilm init --description "My collection of custom components"`

- `--env-var TEXT`: 
  Specifies a custom KiCad environment variable name (e.g., `MY_CUSTOM_LIB`) to associate with this library's path. If not provided (and `--no-env-var` isn't used), a name is automatically generated (e.g., `KICAD_LIB_MY_CUSTOM_LIBRARY`). This variable will be set in KiCad when you run `kilm setup`.
  *Example:* `kilm init --env-var MY_LIB_PATH`

- `--no-env-var`: 
  Prevents an environment variable from being assigned to this library in the metadata. Default: `False`.
  *Example:* `kilm init --no-env-var`

- `--set-current / --no-set-current`: 
  Controls whether this library should be set as the `current_library` in the main `config.yaml`. Default: `--set-current`.
  *Example:* `kilm init --no-set-current`

- `--force`: 
  If `kilm.yaml` already exists, overwrite it with new metadata based on options or defaults. Without `--force`, existing metadata is updated only with explicitly provided options. Default: `False`.
  *Example:* `kilm init --force`

- `--help`: 
  Show the help message and exit.

## Behavior Summary

- **Target:** Current working directory.
- **Creates/Updates:** `symbols/`, `footprints/`, `templates/` dirs, `library_descriptions.yaml`, `kilm.yaml`.
- **Modifies Global Config:** Adds library entry to main `config.yaml`, optionally sets `current_library`.
- **Library Type:** Registers the library with type `github` in `config.yaml`.

## Examples

**Basic Initialization:**
Initialize the current directory, creating folders and metadata, using default names/env vars, and setting it as current.

```bash
cd /path/to/my-kicad-library
kilm init
```

**Initialization with Options:**
Initialize with a specific name, description, and environment variable, and *don't* set it as the current library.

```bash
cd /path/to/another-kicad-library
kilm init --name project-specific --description "Components for Project X" --env-var PROJECT_X_LIBS --no-set-current
```

**Re-initialize with Force:**
Overwrite existing `kilm.yaml` with default settings.

```bash
cd /path/to/existing-library
kilm init --force
```

**Note:** Running `kilm init` registers the library with KiLM and prepares the directory. You still need to run [`kilm setup`](/reference/cli/setup/) afterwards to make KiCad aware of this library by updating KiCad's configuration files. 