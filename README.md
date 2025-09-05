# KiCad Library Manager (KiLM)

[![PyPI version](https://img.shields.io/pypi/v/kilm.svg)](https://pypi.org/project/kilm/)
[![Python versions](https://img.shields.io/pypi/pyversions/kilm.svg)](https://pypi.org/project/kilm/)
[![PyPI Downloads](https://static.pepy.tech/badge/kilm)](https://pepy.tech/projects/kilm)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Documentation](https://img.shields.io/badge/docs-website-brightgreen.svg)](https://kilm.aristovnik.me)

Professional command-line tool for managing KiCad libraries across projects and workstations.

**[Official Documentation](https://kilm.aristovnik.me)**

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

## Quick Start

```bash
# Install (recommended)
pipx install kilm

# Verify installation
kilm --version

# Initialize a library
kilm init --name my-library --description "My KiCad components"

# Set up KiCad to use your libraries
kilm setup

# Check current configuration
kilm status
```

> **[Complete Installation Guide](https://kilm.aristovnik.me/guides/installation/)** - Multiple installation methods, verification steps, and troubleshooting.

## Documentation

**[Complete Documentation](https://kilm.aristovnik.me)**

| Guide | Description |
|-------|-------------|
| [Getting Started](https://kilm.aristovnik.me/guides/getting-started/) | Creator and consumer workflows with Git integration |
| [Configuration](https://kilm.aristovnik.me/guides/configuration/) | KiLM and KiCad configuration management |
| [CLI Reference](https://kilm.aristovnik.me/reference/cli/) | Complete command documentation with examples |
| [Development](https://kilm.aristovnik.me/community/development/) | Setup guide for contributors and development |

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! See our comprehensive guides:

- **[Contributing Guidelines](https://kilm.aristovnik.me/community/contributing/)** - Issue reporting, pull requests, coding standards
- **[Development Setup](https://kilm.aristovnik.me/community/development/)** - Local development environment and tools

**Quick Start for Contributors:**
```bash
git clone https://github.com/barisgit/kilm.git
cd kilm
pip install -e ".[dev]"
pytest  # Run all tests
```
