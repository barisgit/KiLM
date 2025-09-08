# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Core Principles: Simplicity & Type Safety

KiLM (KiCad Library Manager) prioritizes **professional code standards** and **complete type safety**:

- **Type-first development**: Everything uses proper type hints - no `Any`, no dynamic typing
- **Professional standards**: No emojis in code, no hardcoded values, proper constants
- **CLI-focused**: Simple, reliable command-line interface for KiCad library management
- **Cross-platform**: Support for Windows, macOS, Linux KiCad installations

## Architecture Overview

KiLM is a **command-line tool for managing KiCad libraries** across projects and workstations:

**Core Functionality**:
- KiCad configuration detection across platforms
- Library management (symbol and footprint libraries)  
- Environment variable configuration
- Project template management
- Backup and restore of KiCad configurations

## Development Commands

### Python CLI Development
```bash
# Install Python package in development mode
pip install -e ".[dev]"

# Install pre-commit hooks (once implemented)
pre-commit install

# Test basic functionality
kilm status
kilm --help
```

### Testing & Quality
```bash
# Run tests with coverage
pytest --cov=kicad_lib_manager --cov-report=html

# Type checking, formatting, and linting
pyrefly    # Type check (required - no "any" types allowed)
ruff format .
ruff check .

# All quality checks
pre-commit run --all-files
```

### CI/CD and Releases
```bash
# Create a new release (automated via GitHub Actions)
# 1. Update version in kicad_lib_manager/__init__.py
# 2. Push version tag:
git tag v0.3.1
git push origin v0.3.1

# This triggers:
# - Automated testing and quality checks
# - PyPI publishing with trusted publishing
# - Draft GitHub release with auto-generated notes
# - Multi-platform compatibility verification
```

**Release Process:**
1. **Tag-based releases**: Push version tags to trigger automated releases
2. **Draft releases**: GitHub releases created as drafts for manual review
3. **Automatic PyPI**: Publishes to PyPI immediately via trusted publishing
4. **Auto-generated notes**: Release notes include commits, PRs, and install instructions

## Code Quality Standards

### Type Safety Requirements
- **No Any types**: All functions must have proper type hints
- **Pydantic models**: Use Pydantic for configuration validation where applicable
- **Type checking**: Must pass pyrefly type checking without errors

### Professional Code Standards
- **No emojis**: Keep code and output professional - avoid emojis in code, comments, or CLI output
- **No hardcoding**: Use constants, configuration files, or environment variables
- **Proper error handling**: Consistent error patterns with informative messages
- **Cross-platform paths**: Use pathlib.Path for all file operations
- **Context7**: Often use context 7 MCP when dealing with new code and packages

## CLI Architecture

### Command Structure
```
kilm                    # Main CLI entry point
├── init               # Initialize library
├── setup              # Configure KiCad to use libraries  
├── status             # Show current configuration
├── list               # List available libraries
├── pin/unpin          # Pin/unpin favorite libraries
├── add-3d             # Add 3D model libraries
├── config             # Configuration management
├── sync               # Update/sync library content (was 'update')
├── update             # Update KiLM itself (breaking change in 0.4.0)
├── add-hook           # Add project hooks
└── template           # Project template management
```

## BREAKING CHANGES in v0.4.0

### Command Restructuring
- **`kilm update`** now updates KiLM itself (self-update functionality)
- **`kilm sync`** updates library content (was `kilm update`)
- Added deprecation banner for transition period
- Full auto-update functionality with installation method detection

### New Features
- **Self-Update System**: Detects installation method (pip, pipx, conda, uv, homebrew)
- **PyPI Integration**: Checks for latest versions with proper caching
- **Update Preferences**: Configurable update checking and frequency
- **Professional UX**: Non-intrusive notifications with method-specific guidance

### Core Modules
- **CLI Layer** (`main.py`): Typer-based command interface with Rich output
- **Commands** (`commands/`): Individual command implementations
- **Library Manager** (`library_manager.py`): Core library management logic
- **Configuration** (`config.py`): KiCad configuration handling with update preferences
- **Auto-Update** (`auto_update.py`): Self-update functionality with installation detection
- **Utilities** (`utils/`): File operations, backups, metadata, templates

## Development Workflow - MANDATORY

### Task Documentation
- **ALWAYS create task file**: For ANY work request, immediately create `.claude/doc/tasks/[date]-[seq]-[task-name].md`
- **Update throughout**: Document progress, decisions, blockers in real-time
- **Include context**: Always pass current task file path to agents for context sharing

