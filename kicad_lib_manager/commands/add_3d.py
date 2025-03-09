"""
Add cloud-based 3D models directory command for KiCad Library Manager.
"""

import sys
import click
from pathlib import Path

from ..config import Config
from ..utils.metadata import (
    read_cloud_metadata,
    write_cloud_metadata,
    get_default_cloud_metadata,
    generate_env_var_name,
    CLOUD_METADATA_FILE
)


@click.command()
@click.option(
    "--name",
    help="Name for this 3D models collection (automatic if not provided)",
    default=None,
)
@click.option(
    "--directory",
    help="Directory containing 3D models (default: current directory)",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True),
)
@click.option(
    "--description",
    help="Description for this 3D models collection",
    default=None,
)
@click.option(
    "--env-var",
    help="Custom environment variable name for this 3D model library",
    default=None,
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing metadata file if present",
    show_default=True,
)
@click.option(
    "--no-env-var",
    is_flag=True,
    default=False,
    help="Don't assign an environment variable to this library",
    show_default=True,
)
def add_3d(name, directory, description, env_var, force, no_env_var):
    """Add a cloud-based 3D models directory to the configuration.
    
    This command registers a directory containing 3D models that are typically
    stored in cloud storage (Dropbox, Google Drive, etc.) rather than in GitHub.
    
    Each 3D model library gets its own unique environment variable name, which
    will be used when setting up KiCad. This allows you to have multiple 3D model
    libraries and reference them individually.
    
    If a metadata file (.kilm_metadata) already exists, information from it will be
    used unless overridden by command line options.
    
    If no directory is specified, the current directory will be used.
    """
    # Use current directory if not specified
    if not directory:
        directory = Path.cwd().resolve()
    else:
        directory = Path(directory).resolve()
    
    click.echo(f"Adding cloud-based 3D models directory: {directory}")
    
    # Check for existing metadata
    metadata = read_cloud_metadata(directory)
    
    if metadata and not force:
        click.echo(f"Found existing metadata file ({CLOUD_METADATA_FILE}).")
        library_name = metadata.get("name")
        library_description = metadata.get("description")
        library_env_var = metadata.get("env_var")
        click.echo(f"Using existing name: {library_name}")
        
        # Show environment variable if present
        if library_env_var and not no_env_var:
            click.echo(f"Using existing environment variable: {library_env_var}")
        
        # Override with command line parameters if provided
        if name:
            library_name = name
            click.echo(f"Overriding with provided name: {library_name}")
        
        if description:
            library_description = description
            click.echo(f"Overriding with provided description: {library_description}")
        
        if env_var:
            library_env_var = env_var
            click.echo(f"Overriding with provided environment variable: {library_env_var}")
        elif no_env_var:
            library_env_var = None
            click.echo("Disabling environment variable as requested")
            
        # Update metadata if command line parameters were provided
        if name or description or env_var or no_env_var:
            metadata["name"] = library_name
            metadata["description"] = library_description
            if library_env_var and not no_env_var:
                metadata["env_var"] = library_env_var
            else:
                metadata["env_var"] = None
            metadata["updated_with"] = "kilm"
            write_cloud_metadata(directory, metadata)
            click.echo(f"Updated metadata file with new information.")
    else:
        # Create a new metadata file
        if metadata and force:
            click.echo(f"Overwriting existing metadata file ({CLOUD_METADATA_FILE}).")
        else:
            click.echo(f"Creating new metadata file ({CLOUD_METADATA_FILE}).")
        
        # Generate metadata
        metadata = get_default_cloud_metadata(directory)
        
        # Override with command line parameters if provided
        if name:
            metadata["name"] = name
            # If name is provided but env_var isn't, regenerate the env_var based on the new name
            if not env_var and not no_env_var:
                metadata["env_var"] = generate_env_var_name(name, "KICAD_3D")
        
        if description:
            metadata["description"] = description
        
        if env_var:
            metadata["env_var"] = env_var
        elif no_env_var:
            metadata["env_var"] = None
        
        # Write metadata file
        write_cloud_metadata(directory, metadata)
        click.echo(f"Metadata file created.")
        
        library_name = metadata["name"]
        library_env_var = metadata.get("env_var")
    
    # Verify if this looks like a 3D model directory
    model_extensions = ['.step', '.stp', '.wrl', '.wings']
    found_models = False
    
    # Do a quick check for model files
    for ext in model_extensions:
        if list(directory.glob(f'**/*{ext}')):
            found_models = True
            break
    
    if not found_models:
        click.echo("Warning: No 3D model files found in this directory.")
        if not click.confirm("Continue anyway?", default=True):
            click.echo("Operation cancelled.")
            sys.exit(0)
    
    # Update metadata with actual model count
    model_count = 0
    for ext in model_extensions:
        model_count += len(list(directory.glob(f'**/*{ext}')))
    
    metadata["model_count"] = model_count
    write_cloud_metadata(directory, metadata)
    
    # Update the configuration
    try:
        config = Config()
        # Add as a cloud-based 3D model library
        config.add_library(library_name, str(directory), "cloud")
        
        click.echo(f"3D models directory '{library_name}' added successfully!")
        click.echo(f"Path: {directory}")
        if model_count > 0:
            click.echo(f"Found {model_count} 3D model files.")
        
        if library_env_var:
            click.echo(f"Assigned environment variable: {library_env_var}")
            click.echo("\nYou can use this directory with:")
            click.echo(f"  kilm setup --3d-lib-dirs '{library_name}'")
            click.echo(f"  # or by setting the environment variable")
            click.echo(f"  export {library_env_var}='{directory}'")
        
        # Show current cloud libraries
        libraries = config.get_libraries("cloud")
        if len(libraries) > 1:
            click.echo("\nAll registered cloud-based 3D model directories:")
            for lib in libraries:
                lib_name = lib.get("name", "unnamed")
                lib_path = lib.get("path", "unknown")
                lib_env_var = None
                
                # Try to get the environment variable from metadata
                try:
                    lib_metadata = read_cloud_metadata(Path(lib_path))
                    if lib_metadata and "env_var" in lib_metadata:
                        lib_env_var = lib_metadata["env_var"]
                except Exception:
                    pass
                
                if lib_env_var:
                    click.echo(f"  - {lib_name}: {lib_path} (ENV: {lib_env_var})")
                else:
                    click.echo(f"  - {lib_name}: {lib_path}")
    except Exception as e:
        click.echo(f"Error adding 3D models directory: {e}", err=True)
        sys.exit(1) 