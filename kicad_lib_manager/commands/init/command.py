"""The ``init`` command: register the current directory as a KiCad library.

The directory gets ``symbols``, ``footprints``, and ``templates`` folders, a
metadata file, and a ``library_descriptions.yaml`` template, and is recorded
in the KiLM configuration as a GitHub library.
"""

from pathlib import Path
from typing import Annotated

import typer
from rich.panel import Panel
from rich.prompt import Confirm

from kicad_lib_manager.commands.kicad_common import as_json_object
from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.console import get_console

LIBRARY_DESCRIPTIONS_FILE = "library_descriptions.yaml"
LIBRARY_DESCRIPTIONS_TEMPLATE = """\
# Library Descriptions for KiCad
# Format:
#   library_name: "Description text"
#
# Example:
#   Symbols_library: "Sample symbol library description"

# Symbol library descriptions
symbols:
  Symbols_library: "Sample symbol library description"

# Footprint library descriptions
footprints:
  Footprints_library: "Sample footprint library description"
"""


def _sort_folders(
    capabilities: object, present_before: set[str]
) -> tuple[list[str], list[str]]:
    """Split the library folders into those that existed and those just created.

    ``capabilities`` maps folder names to whether the library has them, as
    stored in the metadata; ``present_before`` names the directory entries
    from before initialization.
    """
    existing: list[str] = []
    created: list[str] = []
    for folder, present in (as_json_object(capabilities) or {}).items():
        if present:
            (existing if folder in present_before else created).append(folder)
    return existing, created


def _write_descriptions_template(directory: Path) -> None:
    """Create ``library_descriptions.yaml`` unless the library already has one."""
    path = directory / LIBRARY_DESCRIPTIONS_FILE
    if path.exists():
        return
    console = get_console()
    try:
        path.write_text(LIBRARY_DESCRIPTIONS_TEMPLATE, encoding="utf-8")
    except OSError as e:
        console.print(
            "[yellow]Warning: Could not create library_descriptions.yaml "
            f"file: {e}[/yellow]"
        )
        return
    console.print("[green]Created library_descriptions.yaml template file.[/green]")


def _report_folders(existing: list[str], created: list[str]) -> None:
    """Print the folder status; exit when there are none and the user stops."""
    console = get_console()
    if existing:
        console.print(f"[blue]Found existing folders:[/blue] {', '.join(existing)}")
    if created:
        console.print(f"[green]Created new folders:[/green] {', '.join(created)}")
    if existing or created:
        return
    console.print("[yellow]Warning: No library folders were found or created.[/yellow]")
    if not Confirm.ask("Continue anyway?", default=True):
        console.print("[yellow]Initialization cancelled.[/yellow]")
        raise typer.Exit(0)


def _success_message(
    name: str, directory: Path, env_var: object, *, set_current: bool
) -> str:
    """Return the body of the panel shown after a successful init."""
    message = (
        f"[bold green]Library '{name}' initialized successfully![/bold green]\n\n"
        "[cyan]Type:[/cyan] GitHub library (symbols, footprints, templates)\n"
        f"[cyan]Path:[/cyan] {directory}\n"
    )
    if env_var:
        message += f"[cyan]Environment Variable:[/cyan] {env_var}\n"
    if set_current:
        message += (
            "\n[yellow]This is now your current active library.[/yellow]\n"
            "[dim]KiLM will use this library for all commands by default.[/dim]"
        )
    return message


def init(  # noqa: PLR0913 -- each CLI option is a Typer parameter
    *,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            help="Name for this library collection (automatic if not provided)",
        ),
    ] = None,
    set_current: Annotated[
        bool,
        typer.Option(
            "--set-current/--no-set-current",
            help="Set this as the current active library",
        ),
    ] = True,
    description: Annotated[
        str | None,
        typer.Option(
            "--description",
            help="Description for this library collection",
        ),
    ] = None,
    env_var: Annotated[
        str | None,
        typer.Option(
            "--env-var",
            help="Custom environment variable name for this library",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing metadata file if present",
        ),
    ] = False,
    no_env_var: Annotated[
        bool,
        typer.Option(
            "--no-env-var",
            help="Don't assign an environment variable to this library",
        ),
    ] = False,
) -> None:
    """Initialize the current directory as a KiCad library collection.

    This command sets up the current directory as a KiCad library containing
    symbols, footprints, and templates. It creates the required folders if they
    don't exist and registers the library in the local configuration.

    [bold]Features:[/bold]
    • Creates symbol, footprint, and template directories
    • Generates metadata file with library information
    • Assigns unique environment variable for KiCad integration
    • Registers library in KiLM configuration

    [bold]Note:[/bold] This is intended for GitHub-based libraries containing
    symbols and footprints, not for 3D model libraries.
    """
    current_dir = Path.cwd().resolve()
    console = get_console()
    console.print(
        Panel(
            f"[bold blue]Initializing KiCad library[/bold blue]\n"
            f"[cyan]Location:[/cyan] {current_dir}",
            title="KiLM Library Initialization",
            border_style="blue",
        )
    )

    # The service creates the library folders, so note what exists beforehand.
    present_before = {entry.name for entry in current_dir.iterdir()}
    try:
        metadata = LibraryService().initialize_library(
            directory=current_dir,
            name=name,
            description=description,
            env_var=env_var,
            force=force,
            no_env_var=no_env_var,
        )
    except Exception as e:
        console.print(f"[red]Error initializing library: {e}[/red]")
        raise typer.Exit(1) from e

    _write_descriptions_template(current_dir)
    _report_folders(*_sort_folders(metadata.get("capabilities"), present_before))

    library_name = str(metadata.get("name") or current_dir.name)
    try:
        config = Config()
        config.add_library(library_name, str(current_dir), "github")
        if set_current:
            config.set_current_library(str(current_dir))
    except Exception as e:
        console.print(f"[red]Error initializing library: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(
        Panel(
            _success_message(
                library_name,
                current_dir,
                metadata.get("env_var"),
                set_current=set_current,
            ),
            title="✅ Initialization Complete",
            border_style="green",
        )
    )
    console.print("\n[bold]Next Steps:[/bold]")
    console.print("To add a 3D models directory (typically stored in the cloud), use:")
    console.print(
        "[dim]  kilm add-3d --name my-3d-models --directory /path/to/3d/models[/dim]"
    )
