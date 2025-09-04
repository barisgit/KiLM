---
title: list
description: List symbol and footprint libraries found within a directory.
---

The `kilm list` command scans a specified directory (typically your main KiCad library directory) and lists the symbol (`.kicad_sym`) and footprint (`.pretty`) libraries it finds within it.

This is useful for verifying the contents of a specific library directory, independent of KiLM's own configuration.

## Usage

```bash
kilm list [OPTIONS]
```

## Options

- `--kicad-lib-dir TEXT`: 
  Specify the path to the KiCad library directory you want to scan. 
  If not provided, KiLM will look for the `KICAD_USER_LIB` environment variable and use its value.
  *Default:* Uses `KICAD_USER_LIB` environment variable.
  *Example:* `kilm list --kicad-lib-dir /path/to/my/libraries`

- `--help`: 
  Show this help message and exit.

## Behavior

1.  **Determines Target Directory:** Uses the path provided via `--kicad-lib-dir` or falls back to the `KICAD_USER_LIB` environment variable.
2.  **Scans Directory:** Recursively scans the target directory.
3.  **Identifies Libraries:** 
    - Looks for files ending in `.kicad_sym` to identify symbol libraries.
    - Looks for directories ending in `.pretty` to identify footprint libraries.
4.  **Prints Lists:** Outputs separate lists of the symbol and footprint library names found.

## Examples

**List Libraries in Default Directory:**
Scans the directory specified by the `KICAD_USER_LIB` environment variable.

```bash
kilm list
```

*Expected Output (example):*
```
Available Symbol Libraries:
  - 74xx
  - Connector
  - Device

Available Footprint Libraries:
  - Capacitor_SMD
  - Connector_PinHeader_2.54mm
  - Resistor_SMD
```

**List Libraries in a Specific Directory:**
Scans the specified directory `/home/user/my-kicad-libs`.

```bash
kilm list --kicad-lib-dir /home/user/my-kicad-libs
``` 