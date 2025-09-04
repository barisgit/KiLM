---
title: add-3d
description: Add a directory containing 3D models (e.g., STEP, WRL).
---

The `kilm add-3d` command registers a directory containing 3D models (like `.step` or `.wrl` files) with KiLM. This is typically used for libraries stored outside the main symbol/footprint Git repository, such as in cloud-synced folders.

It performs the following main actions:

1.  Creates or updates a metadata file named `.kilm_cloud_metadata` within the target directory. This stores the library's name, description, associated environment variable, and a count of detected model files.
2.  Adds an entry for this library (with its path and type `cloud`) to the main KiLM configuration file (`~/.config/kicad-lib-manager/config.yaml`).
3.  Scans the directory for common 3D model file extensions and warns if none are found.

## Usage

```bash
kilm add-3d [OPTIONS]
```

## Options

- `--directory DIRECTORY`: 
  Specifies the path to the directory containing the 3D models. 
  *Default:* Uses the current working directory if not specified.
  *Example:* `kilm add-3d --directory ~/kicad/libraries/3d-models`

- `--name TEXT`: 
  Sets a custom name for this 3D library entry. If not provided, a name is generated from the directory name.
  *Example:* `kilm add-3d --directory ... --name standard-3d-lib`

- `--description TEXT`: 
  Adds an optional description for this 3D library to the metadata file.
  *Example:* `kilm add-3d --directory ... --name ... --description "My custom collection of STEP models"`

- `--env-var TEXT`: 
  Specifies a custom KiCad environment variable name (e.g., `MY_CUSTOM_3D`) to associate with this library's path. If not provided (and `--no-env-var` isn't used), a name is automatically generated (e.g., `KICAD_3D_STANDARD_3D_LIB`). This variable will be set in KiCad when you run `kilm setup`.
  *Example:* `kilm add-3d --directory ... --name ... --env-var KICAD_USER_3DMOD`

- `--no-env-var`: 
  Prevents an environment variable from being assigned to this library in the metadata. Default: `False`.
  *Example:* `kilm add-3d --no-env-var`

- `--force`: 
  If `.kilm_cloud_metadata` already exists in the target directory, overwrite it with new metadata based on options or defaults. Without `--force`, existing metadata is updated only with explicitly provided options. Default: `False`.
  *Example:* `kilm add-3d --directory ... --force`

- `--help`: 
  Show the help message and exit.

## Behavior

- **Target Directory:** Uses `--directory` path or current working directory.
- **Creates/Updates Metadata:** Creates or modifies `.kilm_cloud_metadata` in the target directory.
- **Updates Global Config:** Adds library entry (type `cloud`) to main `config.yaml`.
- **Verification:** Checks for the presence of files with extensions like `.step`, `.stp`, `.wrl` in the target directory.

## Examples

**Add a 3D library (using defaults where possible):**
Register the directory `/home/user/cad/my_3d_parts`. A name and environment variable will be generated automatically.

```bash
kilm add-3d --directory /home/user/cad/my_3d_parts --description "Custom 3D mechanical parts"
```

**Add a 3D library with specific names:**
Register the directory `/opt/kicad/packages3d`, name it `kicad-official-3d`, and assign the environment variable `KICAD_OFFICIAL_3D`.

```bash
kilm add-3d --directory /opt/kicad/packages3d --name kicad-official-3d --env-var KICAD_OFFICIAL_3D --description "KiCad Official 3D Models"
```

**Add 3D library in current directory without an environment variable:**

```bash
cd ~/my_project_3d_models
kilm add-3d --name my-project-models --no-env-var
```

**Note:** After adding 3D libraries, you usually need to run [`kilm setup`](/reference/cli/setup/) to create or update the associated environment variables (like `KICAD_OFFICIAL_3D` in the example) in KiCad's configuration. 