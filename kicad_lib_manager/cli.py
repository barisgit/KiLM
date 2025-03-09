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
    list_configured_libraries,
    find_kicad_config,
)
from .utils.env_vars import find_environment_variables, expand_user_path, update_kicad_env_vars, update_pinned_libraries
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
@click.option(
    "--pin-libraries/--no-pin-libraries",
    default=True,
    show_default=True,
    help="Add libraries to KiCad pinned libraries for quick access",
)
def setup(kicad_lib_dir, kicad_3d_dir, max_backups, dry_run, pin_libraries):
    """Configure KiCad to use libraries in the specified directory"""
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            sys.exit(1)
            
    if not kicad_3d_dir:
        kicad_3d_dir = find_environment_variables("KICAD_3D_LIB")
        if not kicad_3d_dir:
            click.echo("Warning: KICAD_3D_LIB not set, 3D models might not work correctly", err=True)
    
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
    
    # Prepare environment variables dictionary
    env_vars = {"KICAD_USER_LIB": kicad_lib_dir}
    if kicad_3d_dir:
        env_vars["KICAD_3D_LIB"] = kicad_3d_dir
    
    # Initialize variables
    env_changes_needed = False
    
    # Update environment variables in KiCad configuration
    try:
        env_changes_needed = update_kicad_env_vars(kicad_config, env_vars, dry_run)
        if env_changes_needed:
            if dry_run:
                click.echo(f"Would update environment variables in KiCad configuration")
            else:
                click.echo(f"Updated environment variables in KiCad configuration")
        else:
            click.echo(f"Environment variables already up to date in KiCad configuration")
    except Exception as e:
        click.echo(f"Error updating environment variables: {e}", err=True)
        # Continue with the rest of the setup, but don't set env_changes_needed to True
    
    # Add libraries
    try:
        added_libraries, changes_needed = add_libraries(
            kicad_lib_dir, 
            kicad_config, 
            kicad_3d_dir=kicad_3d_dir,
            dry_run=dry_run
        )
        
        # Create backups only if changes are needed
        if changes_needed and not dry_run:
            sym_table = kicad_config / "sym-lib-table"
            fp_table = kicad_config / "fp-lib-table"
            
            if sym_table.exists():
                create_backup(sym_table, max_backups)
                click.echo(f"Created backup of symbol library table")
            
            if fp_table.exists():
                create_backup(fp_table, max_backups)
                click.echo(f"Created backup of footprint library table")
        
        if added_libraries:
            if dry_run:
                click.echo(f"Would add {len(added_libraries)} libraries to KiCad configuration")
            else:
                click.echo(f"Added {len(added_libraries)} libraries to KiCad configuration")
        else:
            click.echo("No new libraries to add")
        
        # Pin libraries if requested
        pinned_changes_needed = False
        if pin_libraries:
            # Extract library names from added_libraries
            symbol_libs = []
            footprint_libs = []
            
            # Also list existing libraries to pin them all
            try:
                existing_symbols, existing_footprints = list_libraries(kicad_lib_dir)
                symbol_libs = existing_symbols
                footprint_libs = existing_footprints
            except Exception as e:
                click.echo(f"Error listing libraries to pin: {e}", err=True)
            
            try:
                pinned_changes_needed = update_pinned_libraries(
                    kicad_config,
                    symbol_libs=symbol_libs,
                    footprint_libs=footprint_libs,
                    dry_run=dry_run
                )
                
                if pinned_changes_needed:
                    if dry_run:
                        click.echo(f"Would pin {len(symbol_libs)} symbol and {len(footprint_libs)} footprint libraries in KiCad")
                    else:
                        click.echo(f"Pinned {len(symbol_libs)} symbol and {len(footprint_libs)} footprint libraries in KiCad")
                else:
                    click.echo("All libraries already pinned in KiCad")
            except Exception as e:
                click.echo(f"Error pinning libraries: {e}", err=True)
            
        if not changes_needed and not env_changes_needed and not pinned_changes_needed:
            click.echo("No changes needed, configuration is up to date")
        elif dry_run:
            click.echo("Dry run: No changes were made")
    except Exception as e:
        click.echo(f"Error adding libraries: {e}", err=True)
        sys.exit(1)
    
    if not dry_run and (changes_needed or env_changes_needed or pinned_changes_needed):
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


