"""The ``pin`` command: pin libraries in KiCad's quick-access lists."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from kicad_lib_manager.commands.shared import resolve_kicad_lib_dir
from kicad_lib_manager.services.kicad_service import KiCadService
from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.env_vars import update_pinned_libraries


def _find_kicad_config(*, verbose: bool) -> Path:
    """Return KiCad's configuration directory; exit when it cannot be found."""
    console = get_console()
    try:
        kicad_config = KiCadService().find_kicad_config_dir()
    except Exception as e:
        console.print(f"[red]Error finding KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e
    if verbose:
        console.print(f"[blue]Found KiCad configuration at:[/blue] {kicad_config}")
    return kicad_config


def _all_libraries(library_dir: Path, *, verbose: bool) -> tuple[list[str], list[str]]:
    """Return every symbol and footprint library in ``library_dir``."""
    try:
        symbols, footprints = LibraryService().list_libraries(library_dir)
    except Exception as e:
        get_console().print(f"[red]Error listing libraries: {e}[/red]")
        raise typer.Exit(1) from e
    if verbose:
        get_console().print(
            f"[green]Found {len(symbols)} symbol libraries and "
            f"{len(footprints)} footprint libraries[/green]"
        )
    return symbols, footprints


def _warn_about_missing(
    library_dir: Path, symbols: list[str], footprints: list[str]
) -> None:
    """Warn about selected libraries that ``library_dir`` does not contain.

    Pinning goes ahead regardless, since a library may be configured in KiCad
    without living in the library directory.
    """
    console = get_console()
    try:
        available_symbols, available_footprints = LibraryService().list_libraries(
            library_dir
        )
    except OSError as e:
        console.print(f"[yellow]Error validating libraries: {e}[/yellow]")
        return
    for symbol in symbols:
        if symbol not in available_symbols:
            console.print(
                f"[yellow]Warning: Symbol library '{symbol}' not found[/yellow]"
            )
    for footprint in footprints:
        if footprint not in available_footprints:
            console.print(
                f"[yellow]Warning: Footprint library '{footprint}' not found[/yellow]"
            )


def _report(
    symbols: list[str], footprints: list[str], *, changed: bool, dry_run: bool
) -> None:
    """Print the outcome of a pin request."""
    console = get_console()
    counts = f"{len(symbols)} symbol and {len(footprints)} footprint libraries"
    if not changed:
        console.print(
            "[blue]No changes needed, libraries already pinned in KiCad[/blue]"
        )
    elif dry_run:
        console.print(f"[yellow]Would pin {counts} in KiCad[/yellow]")
    else:
        console.print(
            Panel(
                f"[green]Pinned {counts} in KiCad[/green]\n\n"
                "[blue]• Created backup of kicad_common.json[/blue]\n"
                "[yellow]• Restart KiCad for changes to take effect[/yellow]",
                title="Libraries Pinned",
                border_style="green",
            )
        )


def _print_table(kind: str, names: list[str], style: str) -> None:
    """Print the pinned ``kind`` libraries in ``names`` as a table."""
    if not names:
        return
    table = Table(title=f"Pinned {kind} Libraries")
    table.add_column("Library", style=style)
    for name in sorted(names):
        table.add_row(name)
    get_console().print(table)


def pin(  # noqa: PLR0913 -- each CLI option is a Typer parameter
    *,
    kicad_lib_dir: Annotated[
        str | None,
        typer.Option(
            "--kicad-lib-dir",
            envvar="KICAD_USER_LIB",
            help=(
                "KiCad library directory (uses KICAD_USER_LIB env var if not specified)"
            ),
        ),
    ] = None,
    symbols: Annotated[
        list[str] | None,
        typer.Option(
            "--symbols",
            "-s",
            help="Symbol libraries to pin (can be specified multiple times)",
        ),
    ] = None,
    footprints: Annotated[
        list[str] | None,
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
    """Pin libraries in KiCad for quick access.

    This command pins libraries in KiCad's interface for quick access.
    You can pin specific symbol and footprint libraries or all available libraries.
    """
    library_dir = Path(resolve_kicad_lib_dir(kicad_lib_dir))
    if verbose:
        get_console().print(
            f"[blue]Using KiCad library directory:[/blue] {library_dir}"
        )
    kicad_config = _find_kicad_config(verbose=verbose)

    selected_symbols = symbols or []
    selected_footprints = footprints or []
    if all_libs and not selected_symbols and not selected_footprints:
        selected_symbols, selected_footprints = _all_libraries(
            library_dir, verbose=verbose
        )
    elif not all_libs and (selected_symbols or selected_footprints):
        _warn_about_missing(library_dir, selected_symbols, selected_footprints)

    try:
        changed = update_pinned_libraries(
            kicad_config,
            symbol_libs=selected_symbols,
            footprint_libs=selected_footprints,
            dry_run=dry_run,
            max_backups=max_backups,
        )
    except Exception as e:
        get_console().print(f"[red]Error pinning libraries: {e}[/red]")
        raise typer.Exit(1) from e

    _report(selected_symbols, selected_footprints, changed=changed, dry_run=dry_run)
    if verbose:
        _print_table("Symbol", selected_symbols, "cyan")
        _print_table("Footprint", selected_footprints, "magenta")
