"""The ``list`` command: show the libraries in a library directory."""

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from kicad_lib_manager.commands.shared import resolve_kicad_lib_dir
from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import SYMBOL_DIR_VAR


def _print_library_table(
    kind: str, names: list[str], extension: str, style: str
) -> None:
    """Print the ``kind`` libraries in ``names``, or a notice when there are none."""
    console = get_console()
    if not names:
        console.print(f"[yellow]No {kind} libraries found[/yellow]")
        return
    table = Table(
        title=f"Available {kind.capitalize()} Libraries",
        show_header=True,
        header_style=f"bold {style}",
    )
    table.add_column("Library Name", style=style, no_wrap=True)
    table.add_column("Type", style="blue")
    for name in sorted(names):
        table.add_row(name, extension)
    console.print(table)


def list_cmd(
    *,
    kicad_lib_dir: Annotated[
        str | None,
        typer.Option(
            "--kicad-lib-dir",
            help=(
                "KiCad library directory (uses KICAD_USER_LIB env var if not specified)"
            ),
            envvar=SYMBOL_DIR_VAR,
        ),
    ] = None,
) -> None:
    """List available libraries in the specified directory.

    This command scans the KiCad library directory for symbol (.kicad_sym) and
    footprint (.pretty) libraries and displays them in organized tables.
    """
    library_dir = resolve_kicad_lib_dir(kicad_lib_dir)
    console = get_console()
    try:
        symbols, footprints = LibraryService().list_libraries(Path(library_dir))
    except Exception as e:
        console.print(f"[red]Error listing libraries: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[blue]Scanning library directory:[/blue] {library_dir}\n")
    _print_library_table("symbol", symbols, ".kicad_sym", "cyan")
    console.print()
    _print_library_table("footprint", footprints, ".pretty", "magenta")

    total = len(symbols) + len(footprints)
    if total == 0:
        console.print("[yellow]No libraries found in the specified directory[/yellow]")
        return
    console.print(
        f"\n[green]Found {total} libraries total[/green] "
        f"([cyan]{len(symbols)} symbol[/cyan], "
        f"[magenta]{len(footprints)} footprint[/magenta])"
    )
