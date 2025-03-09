"""
Setup command implementation for KiCad Library Manager.
"""

import sys
import click

from ..library_manager import add_libraries, find_kicad_config
from ..utils.env_vars import find_environment_variables, expand_user_path, update_kicad_env_vars, update_pinned_libraries
from ..utils.backup import create_backup


@click.command()
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
                from ..library_manager import list_libraries
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