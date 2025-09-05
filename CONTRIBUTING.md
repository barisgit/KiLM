# Contributing to KiLM (KiCad Library Manager)

Thank you for considering contributing to KiLM! This document provides guidelines and information for contributors.

## How to Contribute

We welcome contributions of all types:

- **Bug Reports**: Found a bug? Let us know!
- **Feature Requests**: Have an idea? We'd love to hear it!
- **Documentation**: Help improve our docs
- **Testing**: Add tests or improve test coverage
- **Code**: Fix bugs or implement new features
- **Templates**: Add KiCad project templates

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- A GitHub account
- KiCad 8.x or newer (for testing)

### Development Setup

1. **Fork and Clone the Repository**

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/KiLM.git
cd KiLM

# Add the upstream repository
git remote add upstream https://github.com/barisgit/KiLM.git
```

2. **Set Up Development Environment**

```bash
# Create a virtual environment
python -m venv venv

# Activate it (Linux/macOS)
source venv/bin/activate

# With fish shell
source venv/bin/activate.fish

# Or on Windows
venv\\Scripts\\activate

# Install the package in development mode with all dependencies
pip install -e ".[dev]"
```

3. **Install Pre-commit Hooks** (Future)

```bash
# Install pre-commit hooks for code quality (to be implemented)
# pre-commit install

# Run hooks on all files to verify setup
# pre-commit run --all-files
```

## Development Workflow

### Code Style and Quality

We maintain high code quality standards:

- **Ruff**: Fast Python linter
- **Pyrefly**: Strict type checking (to be implemented)
- **Pytest**: Testing framework

#### Running Quality Checks

```bash
# Check and fix linting issues
ruff check --fix

# Type checking
pyrefly check

# Run all checks (to be implemented)
# pre-commit run --all-files
```

### Testing

We maintain comprehensive test coverage:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=kicad_lib_manager --cov-report=html

# Run specific test file
pytest tests/test_config_commands.py

# Run tests with verbose output
pytest -v
```

### Making Changes

1. **Create a Feature Branch**

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a new feature branch
git checkout -b feature/your-feature-name
```

2. **Make Your Changes**

- Follow the existing code style and patterns
- Add comprehensive tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

3. **Commit Your Changes**

```bash
# Stage your changes
git add .

# Commit with a descriptive message
git commit -m "feat: add support for KiCad 9.x library tables

