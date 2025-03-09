"""
Unpin command implementation for KiCad Library Manager.
"""

import sys
import json
import click

from ..library_manager import find_kicad_config
from ..utils.env_vars import update_pinned_libraries
from ..utils.backup import create_backup


@click.command()
@click.option(
    "--symbols", "-s",
    multiple=True,
    help="Symbol libraries to unpin (can be specified multiple times)",
)
@click.option(
    "--footprints", "-f", 
    multiple=True,
    help="Footprint libraries to unpin (can be specified multiple times)",
)
@click.option(
    "--all",
    is_flag=True,
    help="Unpin all libraries",
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
def unpin(symbols, footprints, all, dry_run, max_backups, verbose):
    """Unpin libraries in KiCad"""
    # Find KiCad configuration
    try:
        kicad_config = find_kicad_config()
        if verbose:
            click.echo(f"Found KiCad configuration at: {kicad_config}")
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)
    
    # Get the kicad_common.json file
    kicad_common = kicad_config / "kicad_common.json"
    if not kicad_common.exists():
        click.echo("KiCad common configuration file not found, nothing to unpin")
        return
    
    # If --all is specified, unpin all libraries
    if all:
        try:
            with open(kicad_common, "r") as f:
                config = json.load(f)
            
            # Get all pinned libraries from kicad_common.json
            if "session" in config:
                symbols = config["session"].get("pinned_symbol_libs", [])
                footprints = config["session"].get("pinned_fp_libs", [])
                
                if verbose:
                    if symbols:
                        click.echo(f"Found {len(symbols)} pinned symbol libraries")
                    if footprints:
                        click.echo(f"Found {len(footprints)} pinned footprint libraries")
            else:
                click.echo("No session information found in KiCad configuration, nothing to unpin")
                return
                
            if not symbols and not footprints:
                click.echo("No pinned libraries found, nothing to unpin")
                return
        except Exception as e:
            click.echo(f"Error reading pinned libraries: {e}", err=True)
            sys.exit(1)
    
    # If no libraries are specified, print an error
    if not symbols and not footprints and not all:
        click.echo("Error: No libraries specified to unpin", err=True)
        click.echo("Use --symbols, --footprints, or --all to specify libraries to unpin", err=True)
        sys.exit(1)
    
    # Convert tuples to lists if needed
    if isinstance(symbols, tuple):
        symbols = list(symbols)
    if isinstance(footprints, tuple):
        footprints = list(footprints)
    
    # Unpin the libraries by removing them from the kicad_common.json file
    try:
        with open(kicad_common, "r") as f:
            config = json.load(f)
        
        changes_needed = False
        
        # Ensure session section exists
        if "session" not in config:
            click.echo("No session information found in KiCad configuration, nothing to unpin")
            return
        
        # Handle symbol libraries
        if "pinned_symbol_libs" in config["session"] and symbols:
            current_symbols = config["session"]["pinned_symbol_libs"]
            new_symbols = [lib for lib in current_symbols if lib not in symbols]
            
            if len(new_symbols) != len(current_symbols):
                changes_needed = True
                if not dry_run:
                    config["session"]["pinned_symbol_libs"] = new_symbols
        
        # Handle footprint libraries
        if "pinned_fp_libs" in config["session"] and footprints:
            current_footprints = config["session"]["pinned_fp_libs"]
            new_footprints = [lib for lib in current_footprints if lib not in footprints]
            
            if len(new_footprints) != len(current_footprints):
                changes_needed = True
                if not dry_run:
                    config["session"]["pinned_fp_libs"] = new_footprints
        
        # Write changes if needed
        if changes_needed and not dry_run:
            # Create backup before making changes
            create_backup(kicad_common, max_backups)
            
            with open(kicad_common, "w") as f:
                json.dump(config, f, indent=2)
        
        if changes_needed:
            if dry_run:
                click.echo(f"Would unpin {len(symbols) if symbols else 0} symbol and {len(footprints) if footprints else 0} footprint libraries in KiCad")
            else:
                click.echo(f"Unpinned {len(symbols) if symbols else 0} symbol and {len(footprints) if footprints else 0} footprint libraries in KiCad")
                click.echo(f"Created backup of kicad_common.json")
                click.echo("Restart KiCad for changes to take effect")
        else:
            click.echo("No changes needed, libraries already unpinned in KiCad")
        
        if verbose:
            if symbols:
                click.echo("\nUnpinned Symbol Libraries:")
                for symbol in sorted(symbols):
                    click.echo(f"  - {symbol}")
            
            if footprints:
                click.echo("\nUnpinned Footprint Libraries:")
                for footprint in sorted(footprints):
                    click.echo(f"  - {footprint}")
                    
    except Exception as e:
        click.echo(f"Error unpinning libraries: {e}", err=True)
        sys.exit(1) 