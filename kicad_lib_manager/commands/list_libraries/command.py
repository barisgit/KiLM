"""
List command implementation for KiCad Library Manager (Typer version).
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from ...services.library_service import LibraryService
from ...utils.env_vars import expand_user_path, find_environment_variables

console = Console()


def list_cmd(
    kicad_lib_dir: Annotated[
        Optional[str],
        typer.Option(
            "--kicad-lib-dir",
            help="KiCad library directory (uses KICAD_USER_LIB env var if not specified)",
            envvar="KICAD_USER_LIB",
        ),
    ] = None,
) -> None:
    """
    List available libraries in the specified directory.

    This command scans the KiCad library directory for symbol (.kicad_sym) and
    footprint (.pretty) libraries and displays them in organized tables.
    """
    # Find environment variables if not provided
    if not kicad_lib_dir:
        kicad_lib_dir = find_environment_variables("KICAD_USER_LIB")
        if not kicad_lib_dir:
            console.print("[red]Error: KICAD_USER_LIB not set and not provided[/red]")
            raise typer.Exit(1)

    # Expand user home directory if needed
    kicad_lib_dir = expand_user_path(kicad_lib_dir)

    try:
        library_service = LibraryService()
        symbols, footprints = library_service.list_libraries(Path(kicad_lib_dir))

        console.print(f"[blue]Scanning library directory:[/blue] {kicad_lib_dir}\n")

        # Display symbol libraries in a table
        if symbols:
            symbol_table = Table(
                title="Available Symbol Libraries",
                show_header=True,
                header_style="bold cyan",
            )
            symbol_table.add_column("Library Name", style="cyan", no_wrap=True)
            symbol_table.add_column("Type", style="blue")

            for symbol in sorted(symbols):
                symbol_table.add_row(symbol, ".kicad_sym")

            console.print(symbol_table)
        else:
            console.print("[yellow]No symbol libraries found[/yellow]")

        console.print()  # Empty line for spacing

        # Display footprint libraries in a table
        if footprints:
            footprint_table = Table(
                title="Available Footprint Libraries",
                show_header=True,
                header_style="bold magenta",
            )
            footprint_table.add_column("Library Name", style="magenta", no_wrap=True)
            footprint_table.add_column("Type", style="blue")

            for footprint in sorted(footprints):
                footprint_table.add_row(footprint, ".pretty")

            console.print(footprint_table)
        else:
            console.print("[yellow]No footprint libraries found[/yellow]")

        # Summary information
        total_libs = len(symbols) + len(footprints)
        if total_libs > 0:
            console.print(
                f"\n[green]Found {total_libs} libraries total[/green] "
                f"([cyan]{len(symbols)} symbol[/cyan], "
                f"[magenta]{len(footprints)} footprint[/magenta])"
            )
        else:
            console.print(
                "[yellow]No libraries found in the specified directory[/yellow]"
            )

    except Exception as e:
        console.print(f"[red]Error listing libraries: {e}[/red]")
        raise typer.Exit(1) from e
