"""The ``setup`` command: configure KiCad to use the KiLM libraries."""

import traceback
from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from kicad_lib_manager.commands.setup import changes
from kicad_lib_manager.commands.setup.changes import ChangeOptions, SetupLibraries
from kicad_lib_manager.commands.setup.sources import (
    LibrarySelection,
    LibrarySources,
    add_config_libraries,
    command_line_sources,
    fall_back_to_environment,
    print_source_summary,
    requested_names,
)
from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.env_vars import expand_user_path


def setup(  # noqa: PLR0913 -- each CLI option is a Typer parameter
    *,
    kicad_lib_dir: Annotated[
        str | None,
        typer.Option(
            "--kicad-lib-dir",
            envvar="KICAD_USER_LIB",
            help="KiCad library directory (uses KICAD_USER_LIB env var if not "
            "specified)",
        ),
    ] = None,
    kicad_3d_dir: Annotated[
        str | None,
        typer.Option(
            "--kicad-3d-dir",
            envvar="KICAD_3D_LIB",
            help="KiCad 3D models directory (uses KICAD_3D_LIB env var if not "
            "specified)",
        ),
    ] = None,
    threed_lib_dirs: Annotated[
        str | None,
        typer.Option(
            "--threed-lib-dirs",
            help="Names of 3D model libraries to use (comma-separated, uses all "
            "if not specified)",
        ),
    ] = None,
    symbol_lib_dirs: Annotated[
        str | None,
        typer.Option(
            "--symbol-lib-dirs",
            help="Names of symbol libraries to use (comma-separated, uses current "
            "if not specified)",
        ),
    ] = None,
    all_libraries: Annotated[
        bool,
        typer.Option(
            "--all-libraries",
            help="Set up all configured libraries (both symbols and 3D models)",
        ),
    ] = False,
    max_backups: Annotated[
        int, typer.Option("--max-backups", help="Maximum number of backups to keep")
    ] = 5,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be done without making changes"
        ),
    ] = False,
    pin_libraries: Annotated[
        bool,
        typer.Option(
            "--pin-libraries/--no-pin-libraries",
            help="Add libraries to KiCad pinned libraries for quick access",
        ),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show more information for debugging"),
    ] = False,
) -> None:
    """Configure KiCad to use libraries in the specified directory.

    This command sets up KiCad to use your configured libraries. It will:

    1. Set environment variables in KiCad's configuration
    2. Add libraries to KiCad's library tables
    3. Optionally pin libraries for quick access

    You can set up specific libraries by name, or use all configured libraries.
    Each 3D model library can have its own environment variable, allowing multiple
    3D model libraries to be used simultaneously.
    """
    sources = command_line_sources(kicad_lib_dir, kicad_3d_dir, verbose=verbose)
    selection = LibrarySelection(
        all_libraries=all_libraries,
        model_names=requested_names(
            threed_lib_dirs, "3D model libraries", verbose=verbose
        ),
        symbol_names=requested_names(
            symbol_lib_dirs, "symbol libraries", verbose=verbose
        ),
    )
    _read_config(sources, selection, verbose=verbose)
    symbol_dir = fall_back_to_environment(sources)
    if verbose:
        print_source_summary(sources)

    libraries = SetupLibraries(
        symbol_dir=expand_user_path(symbol_dir),
        models_dir=None
        if sources.models_dir is None
        else expand_user_path(sources.models_dir),
        library_vars=sources.from_config,
    )
    _print_configuration(libraries)
    options = ChangeOptions(
        kicad_config=_find_kicad_config(dry_run=dry_run, max_backups=max_backups),
        dry_run=dry_run,
        max_backups=max_backups,
        verbose=verbose,
    )
    if _apply_changes(options, libraries, pin=pin_libraries) and not dry_run:
        get_console().print()
        get_console().print(
            Panel(
                "[bold green]Setup complete! Restart KiCad for changes to take "
                "effect.[/bold green]",
                title="[bold green]Success[/bold green]",
                border_style="green",
            )
        )


def _read_config(
    sources: LibrarySources, selection: LibrarySelection, *, verbose: bool
) -> None:
    """Add the configured libraries, carrying on without them on failure."""
    try:
        add_config_libraries(sources, selection, verbose=verbose)
    except (OSError, ValueError) as e:
        # Environment variables can still provide the libraries.
        if verbose:
            console = get_console()
            console.print(f"Error reading from config: {e}")
            console.print(traceback.format_exc())


def _print_configuration(libraries: SetupLibraries) -> None:
    """Print the main library directories setup configures."""
    content = (
        "[green]Symbol library directory:[/green] "
        f"[blue]{libraries.symbol_dir}[/blue]\n"
    )
    if libraries.models_dir is None:
        content += "[yellow]3D models directory: Not configured[/yellow]"
    else:
        content += (
            f"[green]3D models directory:[/green]\n[blue]{libraries.models_dir}[/blue]"
        )
    console = get_console()
    console.print()
    console.print(
        Panel(
            content,
            title="[bold cyan]Configuration Summary[/bold cyan]",
            border_style="cyan",
        )
    )


def _find_kicad_config(*, dry_run: bool, max_backups: int) -> Path:
    """Find KiCad's configuration and unwrap invalid library paths in it.

    Raises:
        typer.Exit: KiCad's configuration is missing or cannot be fixed.
    """
    console = get_console()
    try:
        kicad_config = LibraryService.find_kicad_config()
        console.print(
            f"[green]Found KiCad configuration at:[/green] [blue]{kicad_config}[/blue]"
        )
        fixed = changes.fix_invalid_uris(
            kicad_config, max_backups=max_backups, dry_run=dry_run
        )
    except Exception as e:
        console.print(f"[red]Error finding KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e

    if fixed and dry_run:
        console.print(
            "[yellow]Would fix invalid library URIs in KiCad configuration[/yellow]"
        )
    elif fixed:
        console.print(
            "[green]Fixed invalid library URIs in KiCad configuration[/green]"
        )
    return kicad_config


def _apply_changes(
    options: ChangeOptions, libraries: SetupLibraries, *, pin: bool
) -> bool:
    """Make setup's changes in KiCad and return whether anything changed.

    Raises:
        typer.Exit: The libraries cannot be added.
    """
    console = get_console()
    env_changed = changes.update_environment(options, libraries.env_vars())
    try:
        tables_changed = changes.add_libraries(options, libraries)
        pins_changed = pin and changes.pin_libraries(options, libraries.symbol_dir)
    except Exception as e:
        console.print(f"[red]Error adding libraries: {e}[/red]")
        if options.verbose:
            console.print(traceback.format_exc())
        raise typer.Exit(1) from e

    changed = env_changed or tables_changed or pins_changed
    if not changed:
        console.print("[blue]No changes needed, configuration is up to date[/blue]")
    elif options.dry_run:
        console.print("[yellow]Dry run: No changes were made[/yellow]")
    return changed
