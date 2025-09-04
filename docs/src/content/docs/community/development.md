---
title: Development Setup
description: How to set up a development environment for KiLM.
---

If you want to contribute to KiLM or work with the source code, follow these steps to set up a development environment.

## 1. Clone the Repository

First, clone the KiLM repository from GitHub:

```bash
git clone https://github.com/barisgit/kilm.git
cd kilm
```

## 2. Create a Virtual Environment (Recommended)

It's highly recommended to use a virtual environment to isolate development dependencies.

```bash
# Using Python's built-in venv
python -m venv .venv
source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
```

## 3. Install Dependencies

Install KiLM in editable mode (`-e`) along with its development dependencies (`[dev]`):

```bash
pip install -e ".[dev]"
```

This installs the package such that changes you make to the source code are immediately reflected when you run the `kilm` command (within the activated virtual environment).
The `[dev]` part installs extra packages needed for testing and formatting, such as `pytest` and `black`.

## 4. Verify Installation

You should now be able to run the development version:

```bash
kilm --version
```

## Running Tests

KiLM uses `pytest` for testing.

```bash
# Run all tests
pytest

# Run tests in a specific file
pytest tests/test_config_commands.py

# Run tests with coverage reporting
pytest --cov=kicad_lib_manager --cov-report=term-missing
```

## Code Formatting

KiLM uses [Black](https://github.com/psf/black) for code formatting. Ensure your code is formatted before committing:

```bash
# Check formatting
black --check .

# Apply formatting
black .
```

## Next Steps

Now you're ready to start developing! See the [Contributing guide](/community/contributing/) for how to submit your changes. 