@main.command()
def status():
    """Show the current KiCad configuration status"""
    import json
    
    try:
        kicad_config = find_kicad_config()
        click.echo(f"KiCad configuration directory: {kicad_config}")
        
        # Check environment variables in KiCad common
        kicad_common = kicad_config / "kicad_common.json"
        if kicad_common.exists():
            try:
                with open(kicad_common, "r") as f:
                    common_config = json.load(f)
                
                click.echo("\nEnvironment Variables in KiCad:")
                if "environment" in common_config and "vars" in common_config["environment"]:
                    env_vars = common_config["environment"]["vars"]
                    if env_vars:
                        for key, value in env_vars.items():
                            click.echo(f"  {key} = {value}")
                    else:
                        click.echo("  No environment variables set in KiCad")
                else:
                    click.echo("  No environment variables section in KiCad config")
                
                # Display pinned libraries
                if "session" in common_config:
                    session = common_config["session"]
                    
                    if "pinned_symbol_libs" in session and session["pinned_symbol_libs"]:
                        click.echo("\nPinned Symbol Libraries:")
                        for lib in session["pinned_symbol_libs"]:
                            click.echo(f"  - {lib}")
                    else:
                        click.echo("\nNo pinned symbol libraries")
                        
                    if "pinned_fp_libs" in session and session["pinned_fp_libs"]:
                        click.echo("\nPinned Footprint Libraries:")
                        for lib in session["pinned_fp_libs"]:
                            click.echo(f"  - {lib}")
                    else:
                        click.echo("\nNo pinned footprint libraries")
                
            except json.JSONDecodeError:
                click.echo("  Error: KiCad common config has invalid JSON format")
            except Exception as e:
                click.echo(f"  Error reading KiCad common config: {e}")
        else:
            click.echo("\nKiCad common config file not found")
        
        # List configured libraries
        try:
            symbol_libs, footprint_libs = list_configured_libraries(kicad_config)
            
            if symbol_libs:
                click.echo("\nConfigured Symbol Libraries:")
                for lib in symbol_libs:
                    click.echo(f"  - {lib['name']}")
                    if "uri" in lib:
                        click.echo(f"    URI: {lib['uri']}")
            else:
                click.echo("\nNo symbol libraries configured")
            
            if footprint_libs:
                click.echo("\nConfigured Footprint Libraries:")
                for lib in footprint_libs:
                    click.echo(f"  - {lib['name']}")
                    if "uri" in lib:
                        click.echo(f"    URI: {lib['uri']}")
            else:
                click.echo("\nNo footprint libraries configured")
                
        except Exception as e:
            click.echo(f"\nError listing configured libraries: {e}")
            
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)


