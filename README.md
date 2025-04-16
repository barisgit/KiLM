# KiCad Library Manager (KiLM)

[![PyPI version](https://img.shields.io/pypi/v/kilm.svg)](https://pypi.org/project/kilm/)
[![Python versions](https://img.shields.io/pypi/pyversions/kilm.svg)](https://pypi.org/project/kilm/)
[![PyPI Downloads](https://static.pepy.tech/badge/kilm)](https://pepy.tech/projects/kilm)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-website-brightgreen.svg)](https://kilm.aristovnik.me)

A command-line tool for managing KiCad libraries across projects and workstations.

**[📚 Official Documentation](https://kilm.aristovnik.me)**

## Features

- Automatically detect KiCad configurations across different platforms (Windows, macOS, Linux)
- Add symbol and footprint libraries to KiCad from a centralized repository
- Set environment variables directly in KiCad configuration
- Pin favorite libraries for quick access in KiCad
- Create timestamped backups of configuration files
- Support for environment variables
- Dry-run mode to preview changes
- Compatible with KiCad 6.x and newer
- Project template management to standardize new designs

## Installation

```bash
# Using pip
pip install kilm

# Using pipx (recommended for CLI tools)
pipx install kilm

# Using uv (faster Python package installer)
uv pip install kilm
```

## Quick Start

```bash
# Initialize a library
kilm init

# Set up KiCad to use your libraries
kilm setup

# Check current configuration
kilm status
```

## Documentation

For comprehensive guides, usage examples, and configuration options, visit the [official documentation](https://kilm.aristovnik.me).

- [Installation Guide](https://kilm.aristovnik.me/guides/installation/)
- [Getting Started](https://kilm.aristovnik.me/guides/getting-started/)
- [Configuration Options](https://kilm.aristovnik.me/guides/configuration/)
- [Command Reference](https://kilm.aristovnik.me/reference/cli/)
- [Project Architecture](https://kilm.aristovnik.me/community/development/)

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch
3. Submit a Pull Request

See the [development documentation](https://kilm.aristovnik.me/community/development/) for more details.
