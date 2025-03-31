"""
Setup command implementation for KiCad Library Manager.
"""

import sys
import click
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re

from ..library_manager import add_libraries, find_kicad_config
from ..utils.env_vars import find_environment_variables, expand_user_path, update_kicad_env_vars, update_pinned_libraries
from ..utils.backup import create_backup
from ..config import Config
from ..utils.metadata import read_github_metadata, read_cloud_metadata


def fix_invalid_uris(kicad_config: Path, backup_first: bool = True, max_backups: int = 5, dry_run: bool = False) -> bool:
    """
    Fix invalid URIs in KiCad library tables, such as paths incorrectly wrapped in ${} syntax.
    
    Args:
        kicad_config: Path to the KiCad configuration directory
        backup_first: Whether to create backups before making changes
        max_backups: Maximum number of backups to keep
        dry_run: If True, don't make any changes
        
    Returns:
        True if changes were made, False otherwise
    """
    from ..utils.backup import create_backup
    
    # Get the library table paths
    sym_table = kicad_config / "sym-lib-table"
    fp_table = kicad_config / "fp-lib-table"
    
    changes_made = False
    
    for table_path in [sym_table, fp_table]:
        if table_path.exists():
            # Ensure UTF-8 encoding when reading
            with open(table_path, "r", encoding='utf-8') as f:
                content = f.read()
            
            # Look for URIs with invalid environment variable syntax like ${/path/to/lib}
            pattern = r'\(uri "\${(\/[^}]+)}\/(.*?)"\)'
            if re.search(pattern, content):
                changes_made = True
                
                if not dry_run:
                    if backup_first:
                        create_backup(table_path, max_backups)
                    
                    # Replace invalid URIs
                    fixed_content = re.sub(pattern, r'(uri "\\1/\\2")', content)
                    
                    # Ensure UTF-8 encoding when writing
                    with open(table_path, "w", encoding='utf-8') as f:
                        f.write(fixed_content)
    
    return changes_made

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
    "--threed-lib-dirs",
    help="Names of 3D model libraries to use (comma-separated, uses all if not specified)",
)
@click.option(
    "--symbol-lib-dirs",
    help="Names of symbol libraries to use (comma-separated, uses current if not specified)",
)
@click.option(
    "--all-libraries",
    is_flag=True,
    default=False,
    help="Set up all configured libraries (both symbols and 3D models)",
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
def setup(kicad_lib_dir, kicad_3d_dir, threed_lib_dirs, symbol_lib_dirs, all_libraries, 
          max_backups, dry_run, pin_libraries, verbose):
    """Configure KiCad to use libraries in the specified directory
    
    This command sets up KiCad to use your configured libraries. It will:
    
    1. Set environment variables in KiCad's configuration
    2. Add libraries to KiCad's library tables
    3. Optionally pin libraries for quick access
    
    You can set up specific libraries by name, or use all configured libraries.
    Each 3D model library can have its own environment variable, allowing multiple
    3D model libraries to be used simultaneously.
    """
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
    
    # Split library names if provided
    threed_lib_names = None
    if threed_lib_dirs:
        threed_lib_names = [name.strip() for name in threed_lib_dirs.split(",")]
        if verbose:
            click.echo(f"Requested 3D model libraries: {threed_lib_names}")
    
    symbol_lib_names = None
    if symbol_lib_dirs:
        symbol_lib_names = [name.strip() for name in symbol_lib_dirs.split(",")]
        if verbose:
            click.echo(f"Requested symbol libraries: {symbol_lib_names}")
    
    # Check Config file for library paths
    config_lib_paths: Dict[str, str] = {}
    config_3d_libs: List[Dict[str, str]] = []
    config_symbol_libs: List[Dict[str, str]] = []
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
        
        # Get all configured libraries
        all_symbol_libs = config_obj.get_libraries("github")
        all_3d_libs = config_obj.get_libraries("cloud")
        
        if verbose:
            click.echo(f"Found {len(all_symbol_libs)} symbol libraries and {len(all_3d_libs)} 3D model libraries in config")
        
        # Get library paths based on selection criteria
        if all_libraries:
            # Use all libraries
            config_symbol_libs = all_symbol_libs
            config_3d_libs = all_3d_libs
        else:
            # Get libraries by name if specified
            if symbol_lib_names:
                for name in symbol_lib_names:
                    for lib in all_symbol_libs:
                        if lib.get("name") == name:
                            config_symbol_libs.append(lib)
                            break
            else:
                # Get GitHub library path (current library)
                github_lib = config_obj.get_symbol_library_path()
                if github_lib and not kicad_lib_dir:
                    for lib in all_symbol_libs:
                        if lib.get("path") == github_lib:
                            config_symbol_libs.append(lib)
                            break
            
            # Get 3D model libraries by name if specified
            if threed_lib_names:
                for name in threed_lib_names:
                    for lib in all_3d_libs:
                        if lib.get("name") == name:
                            config_3d_libs.append(lib)
                            break
            else:
                # If --all-libraries is not specified and no 3D libraries are specified,
                # we'll only set up the current 3D library (if any)
                cloud_lib = config_obj.get_3d_library_path()
                if cloud_lib and not kicad_3d_dir:
                    for lib in all_3d_libs:
                        if lib.get("path") == cloud_lib:
                            config_3d_libs.append(lib)
                            break
        
        # Print what we're setting up
        if config_symbol_libs:
            click.echo("\nSetting up symbol libraries:")
            for lib in config_symbol_libs:
                lib_name = lib.get("name", "unnamed")
                lib_path = lib.get("path", "unknown")
                click.echo(f"  - {lib_name}: {lib_path}")
                
                # Read metadata to get environment variable name
                try:
                    metadata = read_github_metadata(Path(lib_path))
                    if metadata and "env_var" in metadata:
                        env_var = metadata["env_var"]
                        if env_var:
                            # Store all GitHub libraries with their env vars
                            config_lib_paths[env_var] = lib_path
                            click.echo(f"    Using environment variable: {env_var}")
                        else:
                            click.echo(f"    No environment variable configured")
                    else:
                        click.echo(f"    No metadata or environment variable found")
                except Exception as e:
                    if verbose:
                        click.echo(f"    Error reading metadata: {e}")
                
                # If we're using the first symbol library as the main library
                if not kicad_lib_dir and lib == config_symbol_libs[0]:
                    kicad_lib_dir = lib_path
                    # For backward compatibility, also use KICAD_USER_LIB as fallback
                    if "KICAD_USER_LIB" not in config_lib_paths:
                        config_lib_paths["KICAD_USER_LIB"] = lib_path
        
        if config_3d_libs:
            click.echo("\nSetting up 3D model libraries:")
            for lib in config_3d_libs:
                lib_name = lib.get("name", "unnamed")
                lib_path = lib.get("path", "unknown")
                click.echo(f"  - {lib_name}: {lib_path}")
                
                # Read metadata to get environment variable name
                try:
                    metadata = read_cloud_metadata(Path(lib_path))
                    if metadata and "env_var" in metadata:
                        env_var = metadata["env_var"]
                        if env_var:
                            # Store all 3D libraries with their env vars
                            config_lib_paths[env_var] = lib_path
                            click.echo(f"    Using environment variable: {env_var}")
                        else:
                            click.echo(f"    No environment variable configured")
                    else:
                        click.echo(f"    No metadata or environment variable found")
                except Exception as e:
                    if verbose:
                        click.echo(f"    Error reading metadata: {e}")
                
                # Use the first 3D library as the default if not specified
                if not kicad_3d_dir and lib == config_3d_libs[0]:
                    kicad_3d_dir = lib_path
    
    except Exception as e:
        # If there's any issue with config, continue with environment variables
        if verbose:
            click.echo(f"Error reading from config: {e}")
            import traceback
            click.echo(traceback.format_exc())
    
    # Fall back to environment variables if still not found
    env_lib_paths = {}
    if not kicad_lib_dir:
        env_var = find_environment_variables("KICAD_USER_LIB")
        if env_var:
            kicad_lib_dir = env_var
            env_lib_paths["KICAD_USER_LIB"] = env_var
            click.echo(f"Using KiCad library from environment variable: {kicad_lib_dir}")
        else:
            click.echo("Error: KICAD_USER_LIB not set and not provided", err=True)
            click.echo("Consider initializing a library with 'kilm init' first.", err=True)
            sys.exit(1)
            
    if not kicad_3d_dir:
        env_var = find_environment_variables("KICAD_3D_LIB")
        if env_var:
            kicad_3d_dir = env_var
            env_lib_paths["KICAD_3D_LIB"] = env_var
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
    
    click.echo(f"\nUsing KiCad symbol library directory: {kicad_lib_dir}")
    if kicad_3d_dir:
        click.echo(f"Using KiCad main 3D models directory: {kicad_3d_dir}")
    
    # Find KiCad configuration
    try:
        kicad_config = find_kicad_config()
        click.echo(f"Found KiCad configuration at: {kicad_config}")
        
        # Fix any invalid URIs in existing library entries
        uri_changes = fix_invalid_uris(kicad_config, True, max_backups, dry_run)
        if uri_changes:
            if dry_run:
                click.echo("Would fix invalid library URIs in KiCad configuration")
            else:
                click.echo("Fixed invalid library URIs in KiCad configuration")
    except Exception as e:
        click.echo(f"Error finding KiCad configuration: {e}", err=True)
        sys.exit(1)
    
    # Prepare environment variables dictionary
    env_vars = {}
    
    # Always include KICAD_USER_LIB for backward compatibility
    if kicad_lib_dir:
        env_vars["KICAD_USER_LIB"] = kicad_lib_dir
    
    # Add main 3D library if specified
    if kicad_3d_dir:
        env_vars["KICAD_3D_LIB"] = kicad_3d_dir
    
    # Add all custom environment variables from both GitHub and cloud libraries
    for var_name, path in config_lib_paths.items():
        env_vars[var_name] = path
    
    # Initialize variables
    env_changes_needed = False
    
    # Update environment variables in KiCad configuration
    try:
        env_changes_needed = update_kicad_env_vars(kicad_config, env_vars, dry_run, max_backups)
        if env_changes_needed:
            if dry_run:
                click.echo(f"Would update environment variables in KiCad configuration")
            else:
                click.echo(f"Updated environment variables in KiCad configuration")
                click.echo(f"Created backup of kicad_common.json")
                
                # Show all environment variables that were set
                click.echo("\nEnvironment variables set in KiCad:")
                for var_name, value in env_vars.items():
                    click.echo(f"  {var_name} = {value}")
        else:
            click.echo(f"Environment variables already up to date in KiCad configuration")
    except Exception as e:
        click.echo(f"Error updating environment variables: {e}", err=True)
        # Continue with the rest of the setup, but don't set env_changes_needed to True
    
    # Add libraries
    try:
        # Prepare all 3D library paths
        three_d_dirs = {}
        for var_name, path in config_lib_paths.items():
            if var_name.startswith("KICAD_3D_"):
                three_d_dirs[var_name] = path
        
        # Add the main 3D library if it's not already in the list
        if kicad_3d_dir and "KICAD_3D_LIB" not in three_d_dirs:
            three_d_dirs["KICAD_3D_LIB"] = kicad_3d_dir
        
        # Call add_libraries with the main library and all 3D libraries
        added_libraries, changes_needed = add_libraries(
            kicad_lib_dir, 
            kicad_config, 
            kicad_3d_dir=kicad_3d_dir,
            additional_3d_dirs=three_d_dirs,
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