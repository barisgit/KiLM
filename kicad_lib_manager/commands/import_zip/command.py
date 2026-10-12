"""Import command: add the parts in vendor KiCad ZIPs to a KiLM library.

The work is split by concern: archive (safe extraction), symbols (merging
into a .kicad_sym), formats and kicad_cli (format limits and upgrades),
importer (planning and applying one ZIP), and target (which libraries to
write). This module holds the CLI entry point and the run summary.
"""

from pathlib import Path
from typing import Annotated

import typer

from kicad_lib_manager.utils.console import get_console

from ...services.config_service import Config
from .errors import ImportFailure
from .importer import ImportTarget, ZipResult, import_zip_file
from .kicad_cli import Upgrader, detect_kicad_cli
from .target import build_target


def import_zip(
    zip_files: Annotated[
        list[Path],
        typer.Argument(
            help="SamacSys/Mouser/UltraLibrarian/SnapMagic ZIP file(s) to import"
        ),
    ],
    library: Annotated[
        str | None,
        typer.Option(
            "--library",
            "-l",
            help="Target library name (default: the current library)",
        ),
    ] = None,
    symbol_lib: Annotated[
        str | None,
        typer.Option(
            "--symbol-lib",
            "-s",
            help="Symbol library to add to, e.g. MyLib_IC (required if there are several)",
        ),
    ] = None,
    footprint_lib: Annotated[
        str | None,
        typer.Option(
            "--footprint-lib",
            "-f",
            help="Footprint library to add to, e.g. MyLib_QFN (required if there are several)",
        ),
    ] = None,
    kicad_cli_path: Annotated[
        Path | None,
        typer.Option(
            "--kicad-cli", help="Path to kicad-cli or kicad.appimage for format upgrade"
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be imported without making changes"
        ),
    ] = False,
) -> None:
    """Import SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP(s) into the configured library.

    Each ZIP should be a standard SamacSys multi-EDA archive (as downloaded
    from Mouser or component search) or an UltraLibrarian KiCad export.
    The command extracts the KiCad files
    and merges them into the library. Run 'kilm setup' afterwards to register
    any newly added libraries in KiCad.
    """
    upgrader = Upgrader(_resolve_kicad_cli(kicad_cli_path))
    target = build_target(
        Config(), library, symbol_lib, footprint_lib, upgrader, dry_run
    )
    if dry_run:
        get_console().print("[yellow]Dry run - no changes will be made[/yellow]")

    totals = ZipResult()
    failed: list[str] = []
    for zip_path in zip_files:
        result = _import_one(zip_path.expanduser().resolve(), target)
        if result is None:
            failed.append(zip_path.name)
        else:
            totals.extend(result)

    _print_summary(totals, dry_run)
    if failed:
        get_console().print(f"[red]Failed to import: {', '.join(failed)}[/red]")
        raise typer.Exit(1)


def _resolve_kicad_cli(path: Path | None) -> Path | None:
    """kicad-cli to upgrade with: path when given (it must exist), else a detected one."""
    if path is not None and not path.exists():
        get_console().print(f"[red]kicad-cli not found at: {path}[/red]")
        raise typer.Exit(1)
    kicad_cli = path or detect_kicad_cli()
    if kicad_cli:
        get_console().print(f"[dim]kicad-cli: {kicad_cli}[/dim]")
    else:
        get_console().print("[dim]kicad-cli not found - format upgrade skipped[/dim]")
    return kicad_cli


def _import_one(zip_path: Path, target: ImportTarget) -> ZipResult | None:
    """Import one ZIP and return what it added, or None after reporting a failure.

    A failed ZIP does not stop the run; the caller imports the rest.
    """
    if not zip_path.exists():
        get_console().print(f"[red]Skipping {zip_path.name}: file not found[/red]")
        return None
    get_console().print(f"\n[cyan]Importing {zip_path.name}[/cyan]")
    try:
        return import_zip_file(zip_path, target)
    except (ImportFailure, OSError) as exc:
        get_console().print(
            f"  error: {zip_path.name}: {exc}", style="red", markup=False
        )
        return None


def _print_summary(totals: ZipResult, dry_run: bool) -> None:
    get_console().print("\n[bold]Summary:[/bold]")
    get_console().print(f"  Symbols   added: {len(totals.symbols)}")
    get_console().print(f"  Footprints added: {len(totals.footprints)}")
    get_console().print(f"  3D models  added: {len(totals.models)}")

    if dry_run:
        get_console().print(
            "\n[dim]Dry run complete - run without --dry-run to apply changes.[/dim]"
        )
    elif totals.symbols or totals.footprints or totals.models:
        get_console().print("\n[green]Import complete.[/green]")
        get_console().print(
            "[dim]Note: If this library is not yet configured in KiCad, run 'kilm setup' to register it.[/dim]"
        )
    else:
        get_console().print("\n[dim]Nothing new added.[/dim]")