- Add compatibility layer for new library table format
- Update library detection for KiCad 9.x installations
- Add tests for KiCad version detection
- Update documentation with KiCad 9.x examples"
```

#### Commit Message Format

We follow conventional commits:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `test:` Adding or modifying tests
- `refactor:` Code refactoring
- `style:` Code style changes
- `chore:` Maintenance tasks

### Pull Request Process

1. **Push Your Branch**

```bash
git push origin feature/your-feature-name
```

2. **Create a Pull Request**

- Go to GitHub and create a PR from your fork
- Fill out the PR template completely
- Link any related issues
- Ensure all tests pass

3. **Code Review Process**

- Maintainers will review your PR
- Address any feedback promptly
- Keep your branch updated with main
- Be responsive to questions and suggestions

## Contribution Guidelines

### Code Guidelines

1. **Follow Professional Standards**: Use consistent code style
2. **Type Hints**: Add type hints to all functions and methods (no `Any` types)
3. **Docstrings**: Document all public functions, classes, and modules
4. **Error Handling**: Handle errors gracefully with informative messages
5. **Security**: Never commit secrets or sensitive information
6. **Constants**: Use constants from `constants.py` instead of hardcoded values
7. **No Emojis**: Keep code professional - avoid emojis in code and output

### Documentation Guidelines

1. **Keep README Updated**: Update README.md for user-facing changes
2. **API Documentation**: Document all public APIs
3. **Examples**: Add examples for new features
4. **Changelog**: Add entries for releases

### Testing Guidelines

1. **Test Coverage**: Aim for comprehensive test coverage
2. **Test All Cases**: Test happy path, edge cases, and error conditions
3. **Cross-platform**: Test on Windows, macOS, Linux if possible
4. **KiCad Integration**: Test with actual KiCad installations when feasible

## Architecture Overview

Understanding the architecture helps with contributions:

```
┌─────────────────┐
│   CLI Layer     │  ← Click commands, user interface
│   (cli.py)      │
├─────────────────┤
│  Command Layer  │  ← Individual command implementations
│  (commands/)    │
├─────────────────┤
│  Core Layer     │  ← Library management, configuration
│  (config.py,    │
│ lib_manager.py) │
├─────────────────┤
│ Utilities Layer │  ← File ops, backups, templates
│   (utils/)      │
└─────────────────┘
```

### Key Design Principles

1. **Cross-platform First**: Support Windows, macOS, Linux equally
2. **Type Safety**: Comprehensive type hints, no `Any` types
3. **Professional Quality**: No emojis, proper error handling
4. **Modularity**: Clear separation of concerns
5. **Testability**: Design for easy testing
6. **Backward Compatibility**: Maintain CLI interface stability

## Reporting Issues

### Bug Reports

When reporting bugs, please include:

1. **KiLM Version**: Output of `kilm --version`
2. **Python Version**: Output of `python --version`
3. **Operating System**: Your OS and version
4. **KiCad Version**: Your KiCad installation version
5. **Steps to Reproduce**: Clear steps to reproduce the issue
6. **Expected Behavior**: What you expected to happen
7. **Actual Behavior**: What actually happened
8. **Error Messages**: Full error messages and stack traces
9. **Configuration**: Relevant parts of your configuration (remove secrets!)

### Feature Requests

For feature requests, please provide:

1. **Use Case**: Describe your specific use case
2. **Proposed Solution**: How do you envision this working?
3. **Alternatives**: What alternatives have you considered?
4. **Impact**: How would this benefit other users?

## Areas for Contribution

We especially welcome contributions in these areas:

### High Priority
- **KiCad 9.x Support**: Full compatibility with latest KiCad
- **Template System**: More project templates and template features
- **Cross-platform Testing**: Ensure reliability across platforms
- **Documentation**: More examples and tutorials

### Medium Priority  
- **CLI Modernization**: Migrate from Click to Typer + Rich
- **Type Safety**: Complete elimination of `Any` types
- **Performance**: Optimization for large library collections
- **Error Messages**: More helpful error messages and recovery suggestions

### Good First Issues

Look for issues labeled `good-first-issue` for beginner-friendly contributions:

- Documentation improvements
- Adding tests
- Small bug fixes
- Template examples
- Cross-platform compatibility fixes

## Getting Help

If you need help:

1. **Documentation**: Check the README and PLAN.md first or look at the official documentation at https://kilm.aristovnik.me
2. **Search Issues**: Look through existing GitHub issues
3. **Ask Questions**: Open a GitHub issue with the `question` label
4. **Discussions**: Use GitHub Discussions for general questions

## Development Environment Tips

### KiCad Testing Setup

For testing KiCad integration:

1. **Install KiCad**: Install KiCad 8.x or newer
2. **Backup Config**: Always backup your KiCad configuration before testing
3. **Test Libraries**: Use test library directories, not production ones
4. **Multiple Versions**: Test with different KiCad versions if possible

### Useful Commands

```bash
# Check current KiCad configuration
kilm status

# Test library setup (dry run)
kilm setup --dry-run

# Initialize test library
kilm init --directory test-lib

# Run specific tests
pytest tests/test_library_manager.py -v
```

## Recognition

Contributors will be:

- Listed in the README contributors section
- Mentioned in release notes for significant contributions
- Invited to be maintainers for sustained, high-quality contributions

## License

By contributing to KiLM, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to KiLM!