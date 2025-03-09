"""
Setup command implementation for KiCad Library Manager.
"""

import sys
import click

from ..library_manager import add_libraries, find_kicad_config
from ..utils.env_vars import find_environment_variables, expand_user_path, update_kicad_env_vars, update_pinned_libraries
from ..utils.backup import create_backup
from ..config import Config


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
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show more information for debugging",
)
def setup(kicad_lib_dir, kicad_3d_dir, max_backups, dry_run, pin_libraries, verbose):
    """Configure KiCad to use libraries in the specified directory"""
    # Show source of library paths
    cmd_line_lib_paths = {}
    if kicad_lib_dir:
        cmd_line_lib_paths["symbols"] = kicad_lib_dir
        if verbose:
            click.echo(f"Symbol library specified on command line: {kicad_lib_dir}")
    
    if kicad_3d_dir:
        cmd_line_lib_paths["3d"] = kicad_3d_dir
        if verbose:
            click.echo(f"3D model library specified on command line: {kicad_3d_dir}")
    
    # Check Config file for library paths
    config_lib_paths = {}
    config_obj = None
    try:
        config_obj = Config()
        
        # Display configuration file location if verbose
        if verbose:
            config_file = config_obj._get_config_file()
            click.echo(f"Looking for configuration in: {config_file}")
            if config_file.exists():
                click.echo(f"Configuration file exists")
            else:
                click.echo(f"Configuration file does not exist")
        
        # Get GitHub library path
        if not kicad_lib_dir:
            github_lib = config_obj.get_symbol_library_path()
            if github_lib:
                kicad_lib_dir = github_lib
                config_lib_paths["symbols"] = github_lib
                click.echo(f"Using GitHub library from config: {kicad_lib_dir}")
                
                # Show all GitHub libraries if verbose
                if verbose:
                    click.echo("All GitHub libraries in config:")
                    for lib in config_obj.get_libraries("github"):
                        name = lib.get("name", "unnamed")
                        path = lib.get("path", "unknown")
                        current = "(current)" if path == config_obj.get_current_library() else ""
                        click.echo(f"  - {name}: {path} {current}")

        # Get cloud 3D library path
        if not kicad_3d_dir:
            cloud_lib = config_obj.get_3d_library_path()
            if cloud_lib:
                kicad_3d_dir = cloud_lib
                config_lib_paths["3d"] = cloud_lib
                click.echo(f"Using cloud 3D library from config: {kicad_3d_dir}")
                
                # Show all cloud libraries if verbose
                if verbose:
                    click.echo("All cloud libraries in config:")
                    for lib in config_obj.get_libraries("cloud"):
                        name = lib.get("name", "unnamed")
                        path = lib.get("path", "unknown")
                        current = "(current)" if path == config_obj.get_current_library() else ""
                        click.echo(f"  - {name}: {path} {current}")
    except Exception as e:
        # If there's any issue with config, continue with environment variables
        if not kicad_lib_dir or not kicad_3d_dir:
            click.echo(f"Note: Could not read config file: {e}")
            if verbose:
                import traceback
                click.echo(traceback.format_exc())
    
    # Fall back to environment variables if still not found
    env_lib_paths = {}
    if not kicad_lib_dir:
        env_var = find_environment_variables("KICAD_USER_LIB")
        if env_var:
            kicad_lib_dir = env_var
            env_lib_paths["symbols"] = env_var
            click.echo(f"Using KiCad library from environment variable: {kicad_lib_dir}")
        else:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            click.echo("Consider initializing a library with 'kilm init' first.", err=True)
            sys.exit(1)
            
    if not kicad_3d_dir:
        env_var = find_environment_variables("KICAD_3D_LIB")
        if env_var:
            kicad_3d_dir = env_var
            env_lib_paths["3d"] = env_var
            click.echo(f"Using 3D model library from environment variable: {kicad_3d_dir}")
        else:
            click.echo("Warning: KICAD_3D_LIB not set, 3D models might not work correctly", err=True)
            click.echo("Consider adding a 3D model directory with 'kilm add-3d'", err=True)
    
    # Show summary of where libraries are coming from
    if verbose:
        click.echo("\nSummary of library sources:")
        if cmd_line_lib_paths:
            click.echo("  From command line:")
            for lib_type, path in cmd_line_lib_paths.items():
                click.echo(f"    - {lib_type}: {path}")
        
        if config_lib_paths:
            click.echo("  From config file:")
            for lib_type, path in config_lib_paths.items():
                click.echo(f"    - {lib_type}: {path}")
                
        if env_lib_paths:
            click.echo("  From environment variables:")
            for lib_type, path in env_lib_paths.items():
                click.echo(f"    - {lib_type}: {path}")
    
    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    if kicad_3d_dir:
        kicad_3d_dir = expand_user_path(kicad_3d_dir)
    
    click.echo(f"\nUsing KiCad library directory: {kicad_lib_dir}")
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
                
                if verbose:
                    click.echo(f"Found {len(symbol_libs)} symbol libraries and {len(footprint_libs)} footprint libraries to pin")
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
        if verbose:
            import traceback
            click.echo(traceback.format_exc())
        sys.exit(1)
    
    if not dry_run and (changes_needed or env_changes_needed or pinned_changes_needed):
        click.echo("Setup complete! Restart KiCad for changes to take effect.") 