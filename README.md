# KiCad Library Manager (KiLM)

[![PyPI version](https://img.shields.io/pypi/v/kilm.svg)](https://pypi.org/project/kilm/)
[![Python versions](https://img.shields.io/pypi/pyversions/kilm.svg)](https://pypi.org/project/kilm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A command-line tool for managing KiCad libraries across projects and workstations.

## Features

- Automatically detect KiCad configurations across different platforms (Windows, macOS, Linux)
- Add symbol and footprint libraries to KiCad from a centralized repository
- Set environment variables directly in KiCad configuration
- Pin favorite libraries for quick access in KiCad
- Create timestamped backups of configuration files (only when changes are needed)
- Support for environment variables
- Dry-run mode to preview changes
- Compatible with KiCad 6.x and newer
- Project template management to standardize new designs

## Requirements

- Python 3.7 or newer
- KiCad 6.x or newer (must be run at least once before using this tool)

### Dependencies

- click >= 8.0
- pyyaml >= 6.0
- pathlib >= 1.0.1
- pathspec >= 0.12.1
- jinja2 >= 3.1.6

## Installation

### From PyPI

```bash
pip install kilm
```

### Using pipx (recommended for CLI tools)

[pipx](https://pypa.github.io/pipx/) installs the tool in an isolated environment while making it available globally:

```bash
# Install pipx if you don't have it
python -m pip install --user pipx
python -m pipx ensurepath

# Install kilm
pipx install kilm
```

### Using uv (faster Python package installer)

[uv](https://github.com/astral-sh/uv) is a fast Python package installer and resolver:

```bash
# Install uv if you don't have it
curl -sSf https://astral.sh/uv/install.sh | sh

# Install kilm using uv
uv pip install kilm
```

### From source

```bash
git clone https://github.com/barisgit/kilm.git
cd kilm
pip install -e .
```

## Configuration

KiLM stores its configuration in the following location:

- **Linux/macOS**: `~/.config/kicad-lib-manager/`
- **Windows**: `%APPDATA%\kicad-lib-manager\`

The main configuration file is `config.yaml`, which contains information about your libraries and settings.

## Usage

### Initialize a Library

The first step is to initialize your KiCad library. This creates metadata for your library and registers it in the configuration:

```bash
# Initialize the current directory as a KiCad library
kilm init

# Initialize with a custom name
kilm init --name my-kicad-library

# Initialize with a description
kilm init --description "My custom KiCad library"

# Initialize with a custom environment variable
kilm init --env-var MY_CUSTOM_LIB
```

Note: Metadata for configurations is saved in ~/.config/kicad-lib-manager/

### Add a 3D Models Library

You can add multiple 3D model libraries, each with its own environment variable:

```bash
# Add the current directory as a 3D models library
kilm add-3d

# Add a specific directory
kilm add-3d --directory ~/path/to/3d-models

# Add with a custom name and environment variable
kilm add-3d --name my-3d-models --env-var MY_CUSTOM_3D_VAR
```

### View Configured Libraries

You can view all configured libraries with:

```bash
# List all configured libraries
kilm config list

# List only GitHub libraries (symbols/footprints)
kilm config list --type github

# List only cloud libraries (3D models)
kilm config list --type cloud

# Show detailed information
kilm config list --verbose
```

### Configure KiCad

With libraries initialized, you can set up KiCad to use them:

```bash
# Set up using the current libraries
kilm setup

# Set up all configured libraries
kilm setup --all-libraries

# Set up specific libraries by name
kilm setup --symbol-lib-dirs "main-lib,project-lib" --threed-lib-dirs "my-3d-models"

# Preview changes without making them (dry run)
kilm setup --dry-run

# Show verbose output for debugging
kilm setup --verbose
```

### Using Environment Variables (Legacy Method)

You can still use environment variables if preferred:

```bash
# For Bash/Zsh
export KICAD_USER_LIB=~/path/to/your/kicad-libraries
export KICAD_3D_LIB="~/path/to/your/kicad-3d-models"

# For Fish
set -U KICAD_USER_LIB ~/path/to/your/kicad-libraries
set -U KICAD_3D_LIB "~/path/to/your/kicad-3d-models"

# For Windows PowerShell
[System.Environment]::SetEnvironmentVariable("KICAD_USER_LIB", "C:\path\to\your\kicad-libraries", "User")
[System.Environment]::SetEnvironmentVariable("KICAD_3D_LIB", "C:\path\to\your\kicad-3d-models", "User")
```

### Managing Pinned Libraries

KiCad has a feature to pin libraries as favorites for quick access. You can manage these pinned libraries with:

```bash
# Pin all libraries from your library directory
kilm pin

# Pin specific libraries
kilm pin --symbols MySymbolLib AnotherLib --footprints MyFootprintLib

# Unpin specific libraries
kilm unpin --symbols LibToUnpin --footprints FootprintToUnpin

# Unpin all libraries
kilm unpin --all
```

### Working with Templates

KiLM provides tools for managing KiCad project templates, allowing you to create reusable project structures:

#### Creating a Template from an Existing Project

```bash
# Create a template named 'basic-project' from the current directory
# (will run in interactive mode by default)
kilm template make basic-project

# Create a template from a specific directory
kilm template make basic-project path/to/project

# Create a template with a description and use case
kilm template make basic-project --description "Basic KiCad project" \
    --use-case "Starting point for simple PCB designs"

# Create a template with variables
kilm template make basic-project --variable "author=John Doe"

# Preview template creation without making changes
kilm template make basic-project --dry-run

# Create a template without interactive prompts
kilm template make basic-project --non-interactive
```

#### Creating a Project from a Template

```bash
# Create a project named 'MyProject' in the current directory
kilm template create MyProject

# Create a project in a specific directory
kilm template create MyProject path/to/project

# Create a project with a specific template
kilm template create MyProject --template basic-project

# Set template variables
kilm template create MyProject --set-var author="John Doe" --set-var version=1.0

# Preview project creation without making changes
kilm template create MyProject --dry-run

# Skip post-creation hooks
kilm template create MyProject --skip-hooks
```

#### Listing Available Templates

```bash
# List all available templates
kilm template list

# List templates with detailed information including variables
kilm template list --verbose

# List templates from a specific library
kilm template list --library my-library

# Output template list in JSON format
kilm template list --json
```

#### Template Structure

Templates are stored in a `templates` directory within each library, with the following structure:

```
templates/
  template-name/
    metadata.yaml       # Template metadata and configuration
    hooks/
      post_create.py    # Post-creation hook script
    template/           # The actual template files
      {{ project_filename }}.kicad_pro.jinja2  # Main project file
      {{ project_filename }}.kicad_sch.jinja2  # Main schematic file
      {{ project_filename }}.kicad_pcb.jinja2  # Main PCB file
      README.md.jinja2                         # Documentation
      ...                                     # Other project files
```

The template files can use Jinja2 syntax for variable substitution, both in file contents and filenames. For example:

- A file named `{{ project_name }}_v{{ version }}.txt.jinja2` will be rendered as `MyProject_v1.0.txt` with the appropriate variables.
- The KiCad files use the `project_filename` variable to ensure consistent naming across all project files.

### List Available Libraries

```bash
kilm list
```

### Check Current Configuration

```bash
kilm status
```

This will show:
- kilm configuration details
- KiCad configuration directory location
- Environment variables set in KiCad
- Pinned libraries
- Currently configured symbol and footprint libraries

### Update Libraries

You can update all configured GitHub-based libraries with a single command:

```bash
# Update all configured GitHub libraries
kilm update

# Preview updates without making changes
kilm update --dry-run

# Show detailed output during update
kilm update --verbose
```

This will perform a `git pull` on all configured symbol and footprint libraries that are Git repositories, ensuring they're up-to-date with their remote sources.

### Add Git Hooks

You can add a Git post-merge hook to automatically update your KiCad libraries whenever you pull changes:

```bash
# Add hook to current Git repository
kilm add-hook

# Add hook to a different repository
kilm add-hook --directory ~/path/to/repo

# Overwrite existing hook if present
kilm add-hook --force
```

The hook will automatically run `kilm update` after every `git pull` or `git merge` operation, keeping your libraries up-to-date. If you want to automatically detect new libraries and add them to KiCad as well modify hook in `.git/hooks/post-merge` to run `kilm setup` (more risky).

## Custom Library Descriptions

The tool will look for a file called `library_descriptions.yaml` in your library directory with the following format:

```yaml
# Symbol library descriptions
symbols:
  LibraryName: "Custom description for the library"
  
# Footprint library descriptions
footprints:
  LibraryName: "Custom description for the library"
```

## Automatic Updates

For automatic library updates, you can create a Git hook in your project:

1. Create a script in your project called `update_library.sh`:

   ```bash
   #!/bin/bash
   echo "Updating KiCad libraries..."
   (cd $KICAD_USER_LIB && git pull)
   kicad-lib-manager setup --dry-run
   echo "If the changes look good, run 'kicad-lib-manager setup' to apply them."
   ```

2. Make it executable:

   ```bash
   chmod +x update_library.sh
   ```

3. Add a Git hook to run it automatically:

   ```bash
   mkdir -p .git/hooks
   cat > .git/hooks/post-merge << 'EOL'
   #!/bin/bash
   ./update_library.sh
   EOL
   chmod +x .git/hooks/post-merge
   ```

## Troubleshooting

### Common Issues

1. **KiCad configuration not found**
   
   Make sure KiCad has been run at least once on your system before using KiLM.

2. **Changes not appearing in KiCad**
   
   Restart KiCad after running `kilm setup` to load the new configuration.

3. **Environment variables not working**
   
   If using the environment variable method, ensure your shell has been restarted after setting them.

4. **Template creation failing**
   
   Check for non-standard files in your project that might be causing issues, and use the `--exclude` option to skip them.

## Development

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/barisgit/kilm.git
cd kilm

# Install development dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_config_commands.py

# Run with coverage
pytest --cov=kicad_lib_manager
```

### Code Formatting

Code is formatted using Black:

```bash
# Format code
black .
```

## License

See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
