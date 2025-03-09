"""
Init command implementation for KiCad Library Manager.
Initializes the current directory as a KiCad library directory (symbols, footprints, templates).
"""

import os
import sys
import click
import yaml
from pathlib import Path

from ..config import Config
from ..utils.metadata import (
    read_github_metadata,
    write_github_metadata,
    get_default_github_metadata,
    generate_env_var_name,
    GITHUB_METADATA_FILE
)


@click.command()
@click.option(
    "--name",
    help="Name for this library collection (automatic if not provided)",
    default=None,
)
@click.option(
    "--set-current",
    is_flag=True,
    default=True,
    help="Set this as the current active library",
    show_default=True,
)
@click.option(
    "--description",
    help="Description for this library collection",
    default=None,
)
@click.option(
    "--env-var",
    help="Custom environment variable name for this library",
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
def init(name, set_current, description, env_var, force, no_env_var):
    """Initialize the current directory as a KiCad library collection.
    
    This command sets up the current directory as a KiCad library containing
    symbols, footprints, and templates. It creates the required folders if they
    don't exist and registers the library in the local configuration.
    
    Each library can have its own unique environment variable name, which
    will be used when setting up KiCad. This allows you to have multiple symbol/footprint
    libraries and reference them individually.
    
    If a metadata file (kilm.yaml) already exists, information from it will be
    used unless overridden by command line options.
    
    This is intended for GitHub-based libraries containing symbols and footprints,
    not for 3D model libraries.
    """
    current_dir = Path.cwd().resolve()
    click.echo(f"Initializing KiCad library at: {current_dir}")
    
    # Check for existing metadata
    metadata = read_github_metadata(current_dir)
    
    if metadata and not force:
        click.echo(f"Found existing metadata file ({GITHUB_METADATA_FILE}).")
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
            write_github_metadata(current_dir, metadata)
            click.echo(f"Updated metadata file with new information.")
    else:
        # Create a new metadata file
        if metadata and force:
            click.echo(f"Overwriting existing metadata file ({GITHUB_METADATA_FILE}).")
        else:
            click.echo(f"Creating new metadata file ({GITHUB_METADATA_FILE}).")
        
        # Generate metadata
        metadata = get_default_github_metadata(current_dir)
        
        # Override with command line parameters if provided
        if name:
            metadata["name"] = name
            # If name is provided but env_var isn't, regenerate the env_var based on the new name
            if not env_var and not no_env_var:
                metadata["env_var"] = generate_env_var_name(name, "KICAD_LIB")
        
        if description:
            metadata["description"] = description
        
        if env_var:
            metadata["env_var"] = env_var
        elif no_env_var:
            metadata["env_var"] = None
        
        # Write metadata file
        write_github_metadata(current_dir, metadata)
        click.echo(f"Metadata file created.")
        
        library_name = metadata["name"]
        library_env_var = metadata.get("env_var")
    
    # Create library directory structure if folders don't exist
    required_folders = ["symbols", "footprints", "templates"]
    existing_folders = []
    created_folders = []
    
    for folder in required_folders:
        folder_path = current_dir / folder
        if folder_path.exists():
            existing_folders.append(folder)
        else:
            try:
                os.makedirs(folder_path, exist_ok=True)
                created_folders.append(folder)
            except Exception as e:
                click.echo(f"Error creating {folder} directory: {e}", err=True)
                sys.exit(1)
    
    # Create empty library_descriptions.yaml if it doesn't exist
    library_descriptions_file = current_dir / "library_descriptions.yaml"
    if not library_descriptions_file.exists():
        try:
            # Create a template with comments and examples
            template_content = """# Library Descriptions for KiCad
# Format: 
#   library_name: "Description text"
# 
# Example:
#   Symbols_library: "Sample symbol library description"

# Symbol library descriptions
symbols:
  Symbols_library: "Sample symbol library description"

# Footprint library descriptions
footprints:
  Footprints_library: "Sample footprint library description"
"""
            with open(library_descriptions_file, "w") as f:
                f.write(template_content)
            click.echo(f"Created library_descriptions.yaml template file.")
        except Exception as e:
            click.echo(f"Warning: Could not create library_descriptions.yaml file: {e}", err=True)
    
    # Update the metadata with current capabilities
    updated_capabilities = {
        "symbols": (current_dir / "symbols").exists(),
        "footprints": (current_dir / "footprints").exists(),
        "templates": (current_dir / "templates").exists()
    }
    metadata["capabilities"] = updated_capabilities
    write_github_metadata(current_dir, metadata)
    
    # Report on folder status
    if existing_folders:
        click.echo(f"Found existing folders: {', '.join(existing_folders)}")
    if created_folders:
        click.echo(f"Created new folders: {', '.join(created_folders)}")
    
    # Verify if this looks like a KiCad library
    if not created_folders and not existing_folders:
        click.echo("Warning: No library folders were found or created.")
        if not click.confirm("Continue anyway?", default=True):
            click.echo("Initialization cancelled.")
            sys.exit(0)
    
    # Update the configuration
    try:
        config = Config()
        # Record as a GitHub library (symbols + footprints)
        config.add_library(library_name, str(current_dir), "github")
        
        if set_current:
            config.set_current_library(str(current_dir))
        
        click.echo(f"Library '{library_name}' initialized successfully!")
        click.echo(f"Type: GitHub library (symbols, footprints, templates)")
        click.echo(f"Path: {current_dir}")
        
        if library_env_var:
            click.echo(f"Assigned environment variable: {library_env_var}")
        
        if set_current:
            click.echo("This is now your current active library.")
            click.echo("kilm will use this library for all commands by default.")
        
        # Add a hint for adding 3D models
        click.echo("\nTo add a 3D models directory (typically stored in the cloud), use:")
        click.echo("  kilm add-3d --name my-3d-models --directory /path/to/3d/models")
    except Exception as e:
        click.echo(f"Error initializing library: {e}", err=True)
        sys.exit(1) 