@main.command()
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
    "--verbose", "-v",
    is_flag=True,
    help="Show verbose output for debugging",
)
def pin(kicad_lib_dir, symbols, footprints, all, dry_run, verbose):
    """Pin libraries in KiCad for quick access
    
    If no specific libraries are provided with --symbols or --footprints,
    all libraries from your library directory will be pinned by default.
    """
    import json
    
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            sys.exit(1)
    
    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    
    click.echo(f"Using KiCad library directory: {kicad_lib_dir}")
    
    # Find KiCad configuration
    try:
        kicad_config = find_kicad_config()
        click.echo(f"Found KiCad configuration at: {kicad_config}")
        
        # Show current pinned libraries if in verbose mode
        if verbose:
            kicad_common = kicad_config / "kicad_common.json"
            if kicad_common.exists():
                try:
                    with open(kicad_common, "r") as f:
                        config = json.load(f)
                    
                    click.echo("\nCurrently pinned libraries:")
                    if "session" in config and "pinned_symbol_libs" in config["session"]:
                        click.echo("  Symbol libraries:")
                        for lib in config["session"]["pinned_symbol_libs"]:
                            click.echo(f"    - {lib}")
                    else:
                        click.echo("  No symbol libraries pinned")
                        
                    if "session" in config and "pinned_fp_libs" in config["session"]:
                        click.echo("  Footprint libraries:")
                        for lib in config["session"]["pinned_fp_libs"]:
                            click.echo(f"    - {lib}")
                    else:
                        click.echo("  No footprint libraries pinned")
                except Exception as e:
                    click.echo(f"  Error reading current pinned libraries: {e}")
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)
    
    # Convert symbol and footprint options to lists
    symbol_libs = list(symbols) if symbols else []
    footprint_libs = list(footprints) if footprints else []
    
    if verbose:
        click.echo(f"\nSpecified libraries from command line:")
        click.echo(f"  Symbol libraries: {symbol_libs}")
        click.echo(f"  Footprint libraries: {footprint_libs}")
    
    # If --all is specified and no specific libraries are provided, find all libraries
    if all and not (symbol_libs or footprint_libs):
        try:
            avail_symbols, avail_footprints = list_libraries(kicad_lib_dir)
            
            if not avail_symbols and not avail_footprints:
                click.echo("No libraries found in the library directory. Nothing to pin.")
                sys.exit(0)
                
            click.echo("\nAvailable Symbol Libraries:")
            for symbol in sorted(avail_symbols):
                click.echo(f"  - {symbol}")
                
            click.echo("\nAvailable Footprint Libraries:")
            for footprint in sorted(avail_footprints):
                click.echo(f"  - {footprint}")
            
            # Actually assign the libraries for pinning
            symbol_libs = avail_symbols
            footprint_libs = avail_footprints
            
            if verbose:
                click.echo(f"\nFound libraries to pin:")
                click.echo(f"  Symbol libraries: {symbol_libs}")
                click.echo(f"  Footprint libraries: {footprint_libs}")
                
        except Exception as e:
            click.echo(f"Error listing libraries to pin: {e}", err=True)
            sys.exit(1)
    
    if not symbol_libs and not footprint_libs:
        click.echo("No libraries specified to pin. Use --symbols, --footprints, or --all to specify libraries.")
        sys.exit(1)
    
    if verbose:
        click.echo(f"\nAttempting to pin libraries:")
        if symbol_libs:
            click.echo("  Symbol libraries:")
            for lib in symbol_libs:
                click.echo(f"    - {lib}")
        if footprint_libs:
            click.echo("  Footprint libraries:")
            for lib in footprint_libs:
                click.echo(f"    - {lib}")
    
    # Debug output for verification
    click.echo(f"\nFinal libraries to pin:")
    click.echo(f"  Symbol libraries: {len(symbol_libs)} libraries")
    for lib in symbol_libs:
        click.echo(f"    - {lib}")
    click.echo(f"  Footprint libraries: {len(footprint_libs)} libraries")
    for lib in footprint_libs:
        click.echo(f"    - {lib}")
    
    # Pin the libraries
    try:
        # Update the config file
        kicad_common = kicad_config / "kicad_common.json"
        if kicad_common.exists():
            with open(kicad_common, "r") as f:
                config = json.load(f)
            
            # Ensure session section exists
            if "session" not in config:
                config["session"] = {
                    "pinned_symbol_libs": [],
                    "pinned_fp_libs": [],
                    "remember_open_files": False
                }
            
            # Ensure pinned sections exist
            if "pinned_symbol_libs" not in config["session"]:
                config["session"]["pinned_symbol_libs"] = []
            if "pinned_fp_libs" not in config["session"]:
                config["session"]["pinned_fp_libs"] = []
            
            # Get current pinned libraries
            current_symbols = config["session"]["pinned_symbol_libs"]
            current_footprints = config["session"]["pinned_fp_libs"]
            
            changes_made = False
            
            # Add symbols if not already pinned
            for lib in symbol_libs:
                if lib not in current_symbols:
                    if not dry_run:
                        current_symbols.append(lib)
                    changes_made = True
            
            # Add footprints if not already pinned
            for lib in footprint_libs:
                if lib not in current_footprints:
                    if not dry_run:
                        current_footprints.append(lib)
                    changes_made = True
            
            # Write changes
            if changes_made:
                if dry_run:
                    click.echo(f"\nWould pin {len(symbol_libs)} symbol and {len(footprint_libs)} footprint libraries in KiCad")
                else:
                    # Create backup before making changes
                    from .utils.backup import create_backup
                    try:
                        backup_path = create_backup(kicad_common)
                        click.echo(f"Created backup at {backup_path}")
                    except Exception as e:
                        click.echo(f"Warning: Failed to create backup: {e}", err=True)
                    
                    # Write the updated configuration
                    with open(kicad_common, "w") as f:
                        json.dump(config, f, indent=2)
                    click.echo(f"\nPinned {len(symbol_libs)} symbol and {len(footprint_libs)} footprint libraries in KiCad")
                    click.echo("Restart KiCad for changes to take effect.")
                    
                    # Show updated pinned libraries if in verbose mode
                    if verbose:
                        with open(kicad_common, "r") as f:
                            config = json.load(f)
                        
                        click.echo("\nUpdated pinned libraries:")
                        if "session" in config and "pinned_symbol_libs" in config["session"]:
                            click.echo("  Symbol libraries:")
                            for lib in config["session"]["pinned_symbol_libs"]:
                                click.echo(f"    - {lib}")
                        
                        if "session" in config and "pinned_fp_libs" in config["session"]:
                            click.echo("  Footprint libraries:")
                            for lib in config["session"]["pinned_fp_libs"]:
                                click.echo(f"    - {lib}")
            else:
                click.echo("\nAll specified libraries are already pinned in KiCad")
        else:
            click.echo(f"Error: KiCad common file not found at {kicad_common}")
    except Exception as e:
        click.echo(f"Error pinning libraries: {e}", err=True)
        sys.exit(1)


