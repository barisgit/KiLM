"""The ``status`` command: summarize the KiLM and KiCad configuration.

Each section reports its own read errors and the command carries on, so one
unreadable file does not hide the rest of the status.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"yaml"}

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from kicad_lib_manager.commands.kicad_common import (
    PINNED_FOOTPRINTS_KEY,
    PINNED_SYMBOLS_KEY,
    as_json_object,
    as_list,
    load_json_object,
    pinned_names,
    session_of,
)
from kicad_lib_manager.services.kicad_service import KiCadService
from kicad_lib_manager.services.user_paths import user_config_file
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import KICAD_COMMON_FILE
from kicad_lib_manager.utils.env_vars import JsonObject
from kicad_lib_manager.utils.file_ops import LibraryTableEntry
from kicad_lib_manager.utils.metadata import read_cloud_metadata, read_github_metadata

LEGACY_PINNED_FILE = "pinned"
LEGACY_PINNED_FOOTPRINTS_KEY = "pinned_footprint_libs"

MetadataReader = Callable[[Path], object | None]


def status(
    *,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed configured libraries tables",
        ),
    ] = False,
) -> None:
    """Show the current KiCad configuration status."""
    console = get_console()
    try:
        kicad_service = KiCadService()
        _show_kilm_configuration()
        console.print("\n[bold cyan]KiCad Configuration[/bold cyan]")
        kicad_config = kicad_service.find_kicad_config_dir()
        console.print(f"KiCad configuration directory: [blue]{kicad_config}[/blue]")
        _show_kicad_environment_variables(kicad_config)
        _show_pinned_libraries(kicad_config)
        if verbose:
            _show_configured_libraries(kicad_config, kicad_service)
    except Exception as e:
        console.print(f"[red]Error getting KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e


def _show_kilm_configuration() -> None:
    """Show the libraries and settings in the KiLM configuration file."""
    console = get_console()
    try:
        config_file = user_config_file()
        exists = config_file.exists()
    except (OSError, RuntimeError) as e:
        console.print(f"[red]Error reading KILM configuration: {e}[/red]")
        return
    if not exists:
        console.print(
            "[yellow]No KILM configuration file found. Run 'kilm init' to create "
            "one.[/yellow]"
        )
        return

    console.print("[bold cyan]KILM Configuration[/bold cyan]")
    try:
        # Parsing the open file keeps its name in YAML error messages.
        with config_file.open(encoding="utf-8") as stream:
            loaded: object = yaml.safe_load(stream)
    except (OSError, ValueError, yaml.YAMLError) as e:
        console.print(f"[red]Error reading configuration: {e}[/red]")
        return
    config_data = as_json_object(loaded)
    if config_data is None:
        console.print("[yellow]Configuration file is empty or invalid[/yellow]")
        return
    _show_configured_libraries_tables(config_data)
    _show_kilm_settings(config_data)


def _show_library_table(
    title: str,
    libraries: list[JsonObject],
    current_library: object,
    read_metadata: MetadataReader,
) -> None:
    """Print one table of KiLM libraries, marking the current one."""
    if not libraries:
        return
    table = Table(title=title, show_header=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Path", style="blue")
    table.add_column("Status", justify="center")
    table.add_column("Metadata", justify="center")
    for library in libraries:
        path = str(library.get("path", "unknown"))
        metadata = read_metadata(Path(path))
        table.add_row(
            str(library.get("name", "unnamed")),
            path,
            "✓ Current" if current_library == path else "",
            "✓" if metadata is not None and metadata else "✗",
        )
    get_console().print(table)


def _show_configured_libraries_tables(config_data: JsonObject) -> None:
    """Show the configured GitHub and cloud libraries as tables."""
    libraries = [
        library
        for entry in as_list(config_data.get("libraries"))
        if (library := as_json_object(entry)) is not None
    ]
    if not libraries:
        get_console().print("[yellow]  No libraries configured[/yellow]")
        return

    current_library = config_data.get("current_library", "")
    _show_library_table(
        "GitHub Libraries (symbols/footprints)",
        [library for library in libraries if library.get("type") == "github"],
        current_library,
        read_github_metadata,
    )
    _show_library_table(
        "Cloud Libraries (3D models)",
        [library for library in libraries if library.get("type") == "cloud"],
        current_library,
        read_cloud_metadata,
    )


def _show_kilm_settings(config_data: JsonObject) -> None:
    """Show the current library and backup settings."""
    if not config_data:
        return
    settings_text = Text()
    current_library = config_data.get("current_library")
    if current_library:
        settings_text.append(f"Current Library: {current_library}\n", style="green")
    else:
        settings_text.append("No current library set\n", style="yellow")
    max_backups = config_data.get("max_backups")
    if max_backups is not None:
        settings_text.append(f"Max Backups: {max_backups}", style="blue")
    get_console().print(Panel(settings_text, title="Settings", border_style="blue"))


def _show_kicad_environment_variables(kicad_config: Path) -> None:
    """Show the path variables set in kicad_common.json."""
    console = get_console()
    kicad_common = kicad_config / KICAD_COMMON_FILE
    if not kicad_common.exists():
        console.print("[yellow]No kicad_common.json found[/yellow]")
        return
    try:
        common_config = load_json_object(kicad_common)
    except (OSError, ValueError) as e:
        console.print(f"[red]Error reading KiCad common configuration: {e}[/red]")
        return

    console.print("\n[bold]Environment Variables in KiCad:[/bold]")
    environment = as_json_object(common_config.get("environment"))
    if environment is None or "vars" not in environment:
        console.print("[yellow]  No environment variables found[/yellow]")
        return
    variables = as_json_object(environment["vars"])
    if variables is None or not variables:
        console.print("[yellow]  No environment variables set[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("Variable", style="cyan", no_wrap=True)
    table.add_column("Value", style="blue")
    for key, value in variables.items():
        table.add_row(key, str(value))
    console.print(table)


def _print_pinned(symbols: list[str], footprints: list[str], none_found: str) -> None:
    """List pinned libraries, or print ``none_found`` when there are none."""
    console = get_console()
    for heading, names in (("Symbol", symbols), ("Footprint", footprints)):
        if names:
            console.print(f"[cyan]{heading} Libraries:[/cyan]")
            for name in names:
                console.print(f"  • {name}")
    if not symbols and not footprints:
        console.print(f"[yellow]  {none_found}[/yellow]")


def _show_pinned_libraries(kicad_config: Path) -> None:
    """Show the pinned libraries from kicad_common.json.

    Falls back to the separate ``pinned`` file of older KiCad versions when
    kicad_common.json is missing or unreadable.
    """
    console = get_console()
    kicad_common = kicad_config / KICAD_COMMON_FILE
    if kicad_common.exists():
        try:
            session = session_of(load_json_object(kicad_common)) or {}
        except (OSError, ValueError) as e:
            console.print(
                f"[red]Error reading pinned libraries from kicad_common.json: {e}[/red]"
            )
        else:
            console.print("\n[bold]Pinned Libraries in KiCad:[/bold]")
            _print_pinned(
                pinned_names(session, PINNED_SYMBOLS_KEY),
                pinned_names(session, PINNED_FOOTPRINTS_KEY),
                "No pinned libraries found in kicad_common.json",
            )
            return
    _show_legacy_pinned_libraries(kicad_config / LEGACY_PINNED_FILE)


def _show_legacy_pinned_libraries(pinned_file: Path) -> None:
    """Show the pinned libraries from a pre-KiCad 6 ``pinned`` file."""
    console = get_console()
    if not pinned_file.exists():
        console.print("\n[yellow]No pinned libraries file found[/yellow]")
        return
    try:
        pinned_config = load_json_object(pinned_file)
    except (OSError, ValueError) as e:
        console.print(f"[red]Error reading pinned libraries: {e}[/red]")
        return
    console.print("\n[bold]Pinned Libraries in KiCad (legacy format):[/bold]")
    _print_pinned(
        pinned_names(pinned_config, PINNED_SYMBOLS_KEY),
        pinned_names(pinned_config, LEGACY_PINNED_FOOTPRINTS_KEY),
        "No pinned libraries found",
    )


def _print_configured(kind: str, libraries: list[LibraryTableEntry]) -> None:
    """Print the libraries in one KiCad library table."""
    console = get_console()
    console.print(f"\n[bold]Configured {kind} Libraries:[/bold]")
    if not libraries:
        console.print(f"[yellow]  No {kind.lower()} libraries configured[/yellow]")
        return
    table = Table(show_header=True)
    table.add_column("Library Name", style="cyan", no_wrap=True)
    table.add_column("URI", style="blue")
    for library in libraries:
        table.add_row(library["name"], library.get("uri", ""))
    console.print(table)


def _show_configured_libraries(kicad_config: Path, kicad_service: KiCadService) -> None:
    """Show the libraries in KiCad's symbol and footprint library tables."""
    try:
        symbols, footprints = kicad_service.get_configured_libraries(kicad_config)
    except (OSError, ValueError) as e:
        get_console().print(f"[red]Error listing configured libraries: {e}[/red]")
        return
    _print_configured("Symbol", symbols)
    _print_configured("Footprint", footprints)