### Code Quality Workflow  
- **After completing ANY code changes**: Prompt user "Should I run the code-reviewer to check for quality issues?"
- **Never assume**: Don't run code-reviewer automatically without asking
- **Update task file**: Document review results and any issues found

### Agent Management
- **Use agents for all complex tasks**: Code reviews, documentation, analysis, implementation planning
- **Always provide task context**: Give agents the current task file path when applicable
- **Delegate, don't duplicate**: Use specialized agents instead of handling complex tasks directly
- **Give quality context to agents**: Point them to current task, tell them to use linters and type checkers

### Agent Context Management (Required)

- **Persist context in repo (important)**: Agents MUST save context under `.claude/doc/` to ensure continuity across runs.
  - Tasks: `.claude/doc/tasks/YYYY-MM-DD-SEQ-slug.md` (SEQ is a 3-digit daily sequence starting at `001`. Agents only have the date—remember to increment SEQ if multiple tasks are created on the same day.)
  - Decisions/ADR: `.claude/doc/adr/ADR-####-short-title.md`
  - General agent reports: `.claude/doc/agent-reports/YYYY-MM-DD-SEQ-agent-report.md`
- **Pass context to agents (including general agents)**: When invoking any agent, ALWAYS include the path to the current task file. If the agent has no repo-specific instructions, explicitly tell it to save an `agent-report` (and append a short update to the task) using the same naming scheme.
- **Round-trip updates**: After each agent step, append a concise update (what changed, why, next) to the active task file.
- **Minimal duplication**: Reference prior notes; keep canonical decisions in ADRs and link from task files.
- **Example context**:
  - Current task: `.claude/doc/tasks/YYYY-MM-DD-SEQ-task-name.md`
  - Agent should also write: `.claude/doc/agent-reports/YYYY-MM-DD-SEQ-agent-report.md`
  - Instruction: "Always provide current task path and increment SEQ for same-day tasks."

## Key Implementation Patterns

### KiCad Configuration Management
```python
# Professional, type-safe configuration handling
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel

class KiCadConfig(BaseModel):
    """Type-safe KiCad configuration model."""
    libraries: List[str]
    environment_vars: Dict[str, str]
    backup_enabled: bool = True
    
def detect_kicad_config_path() -> Optional[Path]:
    """Detect KiCad configuration path across platforms."""
    # Cross-platform detection logic
    pass
```

### Library Management
```python
# Type-safe library operations
from typing import Protocol

class LibraryManager(Protocol):
    """Protocol for library management operations."""
    
    def add_library(self, library_path: Path, library_type: str) -> bool:
        """Add library to KiCad configuration."""
        ...
    
    def remove_library(self, library_name: str) -> bool:
        """Remove library from KiCad configuration."""
        ...
```

## SOLID Principles for CLI Tools

- **S**ingle Responsibility: Each command does one thing well
- **O**pen/Closed: Extensible for new KiCad features without modifying core
- **L**iskov Substitution: All library types implement consistent interfaces
- **I**nterface Segregation: Small, focused command interfaces
- **D**ependency Inversion: Depend on abstractions, not concrete implementations

## Integration with KiCad

### KiCad Version Support
- **KiCad 9.x**: Primary support target
- **KiCad 8.x**: Full compatibility

### Configuration Files
- **Symbol libraries**: `.kicad_sym` files in symbol table
- **Footprint libraries**: `.pretty` directories in footprint table  
- **Environment variables**: `kicad_common.json` configuration
- **Project templates**: Template directory management

## Adding New Commands

**Step 1**: Create command module
```python
# commands/new_command/command.py
from typing import Annotated, Optional
import typer
from rich.console import Console

console = Console()

def new_command(
    option: Annotated[
        Optional[str], 
        typer.Option("--option", help="Command option")
    ] = None,
) -> None:
    """New command description."""
    # Implementation with proper type hints and Rich output
    console.print("Command executed successfully!")
```

**Step 2**: Register in CLI
```python
# main.py - Add to the CLI app
from .commands.new_command.command import new_command

app.command("new-command")(new_command)
```

**Step 3**: Add tests
```python
# tests/test_new_command.py  
def test_new_command():
    """Test new command functionality."""
    # Comprehensive test coverage
    pass
```

## Modernization Roadmap

### Phase 1: Infrastructure
- Modern build system (pyproject.toml with hatchling)
- Complete type safety (zero Any types, pyrefly validation)
- Professional code standards (no emojis, constants extracted)
- Comprehensive documentation structure

### Phase 2: Enhancement 
- Modern CLI framework (Typer + Rich for better UX)
- Development tooling (pre-commit hooks, quality pipeline)
- Enhanced error handling and user experience
- Cross-platform support improvements