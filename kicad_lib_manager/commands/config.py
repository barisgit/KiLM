"""
Configuration commands implementation for KiCad Library Manager.
Provides commands for managing KiCad Library Manager configuration.
"""

import sys
import click
from pathlib import Path

from ..config import Config
from ..utils.metadata import (
    read_github_metadata, 
    read_cloud_metadata,
    GITHUB_METADATA_FILE,
    CLOUD_METADATA_FILE
)


@click.group()
def config():
    """Manage KiCad Library Manager configuration.
    
    This command group allows you to list, set defaults, and remove 
    configuration entries for KiCad Library Manager.
    """
    pass


@config.command()
@click.option(
    "--type",
    "library_type",
    type=click.Choice(["github", "cloud", "all"]),
    default="all",
    help="Type of libraries to list (github=symbols/footprints, cloud=3D models)",
    show_default=True,
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show more information about libraries",
)
def list(library_type, verbose):
    """List all configured libraries in kilm.
    
    This shows all libraries stored in the kilm configuration file.
    There are two types of libraries:
    
    1. GitHub libraries - containing symbols and footprints (type: github)
    2. Cloud libraries - containing 3D models (type: cloud)
    
    Use --verbose to see metadata information stored in the library directories.
    """
    try:
        config = Config()
        
        # Get libraries of specified type
        if library_type == "all":
            libraries = config.get_libraries()
        else:
            libraries = config.get_libraries(library_type)
        
        # Get current library
        current_library = config.get_current_library()
        
        if not libraries:
            click.echo("No libraries configured.")
            click.echo("Use 'kilm init' to initialize a GitHub library.")
            click.echo("Use 'kilm add-3d' to add a cloud-based 3D model library.")
            return
        
        click.echo("Configured Libraries:")
        
        # Group libraries by type
        types = {"github": [], "cloud": []}
        for lib in libraries:
            lib_type = lib.get("type", "unknown")
            if lib_type in types:
                types[lib_type].append(lib)
        
        # Print libraries grouped by type
        if library_type in ["all", "github"] and types["github"]:
            click.echo("\nGitHub Libraries (symbols, footprints, templates):")
            for lib in types["github"]:
                name = lib.get("name", "unnamed")
                path = lib.get("path", "unknown")
                path_obj = Path(path)
                
                # Mark current library
                current_marker = ""
                if path == current_library:
                    current_marker = " (current)"
                
                if verbose:
                    click.echo(f"  - {name}{current_marker}:")
                    click.echo(f"      Path: {path}")
                    
                    # Show metadata if available
                    metadata = read_github_metadata(path_obj)
                    if metadata:
                        click.echo(f"      Metadata: {GITHUB_METADATA_FILE} present")
                        if "description" in metadata:
                            click.echo(f"      Description: {metadata['description']}")
                        if "version" in metadata:
                            click.echo(f"      Version: {metadata['version']}")
                        if "env_var" in metadata and metadata["env_var"]:
                            click.echo(f"      Environment Variable: {metadata['env_var']}")
                        if "capabilities" in metadata:
                            caps = metadata["capabilities"]
                            click.echo(f"      Capabilities: " + 
                                      f"symbols={'✓' if caps.get('symbols') else '✗'}, " +
                                      f"footprints={'✓' if caps.get('footprints') else '✗'}, " +
                                      f"templates={'✓' if caps.get('templates') else '✗'}")
                    else:
                        click.echo(f"      Metadata: No {GITHUB_METADATA_FILE} file")
                    
                    # Check for existence of key folders
                    folders = []
                    if (path_obj / "symbols").exists():
                        folders.append("symbols")
                    if (path_obj / "footprints").exists():
                        folders.append("footprints")
                    if (path_obj / "templates").exists():
                        folders.append("templates")
                    click.echo(f"      Folders: {', '.join(folders) if folders else 'none'}")
                else:
                    click.echo(f"  - {name}: {path}{current_marker}")
        
        if library_type in ["all", "cloud"] and types["cloud"]:
            click.echo("\nCloud Libraries (3D models):")
            for lib in types["cloud"]:
                name = lib.get("name", "unnamed")
                path = lib.get("path", "unknown")
                path_obj = Path(path)
                
                # Mark current library
                current_marker = ""
                if path == current_library:
                    current_marker = " (current)"
                
                if verbose:
                    click.echo(f"  - {name}{current_marker}:")
                    click.echo(f"      Path: {path}")
                    
                    # Show metadata if available
                    metadata = read_cloud_metadata(path_obj)
                    if metadata:
                        click.echo(f"      Metadata: {CLOUD_METADATA_FILE} present")
                        if "description" in metadata:
                            click.echo(f"      Description: {metadata['description']}")
                        if "version" in metadata:
                            click.echo(f"      Version: {metadata['version']}")
                        if "env_var" in metadata and metadata["env_var"]:
                            click.echo(f"      Environment Variable: {metadata['env_var']}")
                        if "model_count" in metadata:
                            click.echo(f"      3D Models: {metadata['model_count']}")
                    else:
                        click.echo(f"      Metadata: No {CLOUD_METADATA_FILE} file")
                        
                    # Count 3D model files if metadata not available or to verify
                    if not metadata or "model_count" not in metadata:
                        model_count = 0
                        for ext in ['.step', '.stp', '.wrl', '.wings']:
                            model_count += len(list(path_obj.glob(f'**/*{ext}')))
                        click.echo(f"      3D Models: {model_count} (counted)")
                else:
                    click.echo(f"  - {name}: {path}{current_marker}")
        
        # Print helpful message if no libraries match the filter
        if library_type == "github" and not types["github"]:
            click.echo("No GitHub libraries configured.")
            click.echo("Use 'kilm init' to initialize a GitHub library.")
        elif library_type == "cloud" and not types["cloud"]:
            click.echo("No cloud libraries configured.")
            click.echo("Use 'kilm add-3d' to add a cloud-based 3D model library.")
    
    except Exception as e:
        click.echo(f"Error listing configurations: {e}", err=True)
        sys.exit(1)


