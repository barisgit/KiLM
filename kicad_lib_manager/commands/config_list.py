"""
List configurations command implementation for KiCad Library Manager.
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


@click.command()
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
def config_list(library_type, verbose):
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