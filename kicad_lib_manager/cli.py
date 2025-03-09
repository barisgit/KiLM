#!/usr/bin/env python3
"""
Command-line interface for KiCad Library Manager
"""

import os
import sys
import click
from pathlib import Path

from . import __version__
from .config import Config
from .library_manager import (
    add_libraries,
    list_libraries,
    find_kicad_config,
)
from .utils.env_vars import find_environment_variables, expand_user_path
from .utils.backup import create_backup


@click.group()
@click.version_option(version=__version__)
def main():
    """KiCad Library Manager - Manage KiCad libraries

    This tool helps configure and manage KiCad libraries across your projects.
    """
    pass


@main.command()
@click.option(
    "--kicad-lib-dir",
    envvar="KICAD_USER_LIB",
    help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
)
@click.option(
    "--kicad-3d-dir",
    envvar="KICAD_3D_LIB",
    help="KiCad 3D models directory (uses KICAD_3D_LIB env var if not specified)",
)
@click.option(
    "--max-backups",
    default=5,
    show_default=True,
    help="Maximum number of backups to keep",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
def setup(kicad_lib_dir, kicad_3d_dir, max_backups, dry_run):
    """Configure KiCad to use libraries in the specified directory"""
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            sys.exit(1)
    
    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    if kicad_3d_dir:
        kicad_3d_dir = expand_user_path(kicad_3d_dir)
    
    click.echo(f"Using KiCad library directory: {kicad_lib_dir}")
    if kicad_3d_dir:
        click.echo(f"Using KiCad 3D models directory: {kicad_3d_dir}")
    
    # Find KiCad configuration
    try:
        kicad_config = find_kicad_config()
        click.echo(f"Found KiCad configuration at: {kicad_config}")
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)
    
    # Create backups
    if not dry_run:
        sym_table = kicad_config / "sym-lib-table"
        fp_table = kicad_config / "fp-lib-table"
        
        if sym_table.exists():
            create_backup(sym_table, max_backups)
        if fp_table.exists():
            create_backup(fp_table, max_backups)
    
    # Add libraries
    try:
        added_libraries = add_libraries(
            kicad_lib_dir, 
            kicad_config, 
            kicad_3d_dir=kicad_3d_dir,
            dry_run=dry_run
        )
        click.echo(f"Added {len(added_libraries)} libraries to KiCad configuration")
        if dry_run:
            click.echo("Dry run: No changes were made")
    except Exception as e:
        click.echo(f"Error adding libraries: {e}", err=True)
        sys.exit(1)
    
    if not dry_run:
        click.echo("Setup complete! Restart KiCad for changes to take effect.")


@main.command()
@click.option(
    "--kicad-lib-dir",
    envvar="KICAD_USER_LIB",
    help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
)
def list(kicad_lib_dir):
    """List available libraries in the specified directory"""
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            sys.exit(1)
    
    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    
    try:
        symbols, footprints = list_libraries(kicad_lib_dir)
        
        if symbols:
            click.echo("\nAvailable Symbol Libraries:")
            for symbol in sorted(symbols):
                click.echo(f"  - {symbol}")
        else:
            click.echo("No symbol libraries found")
        
        if footprints:
            click.echo("\nAvailable Footprint Libraries:")
            for footprint in sorted(footprints):
                click.echo(f"  - {footprint}")
        else:
            click.echo("No footprint libraries found")
    except Exception as e:
        click.echo(f"Error listing libraries: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 