@config.command()
@click.argument("library_name", required=False)
@click.option(
    "--type",
    "library_type",
    type=click.Choice(["github", "cloud"]),
    default="github",
    help="Type of library to set as default (github=symbols/footprints, cloud=3D models)",
    show_default=True,
)
def set_default(library_name, library_type):
    """Set a library as the default for operations.
    
    Sets the specified library as the default for future operations.
    The default library is used by commands when no specific library is specified.
    
    If LIBRARY_NAME is not provided, the command will prompt you to select
    from the available libraries of the specified type.
    
    Examples:
    
    \b
    # Set a GitHub library as default
    kilm config set-default my-library
    
    \b
    # Set a Cloud library as default
    kilm config set-default my-3d-library --type cloud
    
    \b
    # Interactively select a library to set as default
    kilm config set-default
    
    \b
    # Interactively select a Cloud library to set as default
    kilm config set-default --type cloud
    """
    try:
        config = Config()
        
        # Get libraries of specified type
        libraries = config.get_libraries(library_type)
        
        if not libraries:
            click.echo(f"No {library_type} libraries configured.")
            if library_type == "github":
                click.echo("Use 'kilm init' to initialize a GitHub library.")
            else:
                click.echo("Use 'kilm add-3d' to add a cloud-based 3D model library.")
            sys.exit(1)
        
        # Get current library path
        current_library = config.get_current_library()
        
        # If library name not provided, prompt for selection
        if not library_name:
            click.echo(f"\nAvailable {library_type} libraries:")
            
            # Show numbered list of libraries
            for i, lib in enumerate(libraries):
                name = lib.get("name", "unnamed")
                path = lib.get("path", "unknown")
                
                # Mark current library
                current_marker = ""
                if path == current_library:
                    current_marker = " (current)"
                
                click.echo(f"{i+1}. {name}{current_marker}")
            
            # Get selection
            while True:
                try:
                    selection = click.prompt(
                        "Select library (number)",
                        type=int,
                        default=1
                    )
                    if 1 <= selection <= len(libraries):
                        selected_lib = libraries[selection-1]
                        library_name = selected_lib.get("name")
                        library_path = selected_lib.get("path")
                        break
                    else:
                        click.echo(f"Please enter a number between 1 and {len(libraries)}")
                except ValueError:
                    click.echo("Please enter a valid number")
        else:
            # Find the library by name
            library_path = None
            for lib in libraries:
                if lib.get("name") == library_name:
                    library_path = lib.get("path")
                    break
            
            if not library_path:
                click.echo(f"No {library_type} library named '{library_name}' found.")
                click.echo(f"Use 'kilm config list' to see available libraries.")
                sys.exit(1)
        
        # Set as current library
        config.set_current_library(library_path)
        click.echo(f"Set {library_type} library '{library_name}' as default.")
        click.echo(f"Path: {library_path}")
        
    except Exception as e:
        click.echo(f"Error setting default library: {e}", err=True)
        sys.exit(1)


