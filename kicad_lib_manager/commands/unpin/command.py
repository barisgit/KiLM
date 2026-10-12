"""The ``unpin`` command: remove libraries from KiCad's quick-access lists."""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel

from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import DEFAULT_MAX_BACKUPS, KICAD_COMMON_FILE
from kicad_lib_manager.utils.kicad_common import (
    PINNED_FOOTPRINTS_KEY,
    PINNED_SYMBOLS_KEY,
    as_list,
    load_json_object,
    pinned_names,
    replace_json_object,
    session_of,
)

NO_SESSION = (
    "[yellow]No session information found in KiCad configuration, "
    "nothing to unpin[/yellow]"
)


def _find_kicad_common(*, verbose: bool) -> Path:
    """Return the path of kicad_common.json; exit when KiCad is not configured."""
    console = get_console()
    try:
        kicad_config = LibraryService.find_kicad_config()
    except Exception as e:
        console.print(f"[red]Error finding KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e
    if verbose:
        console.print(f"Found KiCad configuration at: [blue]{kicad_config}[/blue]")
    return kicad_config / KICAD_COMMON_FILE


def _all_pinned(kicad_common: Path, *, verbose: bool) -> tuple[list[str], list[str]]:
    """Return every pinned symbol and footprint library.

    Exits with status 1 when the file cannot be read, and with status 0 when
    nothing is pinned.
    """
    console = get_console()
    try:
        session = session_of(load_json_object(kicad_common))
    except Exception as e:
        console.print(f"[red]Error reading pinned libraries: {e}[/red]")
        raise typer.Exit(1) from e
    if session is None:
        console.print(NO_SESSION)
        raise typer.Exit
    symbols = pinned_names(session, PINNED_SYMBOLS_KEY)
    footprints = pinned_names(session, PINNED_FOOTPRINTS_KEY)
    if verbose and symbols:
        console.print(f"Found [cyan]{len(symbols)}[/cyan] pinned symbol libraries")
    if verbose and footprints:
        console.print(
            f"Found [cyan]{len(footprints)}[/cyan] pinned footprint libraries"
        )
    if not symbols and not footprints:
        console.print("[yellow]No pinned libraries found, nothing to unpin[/yellow]")
        raise typer.Exit
    return symbols, footprints


def _remove_pins(
    kicad_common: Path,
    unpinned: dict[str, list[str]],
    *,
    dry_run: bool,
    max_backups: int,
) -> bool | None:
    """Remove the libraries in ``unpinned`` from the pinned lists they name.

    ``unpinned`` maps a pinned-list key to the libraries to remove from it.
    Returns whether any pinned list changes, or None when the file has no
    session. Unless ``dry_run`` is set, a changed file is backed up and then
    replaced atomically.
    """
    config = load_json_object(kicad_common)
    session = session_of(config)
    if session is None:
        return None
    changed = False
    for key, libraries in unpinned.items():
        if key not in session or not libraries:
            continue
        current = as_list(session[key])
        kept = [library for library in current if library not in libraries]
        if len(kept) != len(current):
            changed = True
            session[key] = kept
    if changed and not dry_run:
        config["session"] = session
        replace_json_object(kicad_common, config, max_backups=max_backups)
    return changed


def _report(
    symbols: list[str], footprints: list[str], *, changed: bool, dry_run: bool
) -> None:
    """Print the outcome of an unpin request."""
    console = get_console()
    counts = f"{len(symbols)} symbol and {len(footprints)} footprint libraries"
    if not changed:
        console.print(
            "[yellow]No changes needed, libraries already unpinned in KiCad[/yellow]"
        )
    elif dry_run:
        console.print(f"[yellow]Would unpin {counts} in KiCad[/yellow]")
    else:
        console.print(
            Panel(
                f"[green]Unpinned {counts} in KiCad[/green]\n\n"
                "[blue]• Created backup of kicad_common.json[/blue]\n"
                "[yellow]• Restart KiCad for changes to take effect[/yellow]",
                title="Libraries Unpinned",
                border_style="green",
            )
        )


def _print_names(kind: str, names: list[str]) -> None:
    """List ``names`` under a heading for the ``kind`` of library."""
    if not names:
        return
    console = get_console()
    console.print(f"\n[bold cyan]Unpinned {kind} Libraries:[/bold cyan]")
    for name in sorted(names):
        console.print(f"  • [cyan]{name}[/cyan]")


def unpin(  # noqa: PLR0913 -- each CLI option is a Typer parameter
    *,
    symbols: Annotated[
        list[str] | None,
        typer.Option(
            "--symbols",
            "-s",
            help="Symbol libraries to unpin (can be specified multiple times)",
        ),
    ] = None,
    footprints: Annotated[
        list[str] | None,
        typer.Option(
            "--footprints",
            "-f",
            help="Footprint libraries to unpin (can be specified multiple times)",
        ),
    ] = None,
    all_libraries: Annotated[
        bool, typer.Option("--all", help="Unpin all libraries")
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be done without making changes"
        ),
    ] = False,
    max_backups: Annotated[
        int, typer.Option("--max-backups", help="Maximum number of backups to keep")
    ] = DEFAULT_MAX_BACKUPS,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show verbose output for debugging"),
    ] = False,
) -> None:
    """Remove libraries from KiCad's pinned lists in kicad_common.json.

    Takes the named --symbols and --footprints, or every pinned library with
    --all, and backs up the file before changing it. A missing file or
    session leaves nothing to unpin. Exits 1 when no library is named,
    --all is combined with names, or the file cannot be updated.
    """
    console = get_console()
    selected_symbols = symbols or []
    selected_footprints = footprints or []
    if all_libraries and (selected_symbols or selected_footprints):
        console.print(
            "[red]Error: '--all' cannot be used with '--symbols' or "
            "'--footprints'[/red]"
        )
        raise typer.Exit(1)

    kicad_common = _find_kicad_common(verbose=verbose)
    if not kicad_common.exists():
        console.print(
            "[yellow]KiCad common configuration file not found, "
            "nothing to unpin[/yellow]"
        )
        return

    if all_libraries:
        selected_symbols, selected_footprints = _all_pinned(
            kicad_common, verbose=verbose
        )
    elif not selected_symbols and not selected_footprints:
        console.print("[red]Error: No libraries specified to unpin[/red]")
        console.print(
            "[yellow]Use --symbols, --footprints, or --all to specify libraries "
            "to unpin[/yellow]"
        )
        raise typer.Exit(1)

    try:
        changed = _remove_pins(
            kicad_common,
            {
                PINNED_SYMBOLS_KEY: selected_symbols,
                PINNED_FOOTPRINTS_KEY: selected_footprints,
            },
            dry_run=dry_run,
            max_backups=max_backups,
        )
    except Exception as e:
        console.print(f"[red]Error unpinning libraries: {e}[/red]")
        raise typer.Exit(1) from e
    if changed is None:
        console.print(NO_SESSION)
        return

    _report(selected_symbols, selected_footprints, changed=changed, dry_run=dry_run)
    if verbose:
        _print_names("Symbol", selected_symbols)
        _print_names("Footprint", selected_footprints)