@main.command()
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
    "--verbose", "-v",
    is_flag=True,
    help="Show verbose output for debugging",
)
def unpin(symbols, footprints, all, dry_run, verbose):
    """Unpin libraries from KiCad favorites
    
    Removes libraries from KiCad's pinned library list.
    """
    import json
    
    # Find KiCad configuration
    try:
        kicad_config = find_kicad_config()
        click.echo(f"Found KiCad configuration at: {kicad_config}")
        
        # Show current pinned libraries if in verbose mode
        if verbose:
            kicad_common = kicad_config / "kicad_common.json"
            if kicad_common.exists():
                try:
                    with open(kicad_common, "r") as f:
                        config = json.load(f)
                    
                    click.echo("\nCurrently pinned libraries:")
                    if "session" in config and "pinned_symbol_libs" in config["session"]:
                        click.echo("  Symbol libraries:")
                        for lib in config["session"]["pinned_symbol_libs"]:
                            click.echo(f"    - {lib}")
                    else:
                        click.echo("  No symbol libraries pinned")
                        
                    if "session" in config and "pinned_fp_libs" in config["session"]:
                        click.echo("  Footprint libraries:")
                        for lib in config["session"]["pinned_fp_libs"]:
                            click.echo(f"    - {lib}")
                    else:
                        click.echo("  No footprint libraries pinned")
                except Exception as e:
                    click.echo(f"  Error reading current pinned libraries: {e}")
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)
    
    # Check if we have any libraries to unpin
    if not all and not symbols and not footprints:
        click.echo("No libraries specified to unpin. Use --symbols, --footprints, or --all.")
        sys.exit(1)
    
    # Read the current configuration
    kicad_common = kicad_config / "kicad_common.json"
    if not kicad_common.exists():
        click.echo(f"KiCad common configuration file not found at {kicad_common}")
        sys.exit(1)
    
    try:
        with open(kicad_common, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError:
        click.echo(f"Invalid JSON format in {kicad_common}")
        sys.exit(1)
    
    # Ensure session section exists
    if "session" not in config:
        click.echo("No session configuration found in KiCad common file. Nothing to unpin.")
        sys.exit(0)
    
    changes_made = False
    
    # Handle symbol libraries
    if "pinned_symbol_libs" in config["session"]:
        current_symbols = config["session"]["pinned_symbol_libs"]
        if all:
            if current_symbols:
                changes_made = True
                if not dry_run:
                    config["session"]["pinned_symbol_libs"] = []
                click.echo(f"Would unpin all {len(current_symbols)} symbol libraries" if dry_run else f"Unpinned all {len(current_symbols)} symbol libraries")
        elif symbols:
            original_count = len(current_symbols)
            if not dry_run:
                config["session"]["pinned_symbol_libs"] = [lib for lib in current_symbols if lib not in symbols]
            new_count = len(config["session"]["pinned_symbol_libs"]) if not dry_run else original_count - len(set(symbols) & set(current_symbols))
            if new_count != original_count:
                changes_made = True
                click.echo(f"Would unpin {original_count - new_count} symbol libraries" if dry_run else f"Unpinned {original_count - new_count} symbol libraries")
    
    # Handle footprint libraries
    if "pinned_fp_libs" in config["session"]:
        current_footprints = config["session"]["pinned_fp_libs"]
        if all:
            if current_footprints:
                changes_made = True
                if not dry_run:
                    config["session"]["pinned_fp_libs"] = []
                click.echo(f"Would unpin all {len(current_footprints)} footprint libraries" if dry_run else f"Unpinned all {len(current_footprints)} footprint libraries")
        elif footprints:
            original_count = len(current_footprints)
            if not dry_run:
                config["session"]["pinned_fp_libs"] = [lib for lib in current_footprints if lib not in footprints]
            new_count = len(config["session"]["pinned_fp_libs"]) if not dry_run else original_count - len(set(footprints) & set(current_footprints))
            if new_count != original_count:
                changes_made = True
                click.echo(f"Would unpin {original_count - new_count} footprint libraries" if dry_run else f"Unpinned {original_count - new_count} footprint libraries")
    
    # Write changes if needed
    if changes_made and not dry_run:
        # Create backup before making changes
        from .utils.backup import create_backup
        try:
            backup_path = create_backup(kicad_common)
            click.echo(f"Created backup at {backup_path}")
        except Exception as e:
            click.echo(f"Warning: Failed to create backup: {e}", err=True)
        
        # Write the updated configuration
        with open(kicad_common, "w") as f:
            json.dump(config, f, indent=2)
        click.echo("Restart KiCad for changes to take effect.")
        
        # Show updated pinned libraries if in verbose mode
        if verbose:
            with open(kicad_common, "r") as f:
                updated_config = json.load(f)
            
            click.echo("\nUpdated pinned libraries:")
            if "session" in updated_config and "pinned_symbol_libs" in updated_config["session"]:
                click.echo("  Symbol libraries:")
                for lib in updated_config["session"]["pinned_symbol_libs"]:
                    click.echo(f"    - {lib}")
            
            if "session" in updated_config and "pinned_fp_libs" in updated_config["session"]:
                click.echo("  Footprint libraries:")
                for lib in updated_config["session"]["pinned_fp_libs"]:
                    click.echo(f"    - {lib}")
    elif not changes_made:
        click.echo("No changes made. The specified libraries were not pinned.")
    elif dry_run:
        click.echo("Dry run: No changes were made.")


if __name__ == "__main__":
    main()