@config.command()
@click.argument("library_name", required=True)
@click.option(
    "--type",
    "library_type",
    type=click.Choice(["github", "cloud", "all"]),
    default="all",
    help="Type of library to remove (all=remove from both types)",
    show_default=True,
)
@click.option(
    "--force",
    is_flag=True,
    help="Force removal without confirmation",
)
def remove(library_name, library_type, force):
    """Remove a library from the configuration.
    
    Removes the specified library from the KiCad Library Manager configuration.
    This does not delete any files, it only removes the library from the configuration.
    
    Examples:
    
    \b
    # Remove a library (prompts for confirmation)
    kilm config remove my-library
    
    \b
    # Remove a specific library type
    kilm config remove my-library --type github
    
    \b
    # Force removal without confirmation
    kilm config remove my-library --force
    """
    try:
        config = Config()
        
        # Get current library path
        current_library = config.get_current_library()
        
        # Get all libraries
        all_libraries = config.get_libraries()
        
        # Find libraries matching the name and type
        matching_libraries = []
        for lib in all_libraries:
            if lib.get("name") == library_name:
                if library_type == "all" or lib.get("type") == library_type:
                    matching_libraries.append(lib)
        
        if not matching_libraries:
            if library_type == "all":
                click.echo(f"No library named '{library_name}' found.")
            else:
                click.echo(f"No {library_type} library named '{library_name}' found.")
            click.echo(f"Use 'kilm config list' to see available libraries.")
            sys.exit(1)
        
        # Confirm removal
        if not force:
            for lib in matching_libraries:
                lib_type = lib.get("type", "unknown")
                lib_path = lib.get("path", "unknown")
                click.echo(f"Will remove {lib_type} library '{library_name}' from configuration.")
                click.echo(f"Path: {lib_path}")
                
                if lib_path == current_library:
                    click.echo(f"Warning: This is the current default library.")
                
            if not click.confirm("Continue?"):
                click.echo("Operation cancelled.")
                return
        
        # Remove libraries
        removed_count = 0
        for lib in matching_libraries:
            lib_type = lib.get("type", "unknown")
            removed = config.remove_library(library_name, lib_type)
            if removed:
                removed_count += 1
        
        if removed_count > 0:
            if removed_count == 1:
                click.echo(f"Removed library '{library_name}' from configuration.")
            else:
                click.echo(f"Removed {removed_count} instances of library '{library_name}' from configuration.")
            
            # Check if we removed the current library
            current_library_new = config.get_current_library()
            if current_library and current_library != current_library_new:
                click.echo("Note: Default library was changed as the previous default was removed.")
        else:
            click.echo("No libraries were removed.")
        
    except Exception as e:
        click.echo(f"Error removing library: {e}", err=True)
        sys.exit(1)


# Register the config command
if __name__ == "__main__":
    config() 