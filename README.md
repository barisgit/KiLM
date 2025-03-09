# KiCad Library Manager

A command-line tool for managing KiCad libraries across projects and workstations.

## Features

- Automatically detect KiCad configurations across different platforms (Windows, macOS, Linux)
- Add symbol and footprint libraries to KiCad from a centralized repository
- Create timestamped backups of configuration files
- Support for environment variables
- Dry-run mode to preview changes
- Compatible with KiCad 6.x and newer

## Installation

### From PyPI

```bash
pip install kicad-lib-manager
```

### From Source

```bash
git clone https://github.com/yourusername/kicad-lib-manager.git
cd kicad-lib-manager
pip install -e .
```

## Usage

### Setting Up Environment Variables

1. Define the following environment variables in your shell configuration:

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

2. Source your configuration or restart your terminal

### Configure KiCad Libraries

```bash
# Using environment variables
kicad-lib-manager setup

# Explicitly specify paths
kicad-lib-manager setup --kicad-lib-dir ~/path/to/libraries --kicad-3d-dir ~/path/to/3d-models

# Preview changes without making them (dry run)
kicad-lib-manager setup --dry-run
```

### List Available Libraries

```bash
kicad-lib-manager list
```

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
