"""
Pin command implementation for KiCad Library Manager.
"""

import sys
import click

from ..library_manager import find_kicad_config, list_libraries
from ..utils.env_vars import find_environment_variables, expand_user_path, update_pinned_libraries


@click.command()
@click.option(
    "--kicad-lib-dir",
    envvar="KICAD_USER_LIB",
    help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
)
@click.option(
    "--symbols", "-s",
    multiple=True,
    help="Symbol libraries to pin (can be specified multiple times)",
)
@click.option(
    "--footprints", "-f", 
    multiple=True,
    help="Footprint libraries to pin (can be specified multiple times)",
)
@click.option(
    "--all/--selected",
    default=True,
    show_default=True,
    help="Pin all available libraries or only selected ones",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@click.option(
    "--max-backups",
    default=5,
    show_default=True,
    help="Maximum number of backups to keep",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show verbose output for debugging",
)
def pin(kicad_lib_dir, symbols, footprints, all, dry_run, max_backups, verbose):
    """Pin libraries in KiCad for quick access"""
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            sys.exit(1)
    
    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    
    if verbose:
        click.echo(f"Using KiCad library directory: {kicad_lib_dir}")
    
    # Find KiCad configuration
    try:
        kicad_config = find_kicad_config()
        if verbose:
            click.echo(f"Found KiCad configuration at: {kicad_config}")
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)
    
    # If --all is specified, get all libraries from the directory
    if all and not symbols and not footprints:
        try:
            symbol_libs, footprint_libs = list_libraries(kicad_lib_dir)
            symbols = symbol_libs
            footprints = footprint_libs
            if verbose:
                click.echo(f"Found {len(symbols)} symbol libraries and {len(footprints)} footprint libraries")
        except Exception as e:
            click.echo(f"Error listing libraries: {e}", err=True)
            sys.exit(1)
    
    # Convert tuples to lists if needed
    if isinstance(symbols, tuple):
        symbols = list(symbols)
    if isinstance(footprints, tuple):
        footprints = list(footprints)
    
    # Validate that libraries exist
    if not all and (symbols or footprints):
        try:
            available_symbols, available_footprints = list_libraries(kicad_lib_dir)
            
            # Check symbols
            for symbol in symbols:
                if symbol not in available_symbols:
                    click.echo(f"Warning: Symbol library '{symbol}' not found", err=True)
            
            # Check footprints
            for footprint in footprints:
                if footprint not in available_footprints:
                    click.echo(f"Warning: Footprint library '{footprint}' not found", err=True)
        except Exception as e:
            click.echo(f"Error validating libraries: {e}", err=True)
            # Continue anyway, in case the libraries are configured but not in the directory
    
    try:
        changes_needed = update_pinned_libraries(
            kicad_config,
            symbol_libs=symbols,
            footprint_libs=footprints,
            dry_run=dry_run,
            max_backups=max_backups
        )
        
        if changes_needed:
            if dry_run:
                click.echo(f"Would pin {len(symbols)} symbol and {len(footprints)} footprint libraries in KiCad")
            else:
                click.echo(f"Pinned {len(symbols)} symbol and {len(footprints)} footprint libraries in KiCad")
                click.echo(f"Created backup of kicad_common.json")
                click.echo("Restart KiCad for changes to take effect")
        else:
            click.echo("No changes needed, libraries already pinned in KiCad")
        
        if verbose:
            if symbols:
                click.echo("\nPinned Symbol Libraries:")
                for symbol in sorted(symbols):
                    click.echo(f"  - {symbol}")
            
            if footprints:
                click.echo("\nPinned Footprint Libraries:")
                for footprint in sorted(footprints):
                    click.echo(f"  - {footprint}")
    except Exception as e:
        click.echo(f"Error pinning libraries: {e}", err=True)
        sys.exit(1) 