"""
Pin command implementation for KiCad Library Manager (Typer version).
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...services.kicad_service import KiCadService
from ...services.library_service import LibraryService
from ...utils.env_vars import (
    expand_user_path,
    find_environment_variables,
    update_pinned_libraries,
)

console = Console()


def pin(
    kicad_lib_dir: Annotated[
        Optional[str],
        typer.Option(
            "--kicad-lib-dir",
            envvar="KICAD_USER_LIB",
            help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
        ),
    ] = None,
    symbols: Annotated[
        Optional[list[str]],
        typer.Option(
            "--symbols",
            "-s",
            help="Symbol libraries to pin (can be specified multiple times)",
        ),
    ] = None,
    footprints: Annotated[
        Optional[list[str]],
        typer.Option(
            "--footprints",
            "-f",
            help="Footprint libraries to pin (can be specified multiple times)",
        ),
    ] = None,
    all_libs: Annotated[
        bool,
        typer.Option(
            "--all/--selected",
            help="Pin all available libraries or only selected ones",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be done without making changes",
        ),
    ] = False,
    max_backups: Annotated[
        int,
        typer.Option(
            "--max-backups",
            help="Maximum number of backups to keep",
        ),
    ] = 5,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show verbose output for debugging",
        ),
    ] = False,
) -> None:
    """
    Pin libraries in KiCad for quick access.

    This command pins libraries in KiCad's interface for quick access.
    You can pin specific symbol and footprint libraries or all available libraries.
    """
    # Initialize default values for mutable types
    if symbols is None:
        symbols = []
    if footprints is None:
        footprints = []

    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            console.print("[red]Error: KICAD_USER_LIB not set and not provided[/red]")
            raise typer.Exit(1)

    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)

    if verbose:
        console.print(f"[blue]Using KiCad library directory:[/blue] {kicad_lib_dir}")

    # Initialize services
    library_service = LibraryService()
    kicad_service = KiCadService()

    # Find KiCad configuration
    try:
        kicad_config = kicad_service.find_kicad_config_dir()
        if verbose:
            console.print(f"[blue]Found KiCad configuration at:[/blue] {kicad_config}")
    except Exception as e:
        console.print(f"[red]Error finding KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e

    # If --all is specified, get all libraries from the directory
    if all_libs and not symbols and not footprints:
        try:
            symbol_libs, footprint_libs = library_service.list_libraries(
                Path(kicad_lib_dir)
            )
            symbols = list(symbol_libs)
            footprints = list(footprint_libs)
            if verbose:
                console.print(
                    f"[green]Found {len(symbols)} symbol libraries and {len(footprints)} footprint libraries[/green]"
                )
        except Exception as e:
            console.print(f"[red]Error listing libraries: {e}[/red]")
            raise typer.Exit(1) from e

    # Ensure we have lists (Typer should already provide lists)
    if not isinstance(symbols, list):
        symbols = list(symbols) if symbols else []
    if not isinstance(footprints, list):
        footprints = list(footprints) if footprints else []

    # Validate that libraries exist
    if not all_libs and (symbols or footprints):
        try:
            available_symbols, available_footprints = library_service.list_libraries(
                Path(kicad_lib_dir)
            )

            # Check symbols
            for symbol in symbols:
                if symbol not in available_symbols:
                    console.print(
                        f"[yellow]Warning: Symbol library '{symbol}' not found[/yellow]"
                    )

            # Check footprints
            for footprint in footprints:
                if footprint not in available_footprints:
                    console.print(
                        f"[yellow]Warning: Footprint library '{footprint}' not found[/yellow]"
                    )
        except Exception as e:
            console.print(f"[yellow]Error validating libraries: {e}[/yellow]")
            # Continue anyway, in case the libraries are configured but not in the directory

    try:
        changes_needed = update_pinned_libraries(
            kicad_config,
            symbol_libs=symbols,
            footprint_libs=footprints,
            dry_run=dry_run,
            max_backups=max_backups,
        )

        if changes_needed:
            if dry_run:
                console.print(
                    f"[yellow]Would pin {len(symbols)} symbol and {len(footprints)} footprint libraries in KiCad[/yellow]"
                )
            else:
                success_msg = f"[green]Pinned {len(symbols)} symbol and {len(footprints)} footprint libraries in KiCad[/green]"
                console.print(
                    Panel(
                        f"{success_msg}\n\n"
                        f"[blue]• Created backup of kicad_common.json[/blue]\n"
                        f"[yellow]• Restart KiCad for changes to take effect[/yellow]",
                        title="✅ Libraries Pinned",
                        border_style="green",
                    )
                )
        else:
            console.print(
                "[blue]No changes needed, libraries already pinned in KiCad[/blue]"
            )

        if verbose:
            if symbols:
                table = Table(title="Pinned Symbol Libraries")
                table.add_column("Library", style="cyan")
                for symbol in sorted(symbols):
                    table.add_row(symbol)
                console.print(table)

            if footprints:
                table = Table(title="Pinned Footprint Libraries")
                table.add_column("Library", style="magenta")
                for footprint in sorted(footprints):
                    table.add_row(footprint)
                console.print(table)
    except Exception as e:
        console.print(f"[red]Error pinning libraries: {e}[/red]")
        raise typer.Exit(1) from e
