# Contributing to KiLM

Thank you for your interest in contributing to KiLM (KiCad Library Manager)!

**[Complete Contributing Guide](https://kilm.aristovnik.me/community/contributing/)**

This file provides a quick reference. For detailed guidelines, development setup, and coding standards, see our comprehensive documentation.

## Contribution Types

- **Bug Reports** - Help identify and fix issues
- **Feature Requests** - Share ideas for improvements  
- **Documentation** - Improve guides and examples
- **Testing** - Add tests or improve coverage
- **Code** - Fix bugs or implement features

## Quick Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR-USERNAME/kilm.git
cd kilm

# 2. Set up development environment  
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install with dev dependencies
pip install -e ".[dev]"

# 4. Verify setup
kilm --version
pytest
```

**[Complete Development Setup Guide](https://kilm.aristovnik.me/community/development/)**

## Quality Standards

Before submitting, ensure your code meets our standards:

```bash
# Type checking (required - zero "Any" types)
pyrefly

# Code formatting
black .

# Linting 
ruff check --fix .

# Testing
pytest --cov=kicad_lib_manager
```

## Pull Request Process

1. **Create feature branch**: `git checkout -b feature/my-feature`
2. **Make changes** following coding standards
3. **Add tests** for new functionality  
4. **Run quality checks** (above commands)
5. **Commit** with descriptive messages (`feat:`, `fix:`, `docs:`)
6. **Push and create PR** with clear description

**[Complete Pull Request Guidelines](https://kilm.aristovnik.me/community/contributing/#pull-request-workflow)**

## Getting Help

- **Documentation**: [Official Documentation](https://kilm.aristovnik.me)
- **Issues**: [GitHub Issues](https://github.com/barisgit/kilm/issues) for bugs and features
- **Discussions**: [GitHub Discussions](https://github.com/barisgit/kilm/discussions) for questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.