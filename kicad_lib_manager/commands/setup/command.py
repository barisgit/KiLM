"""
Setup command implementation for KiCad Library Manager (Typer version).
"""

import re
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...services.config_service import Config, LibraryDict
from ...services.library_service import LibraryService
from ...utils.backup import create_backup
from ...utils.env_vars import (
    expand_user_path,
    find_environment_variables,
    update_kicad_env_vars,
    update_pinned_libraries,
)
from ...utils.file_ops import list_libraries
from ...utils.metadata import read_cloud_metadata, read_github_metadata

console = Console()


def fix_invalid_uris(
    kicad_config: Path,
    backup_first: bool = True,
    max_backups: int = 5,
    dry_run: bool = False,
) -> bool:
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
    from ...utils.backup import create_backup

    # Get the library table paths
    sym_table = kicad_config / "sym-lib-table"
    fp_table = kicad_config / "fp-lib-table"

    changes_made = False

    for table_path in [sym_table, fp_table]:
        if table_path.exists():
            # Ensure UTF-8 encoding when reading
            with table_path.open(encoding="utf-8") as f:
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
                    with table_path.open("w", encoding="utf-8") as f:
                        f.write(fixed_content)

    return changes_made


def setup(
    kicad_lib_dir: Optional[str] = typer.Option(
        None,
        "--kicad-lib-dir",
        envvar="KICAD_USER_LIB",
        help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
    ),
    kicad_3d_dir: Optional[str] = typer.Option(
        None,
        "--kicad-3d-dir",
        envvar="KICAD_3D_LIB",
        help="KiCad 3D models directory (uses KICAD_3D_LIB env var if not specified)",
    ),
    threed_lib_dirs: Optional[str] = typer.Option(
        None,
        "--threed-lib-dirs",
        help="Names of 3D model libraries to use (comma-separated, uses all if not specified)",
    ),
    symbol_lib_dirs: Optional[str] = typer.Option(
        None,
        "--symbol-lib-dirs",
        help="Names of symbol libraries to use (comma-separated, uses current if not specified)",
    ),
    all_libraries: bool = typer.Option(
        False,
        "--all-libraries",
        help="Set up all configured libraries (both symbols and 3D models)",
    ),
    max_backups: int = typer.Option(
        5, "--max-backups", help="Maximum number of backups to keep"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without making changes"
    ),
    pin_libraries: bool = typer.Option(
        True,
        "--pin-libraries/--no-pin-libraries",
        help="Add libraries to KiCad pinned libraries for quick access",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show more information for debugging"
    ),
) -> None:
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
            console.print(
                f"Symbol library specified on command line: [blue]{kicad_lib_dir}[/blue]"
            )

    if kicad_3d_dir:
        cmd_line_lib_paths["3d"] = kicad_3d_dir
        if verbose:
            console.print(
                f"3D model library specified on command line: [blue]{kicad_3d_dir}[/blue]"
            )

    # Split library names if provided
    threed_lib_names = None
    if threed_lib_dirs:
        threed_lib_names = [name.strip() for name in threed_lib_dirs.split(",")]
        if verbose:
            console.print(f"Requested 3D model libraries: {threed_lib_names}")

    symbol_lib_names = None
    if symbol_lib_dirs:
        symbol_lib_names = [name.strip() for name in symbol_lib_dirs.split(",")]
        if verbose:
            console.print(f"Requested symbol libraries: {symbol_lib_names}")

    # Check Config file for library paths
    config_lib_paths: dict[str, str] = {}
    config_3d_libs: list[LibraryDict] = []
    config_symbol_libs: list[LibraryDict] = []
    config_obj = None

    try:
        config_obj = Config()

        # Display configuration file location if verbose
        if verbose:
            config_file = config_obj._get_config_file()
            console.print(f"Looking for configuration in: {config_file}")
            if config_file.exists():
                console.print("Configuration file exists")
            else:
                console.print("Configuration file does not exist")

        # Get all configured libraries
        all_symbol_libs = config_obj.get_libraries("github")
        all_3d_libs = config_obj.get_libraries("cloud")

        if verbose:
            console.print(
                f"Found {len(all_symbol_libs)} symbol libraries and {len(all_3d_libs)} 3D model libraries in config"
            )

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
            console.print()
            table = Table(
                title="[bold cyan]Setting up symbol libraries[/bold cyan]",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Library", style="cyan", no_wrap=True)
            table.add_column("Path", style="blue")
            table.add_column("Environment Variable", style="green")

            for lib in config_symbol_libs:
                lib_name = lib.get("name", "unnamed")
                lib_path = lib.get("path", "unknown")
                env_var_display = "None"

                # Read metadata to get environment variable name
                try:
                    metadata = read_github_metadata(Path(lib_path))
                    if metadata and "env_var" in metadata:
                        env_var = metadata["env_var"]
                        if env_var and isinstance(env_var, str):
                            # Store all GitHub libraries with their env vars
                            config_lib_paths[env_var] = lib_path
                            env_var_display = f"[green]{env_var}[/green]"
                        else:
                            env_var_display = "[yellow]Not configured[/yellow]"
                    else:
                        env_var_display = "[yellow]No metadata[/yellow]"
                except Exception as e:
                    env_var_display = (
                        f"[red]Error: {e}[/red]" if verbose else "[red]Error[/red]"
                    )

                # If we're using the first symbol library as the main library
                if not kicad_lib_dir and lib == config_symbol_libs[0]:
                    kicad_lib_dir = lib_path
                    # For backward compatibility, also use KICAD_USER_LIB as fallback
                    if "KICAD_USER_LIB" not in config_lib_paths:
                        config_lib_paths["KICAD_USER_LIB"] = lib_path

                table.add_row(f"[bold]{lib_name}[/bold]", lib_path, env_var_display)

            console.print(table)

        if config_3d_libs:
            console.print()
            table = Table(
                title="[bold cyan]Setting up 3D model libraries[/bold cyan]",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Library", style="cyan", no_wrap=True)
            table.add_column("Path", style="blue")
            table.add_column("Environment Variable", style="green")

            for lib in config_3d_libs:
                lib_name = lib.get("name", "unnamed")
                lib_path = lib.get("path", "unknown")
                env_var_display = "None"

                # Read metadata to get environment variable name
                try:
                    metadata = read_cloud_metadata(Path(lib_path))
                    if metadata and "env_var" in metadata:
                        env_var = metadata["env_var"]
                        if env_var and isinstance(env_var, str):
                            # Store all 3D libraries with their env vars
                            config_lib_paths[env_var] = lib_path
                            env_var_display = f"[green]{env_var}[/green]"
                        else:
                            env_var_display = "[yellow]Not configured[/yellow]"
                    else:
                        env_var_display = "[yellow]No metadata[/yellow]"
                except Exception as e:
                    env_var_display = (
                        f"[red]Error: {e}[/red]" if verbose else "[red]Error[/red]"
                    )

                # Use the first 3D library as the default if not specified
                if not kicad_3d_dir and lib == config_3d_libs[0]:
                    kicad_3d_dir = lib_path

                table.add_row(f"[bold]{lib_name}[/bold]", lib_path, env_var_display)

            console.print(table)

    except Exception as e:
        # If there's any issue with config, continue with environment variables
        if verbose:
            console.print(f"Error reading from config: {e}")
            import traceback

            console.print(traceback.format_exc())

    # Fall back to environment variables if still not found
    env_lib_paths = {}
    if not kicad_lib_dir:
        env_var = find_environment_variables("KICAD_USER_LIB")
        if env_var:
            kicad_lib_dir = env_var
            env_lib_paths["KICAD_USER_LIB"] = env_var
            console.print(
                f"[green]Using KiCad library from environment variable:[/green] [blue]{kicad_lib_dir}[/blue]"
            )
        else:
            console.print("[red]Error: KICAD_USER_LIB not set and not provided[/red]")
            console.print(
                "[yellow]Consider initializing a library with 'kilm init' first.[/yellow]"
            )
            raise typer.Exit(1)

    if not kicad_3d_dir:
        env_var = find_environment_variables("KICAD_3D_LIB")
        if env_var:
            kicad_3d_dir = env_var
            env_lib_paths["KICAD_3D_LIB"] = env_var
            console.print(
                f"[green]Using 3D model library from environment variable:[/green] [blue]{kicad_3d_dir}[/blue]"
            )
        else:
            console.print(
                "[yellow]Warning: KICAD_3D_LIB not set, 3D models might not work correctly[/yellow]"
            )
            console.print(
                "[yellow]Consider adding a 3D model directory with 'kilm add-3d'[/yellow]"
            )

    # Show summary of where libraries are coming from
    if verbose:
        console.print("\nSummary of library sources:")
        if cmd_line_lib_paths:
            console.print("  From command line:")
            for lib_type, path in cmd_line_lib_paths.items():
                console.print(f"    - {lib_type}: {path}")

        if config_lib_paths:
            console.print("  From config file:")
            for lib_type, path in config_lib_paths.items():
                console.print(f"    - {lib_type}: {path}")

        if env_lib_paths:
            console.print("  From environment variables:")
            for lib_type, path in env_lib_paths.items():
                console.print(f"    - {lib_type}: {path}")

    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)
    if kicad_3d_dir:
        kicad_3d_dir = expand_user_path(kicad_3d_dir)

    # Create configuration summary panel
    config_content = (
        f"[green]Symbol library directory:[/green] [blue]{kicad_lib_dir}[/blue]\n"
    )
    if kicad_3d_dir:
        config_content += (
            f"[green]3D models directory:[/green]\n[blue]{kicad_3d_dir}[/blue]"
        )
    else:
        config_content += "[yellow]3D models directory: Not configured[/yellow]"

    console.print()
    console.print(
        Panel(
            config_content,
            title="[bold cyan]Configuration Summary[/bold cyan]",
            border_style="cyan",
        )
    )

    # Find KiCad configuration
    try:
        kicad_config = LibraryService.find_kicad_config()
        console.print(
            f"[green]Found KiCad configuration at:[/green] [blue]{kicad_config}[/blue]"
        )

        # Fix any invalid URIs in existing library entries
        uri_changes = fix_invalid_uris(kicad_config, True, max_backups, dry_run)
        if uri_changes:
            if dry_run:
                console.print(
                    "[yellow]Would fix invalid library URIs in KiCad configuration[/yellow]"
                )
            else:
                console.print(
                    "[green]Fixed invalid library URIs in KiCad configuration[/green]"
                )
    except Exception as e:
        console.print(f"[red]Error finding KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e

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
        env_changes_needed = update_kicad_env_vars(
            kicad_config, env_vars, dry_run, max_backups
        )
        if env_changes_needed:
            if dry_run:
                console.print(
                    "[yellow]Would update environment variables in KiCad configuration[/yellow]"
                )
            else:
                console.print(
                    "[green]Updated environment variables in KiCad configuration[/green]"
                )
                console.print("[blue]Created backup of kicad_common.json[/blue]")

                # Show all environment variables that were set
                console.print(
                    "\n[bold cyan]Environment variables set in KiCad:[/bold cyan]"
                )
                for var_name, value in env_vars.items():
                    console.print(f"  [cyan]{var_name}[/cyan] = [blue]{value}[/blue]")
        else:
            console.print(
                "[blue]Environment variables already up to date in KiCad configuration[/blue]"
            )
    except Exception as e:
        console.print(f"[red]Error updating environment variables: {e}[/red]")
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
        added_libraries, changes_needed = LibraryService.add_libraries(
            kicad_lib_dir,
            kicad_config,
            kicad_3d_dir=kicad_3d_dir,
            additional_3d_dirs=three_d_dirs,
            dry_run=dry_run,
        )

        # Create backups only if changes are needed
        if changes_needed and not dry_run:
            sym_table = kicad_config / "sym-lib-table"
            fp_table = kicad_config / "fp-lib-table"

            if sym_table.exists():
                create_backup(sym_table, max_backups)
                console.print("[blue]Created backup of symbol library table[/blue]")

            if fp_table.exists():
                create_backup(fp_table, max_backups)
                console.print("[blue]Created backup of footprint library table[/blue]")

        if added_libraries:
            if dry_run:
                console.print(
                    f"[yellow]Would add {len(added_libraries)} libraries to KiCad configuration[/yellow]"
                )
            else:
                console.print(
                    f"[green]Added {len(added_libraries)} libraries to KiCad configuration[/green]"
                )
        else:
            console.print("[blue]No new libraries to add[/blue]")

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

                if verbose:
                    console.print(
                        f"Found {len(symbol_libs)} symbol libraries and {len(footprint_libs)} footprint libraries to pin"
                    )
            except Exception as e:
                console.print(f"[red]Error listing libraries to pin: {e}[/red]")

            try:
                pinned_changes_needed = update_pinned_libraries(
                    kicad_config,
                    symbol_libs=symbol_libs,
                    footprint_libs=footprint_libs,
                    dry_run=dry_run,
                )

                if pinned_changes_needed:
                    if dry_run:
                        console.print(
                            f"[yellow]Would pin {len(symbol_libs)} symbol and {len(footprint_libs)} footprint libraries in KiCad[/yellow]"
                        )
                    else:
                        console.print(
                            f"[green]Pinned {len(symbol_libs)} symbol and {len(footprint_libs)} footprint libraries in KiCad[/green]"
                        )
                else:
                    console.print("[blue]All libraries already pinned in KiCad[/blue]")
            except Exception as e:
                console.print(f"[red]Error pinning libraries: {e}[/red]")

        if not changes_needed and not env_changes_needed and not pinned_changes_needed:
            console.print("[blue]No changes needed, configuration is up to date[/blue]")
        elif dry_run:
            console.print("[yellow]Dry run: No changes were made[/yellow]")
    except Exception as e:
        console.print(f"[red]Error adding libraries: {e}[/red]")
        if verbose:
            import traceback

            console.print(traceback.format_exc())
        raise typer.Exit(1) from None

    if not dry_run and (changes_needed or env_changes_needed or pinned_changes_needed):
        console.print()
        console.print(
            Panel(
                "[bold green]Setup complete! Restart KiCad for changes to take effect.[/bold green]",
                title="[bold green]✅ Success[/bold green]",
                border_style="green",
            )
        )
