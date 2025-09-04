---
title: Installation
description: How to install KiLM on your system.
---

KiLM requires Python 3.7 or newer and KiCad 6.x or newer (must be run at least once).

## Dependencies

KiLM relies on the following Python packages:

- `click >= 8.0`
- `pyyaml >= 6.0`
- `pathlib >= 1.0.1`
- `pathspec >= 0.12.1`
- `jinja2 >= 3.1.6`

These dependencies are automatically installed when you install KiLM using `pip` or `pipx`.

## Installation Methods

You can install KiLM using several methods:

### From PyPI (Standard Method)

The most common way to install Python packages:

```bash
pip install kilm
```

### Using pipx (Recommended)

[`pipx`](https://pypa.github.io/pipx/) installs CLI tools in isolated environments, making them available globally without interfering with other Python projects. This is the recommended method for installing KiLM.

```bash
# Install pipx if you don't have it
python -m pip install --user pipx
python -m pipx ensurepath

# Install kilm using pipx
pipx install kilm
```

### Using uv (Faster Installer)

[`uv`](https://github.com/astral-sh/uv) is an extremely fast Python package installer and resolver from the creators of Ruff.

```bash
# Install uv if you don't have it (example for Linux/macOS)
curl -sSf https://astral.sh/uv/install.sh | sh

# Install kilm using uv
uv pip install kilm
```

### From Source (Development)

If you want to contribute to KiLM or use the latest development version:

```bash
# Clone the repository
git clone https://github.com/barisgit/kilm.git
cd kilm

# Install in editable mode
pip install -e .
```

After installation, you should be able to run `kilm --version` to verify it's installed correctly. 