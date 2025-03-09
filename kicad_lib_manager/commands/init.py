"""
Init command implementation for KiCad Library Manager.
Initializes the current directory as a KiCad library directory (symbols, footprints, templates).
"""

import os
import sys
import click
from pathlib import Path

from ..config import Config
from ..utils.metadata import (
    read_github_metadata,
    write_github_metadata,
    get_default_github_metadata,
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
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing metadata file if present",
    show_default=True,
)
def init(name, set_current, description, force):
    """Initialize the current directory as a KiCad library collection.
    
    This command sets up the current directory as a KiCad library containing
    symbols, footprints, and templates. It creates the required folders if they
    don't exist and registers the library in the local configuration.
    
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
        click.echo(f"Using existing name: {library_name}")
        
        # Override with command line parameters if provided
        if name:
            library_name = name
            click.echo(f"Overriding with provided name: {library_name}")
        
        if description:
            library_description = description
            click.echo(f"Overriding with provided description: {library_description}")
            
        # Update metadata if command line parameters were provided
        if name or description:
            metadata["name"] = library_name
            metadata["description"] = library_description
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
        
        if description:
            metadata["description"] = description
        
        # Write metadata file
        write_github_metadata(current_dir, metadata)
        click.echo(f"Metadata file created.")
        
        library_name = metadata["name"]
    
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
        
        if set_current:
            click.echo("This is now your current active library.")
            click.echo("kilm will use this library for all commands by default.")
        
        # Add a hint for adding 3D models
        click.echo("\nTo add a 3D models directory (typically stored in the cloud), use:")
        click.echo("  kilm add-3d --name my-3d-models --directory /path/to/3d/models")
    except Exception as e:
        click.echo(f"Error initializing library: {e}", err=True)
        sys.exit(1) 