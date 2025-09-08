# KiLM (KiCad Library Manager) Plan - Cross-Platform KiCad Library Management

KiLM is a **command-line tool for managing KiCad libraries** across projects and workstations. It provides reliable library installation, configuration management, and project template support.

## Goals

- **Cross-platform KiCad support** - Automatic detection of KiCad configurations on Windows, macOS, Linux
- **Library management** - Add symbol and footprint libraries from centralized repositories
- **Configuration management** - Set environment variables and manage KiCad settings
- **Project templates** - Create and manage standardized project templates
- **Backup and restore** - Timestamped backups of configuration files
- **Developer workflow** - Integrate with existing KiCad workflows seamlessly

## Non-Goals

- Creating KiCad libraries (use KiCad's built-in tools)
- PCB design or schematic capture (handled by KiCad)
- Version control for design files (use Git directly)
- Web interface or GUI (CLI-focused tool)

---

## High-Level Architecture

**KiLM Workflow**:

1. **Detection**: Automatically find KiCad installations and configuration files
2. **Library Management**: Add/remove libraries from centralized repositories
3. **Configuration**: Update KiCad settings and environment variables
4. **Templates**: Create projects from standardized templates
5. **Backup**: Maintain timestamped backups for safety

**User Workflow**:
```bash
# Initialize library setup
kilm init

# Configure KiCad to use libraries
kilm setup

# Check current status
kilm status

# Add libraries
kilm list
kilm pin my-favorite-library

# Create projects from templates
kilm template create MyProject --template basic-project
```

---

## CLI Architecture

KiLM follows a **simple, focused command structure**:

### Core Commands
- **`kilm init`** - Initialize library configuration
- **`kilm setup`** - Configure KiCad to use managed libraries  
- **`kilm status`** - Show current configuration and library status
- **`kilm list`** - List available libraries from repositories

### Library Management
- **`kilm pin <library>`** - Pin favorite libraries for quick access
- **`kilm unpin <library>`** - Unpin libraries
- **`kilm add-3d <path>`** - Add 3D model libraries
- **`kilm sync`** - Update library definitions

### Configuration & Templates
- **`kilm config`** - Manage configuration settings
- **`kilm template`** - Project template management
- **`kilm add-hook`** - Add project creation hooks

### Design Principles
- **Cross-platform first** - Support Windows, macOS, Linux equally
- **Safe operations** - Always backup before making changes
- **Clear feedback** - Informative messages and status reporting
- **Backward compatibility** - Work with KiCad 8.x and newer

---

## KiCad Integration Model

### KiCad Configuration Files
- **Symbol libraries**: Managed via `sym-lib-table`
- **Footprint libraries**: Managed via `fp-lib-table`  
- **Environment variables**: Set in `kicad_common.json`
- **Project templates**: Managed in dedicated template directories

### Cross-Platform Support
- **Windows**: `%APPDATA%/kicad/` and similar paths
- **macOS**: `~/Library/Preferences/kicad/` and `~/Documents/KiCad/`
- **Linux**: `~/.config/kicad/` and `~/Documents/KiCad/`

### Library Types
- **GitHub repositories** - Clone and manage Git-based libraries
- **Local directories** - Add existing local library paths
- **Downloaded archives** - Extract and manage ZIP/TAR libraries

---

## Configuration Model (Type-Safe)

KiLM uses **type-safe configuration management**:

```python
# Type-safe library configuration
class LibraryConfig:
    name: str
    path: str
    type: str  # github, local, archive
    enabled: bool = True

# Cross-platform KiCad detection
class KiCadConfig:
    version: str
    config_path: Path
    library_tables: Dict[str, Path]
    environment_vars: Dict[str, str]
    
# Template system
class ProjectTemplate:
    name: str
    description: str
    variables: Dict[str, str]
    files: List[Path]
    hooks: Optional[Path] = None
```

### Professional Standards
- **No hardcoded paths** - All paths use configuration constants
- **Type safety** - Comprehensive type hints, no `Any` types
- **Error handling** - Graceful failure with informative messages  
- **Professional output** - No emojis, clear command-line interface

---

## Current Architecture Status

### Working Well
- **Comprehensive CLI** - Full command set with Click framework
- **Cross-platform detection** - KiCad configuration discovery
- **Library management** - Add/remove libraries reliably
- **Project templates** - Template creation and management
- **Backup system** - Timestamped configuration backups
- **Good test coverage** - Comprehensive test suite

### Recently Modernized
- **Build system** - Migrated from setup.py to pyproject.toml with hatchling
- **Code quality** - Removed emojis, extracted hardcoded constants
- **Documentation** - Added PLAN.md and CONTRIBUTING.md
- **Type safety** - Improved type annotations (ongoing)

### Future Enhancements
- **CLI framework** - Migrate Click → Typer for better type safety
- **Terminal UI** - Add Rich integration for enhanced output
- **Pre-commit hooks** - Automated quality checks
- **Performance** - Optimize library detection and operations

---

## Implementation Architecture

### Module Organization
```
kicad_lib_manager/
├── cli.py                 # Main CLI entry point (Click-based)
├── constants.py          # Configuration constants (NEW)
├── config.py             # Configuration management  
├── library_manager.py    # Core library operations
├── commands/             # Individual CLI commands
│   ├── init.py
│   ├── setup.py
│   ├── status.py
│   ├── template.py
│   └── ...
└── utils/               # Utility modules
    ├── backup.py        # Configuration backups
    ├── file_ops.py      # File operations
    ├── metadata.py      # Library metadata
    └── template.py      # Template management
```

### Key Design Patterns
- **Command pattern** - Each CLI command is a self-contained module
- **Configuration management** - Centralized config with type safety
- **Cross-platform abstraction** - Platform-specific logic isolated
- **Template system** - Jinja2-based project generation
- **Backup strategy** - Always backup before modifications

---

## Quality Standards

### Code Quality (Professional Standards)
- **Type safety** - Comprehensive type hints, no `Any` types
- **Constants** - No hardcoded strings or magic values
- **Error handling** - Graceful failure with helpful messages
- **Documentation** - Clear docstrings and API documentation
- **Testing** - Unit and integration test coverage

### User Experience
- **Clear commands** - Intuitive CLI with helpful output
- **Safe operations** - Backup before changes, confirmation prompts
- **Cross-platform** - Identical behavior across operating systems  
- **Professional output** - No emojis, consistent formatting

### Development Standards
- **Modern Python** - Uses pathlib, proper exception handling
- **Build system** - Modern pyproject.toml with hatchling
- **Quality tools** - Black, Ruff, Pyrefly for code quality
- **Documentation** - Comprehensive project documentation

---

## Success Criteria

- **Cross-platform reliability** - Works identically on Windows, macOS, Linux
- **Safe library management** - No data loss, always backup configurations
- **Developer productivity** - Quick project setup with templates
- **Professional quality** - Clean code, comprehensive documentation
- **KiCad integration** - Seamless integration with existing workflows
- **Type safety** - Complete type coverage with no `Any` types

---

## Modernization Status

### Phase 1: Infrastructure COMPLETED
- [x] **Modern build system** - pyproject.toml with hatchling
- [x] **Professional standards** - Removed emojis, extracted constants
- [x] **Task tracking** - Proper documentation workflow

### Phase 2: Enhancement (Future)
- [ ] **CLI modernization** - Migrate Click → Typer + Rich
- [ ] **Type safety** - Complete Any type elimination
- [ ] **Quality pipeline** - Pre-commit hooks, automated testing
- [ ] **Performance** - Optimize operations, better caching