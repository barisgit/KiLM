# KiCad Library Manager (KiLM)

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
kilm config

# List only GitHub libraries (symbols/footprints)
kilm config --type github

# List only cloud libraries (3D models)
kilm config --type cloud

# Show detailed information
kilm config --verbose
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

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

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

The hook will automatically run `kilm update` after every `git pull` or `git merge` operation, keeping your libraries up-to-date. If you want to automatically detect new libraries and add them to KiCad as well modify hook in `.git/post-merge` to run `kilm setup` (more risky).
