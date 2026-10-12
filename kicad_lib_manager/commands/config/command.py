"""Commands that list, select, and remove the libraries in the KiLM configuration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final

import click
import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from kicad_lib_manager.services.config_service import Config, LibraryDict
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import CLOUD_METADATA_FILE, GITHUB_METADATA_FILE
from kicad_lib_manager.utils.metadata import read_cloud_metadata, read_github_metadata

MODEL_EXTENSIONS: Final = (".step", ".stp", ".wrl", ".wings")
"""File extensions counted as 3D models when a library does not state its count."""


@dataclass(frozen=True)
class LibraryKind:
    """How `config list` presents one library type."""

    heading: str
    contents: str
    missing: str
    """Shown when no library of this type is configured."""


LIBRARY_KINDS: Final = {
    "github": LibraryKind(
        heading="GitHub Libraries",
        contents="symbols, footprints, templates",
        missing="[yellow]No GitHub libraries configured.[/yellow]\n\n"
        "[cyan]Get Started:[/cyan]\n"
        "• Initialize a GitHub library: [blue]kilm init[/blue]",
    ),
    "cloud": LibraryKind(
        heading="Cloud Libraries",
        contents="3D models",
        missing="[yellow]No cloud libraries configured.[/yellow]\n\n"
        "[cyan]Get Started:[/cyan]\n"
        "• Add a 3D model library: [blue]kilm add-3d[/blue]",
    ),
}
"""The library types `config list` shows, in display order."""

NO_LIBRARIES: Final = (
    "[yellow]No libraries configured.[/yellow]\n\n"
    "[cyan]Get Started:[/cyan]\n"
    "• Initialize GitHub library: [blue]kilm init[/blue]\n"
    "• Add 3D model library: [blue]kilm add-3d[/blue]\n"
    "• Check status: [blue]kilm status[/blue]"
)

LIST_HINT: Final = "Use 'kilm config list' to see available libraries."


def list_config(
    *,
    library_type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Type of libraries to list"
            " (github=symbols/footprints, cloud=3D models)",
        ),
    ] = "all",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show more information about libraries"),
    ] = False,
) -> None:
    """List the configured libraries of one type or of all types.

    With --verbose, each library also shows the metadata stored in its
    directory.
    """
    config = Config()
    libraries = config.get_libraries(None if library_type == "all" else library_type)
    console = get_console()
    console.print()
    if not libraries:
        kind = LIBRARY_KINDS.get(library_type)
        title = f"No {kind.heading}" if kind else "No Libraries"
        console.print(
            Panel(
                kind.missing if kind else NO_LIBRARIES,
                title=f"[bold yellow]{title}[/bold yellow]",
                border_style="yellow",
            )
        )
        return

    current = config.get_current_library()
    counts: dict[str, int] = {}
    for type_name, kind in LIBRARY_KINDS.items():
        of_type = [library for library in libraries if library["type"] == type_name]
        counts[type_name] = len(of_type)
        if of_type:
            _print_section(console, kind, of_type, current, verbose=verbose)

    console.print(
        Panel(
            f"[green]Total Libraries:[/green] {len(libraries)}\n"
            f"[cyan]GitHub:[/cyan] {counts['github']}  "
            f"[blue]Cloud:[/blue] {counts['cloud']}",
            title="[bold cyan]Summary[/bold cyan]",
            border_style="cyan",
            width=35,
        )
    )


def _print_section(
    console: Console,
    kind: LibraryKind,
    libraries: list[LibraryDict],
    current: str | None,
    *,
    verbose: bool,
) -> None:
    """Print the libraries of one type as a table, or as panels when verbose."""
    console.print(
        f"\n[bold cyan]{kind.heading}[/bold cyan] [dim]({kind.contents})[/dim]"
    )
    console.print()
    if not verbose:
        console.print(_library_table(libraries, current))
        console.print()
        return
    for library in libraries:
        is_current = library["path"] == current
        status = "[green]CURRENT[/green]" if is_current else "[dim]Available[/dim]"
        console.print(
            Panel(
                "\n".join(_library_details(library)),
                title=f"[bold cyan]{escape(library['name'])}[/bold cyan] [{status}]",
                border_style="cyan" if is_current else "dim",
            )
        )
        console.print()


def _library_table(libraries: list[LibraryDict], current: str | None) -> Table:
    """Return a table of library names, default marker, and paths."""
    table = Table(show_header=True, header_style="bold magenta", border_style="cyan")
    table.add_column("Library", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center", style="green", width=12)
    table.add_column("Path", style="blue")
    for library in libraries:
        status = (
            "[green]Current[/green]"
            if library["path"] == current
            else "[dim]Available[/dim]"
        )
        table.add_row(
            f"[bold]{escape(library['name'])}[/bold]", status, escape(library["path"])
        )
    return table


def _library_details(library: LibraryDict) -> list[str]:
    """Return the verbose lines for a library: path and its metadata."""
    path = Path(library["path"])
    lines = [f"[blue]Path:[/blue] {escape(library['path'])}"]
    if library["type"] == "cloud":
        lines += _cloud_details(path)
    else:
        lines += _github_details(path)
    return lines


def _github_details(path: Path) -> list[str]:
    """Return the metadata lines of a symbol and footprint library."""
    metadata = read_github_metadata(path)
    if metadata is None:
        return [f"[dim]No {GITHUB_METADATA_FILE} metadata file found[/dim]"]
    lines = _common_details(
        metadata.get("description"), metadata.get("version"), metadata.get("env_var")
    )
    capabilities = metadata.get("capabilities")
    if isinstance(capabilities, dict):
        features = [
            label
            for key, label in (
                ("symbols", "Symbols"),
                ("footprints", "Footprints"),
                ("templates", "Templates"),
            )
            if capabilities.get(key)
        ]
        lines.append(f"[white]Features:[/white] {', '.join(features) or 'none'}")
    return lines


def _cloud_details(path: Path) -> list[str]:
    """Return the metadata lines of a 3D model library, counting models if needed."""
    metadata = read_cloud_metadata(path)
    if metadata is None:
        return [
            f"[dim]No {CLOUD_METADATA_FILE} metadata file found[/dim]",
            _counted_models(path),
        ]
    lines = _common_details(
        metadata.get("description"), metadata.get("version"), metadata.get("env_var")
    )
    model_count = metadata.get("model_count")
    if model_count is None:
        lines.append(_counted_models(path))
    else:
        lines.append(f"[white]3D Models:[/white] {model_count}")
    return lines


def _common_details(description: object, version: object, env_var: object) -> list[str]:
    """Return the description, version, and environment variable lines that are set."""
    lines: list[str] = []
    if description is not None:
        lines.append(f"[green]Description:[/green] {escape(str(description))}")
    if version is not None:
        lines.append(f"[yellow]Version:[/yellow] {escape(str(version))}")
    if env_var:
        lines.append(f"[magenta]Environment Variable:[/magenta] {escape(str(env_var))}")
    return lines


def _counted_models(path: Path) -> str:
    """Return the model count line for a library by counting its model files."""
    count = sum(
        1
        for file in path.rglob("*")
        if file.suffix in MODEL_EXTENSIONS and file.is_file()
    )
    return f"[white]3D Models:[/white] {count} [dim](counted)[/dim]"


def set_default(
    library_name: Annotated[
        str | None, typer.Argument(help="Name of library to set as default")
    ] = None,
    *,
    library_type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Type of library to set as default"
            " (github=symbols/footprints, cloud=3D models)",
        ),
    ] = "github",
) -> None:
    """Make a library of the given type the default; prompt when no name is given.

    Exits with status 1 when no such library exists or the configuration
    cannot be saved.
    """
    console = get_console()
    config = Config()
    libraries = config.get_libraries(library_type)
    if not libraries:
        console.print(f"No {library_type} libraries configured.", markup=False)
        console.print(
            "Use 'kilm init' to initialize a GitHub library."
            if library_type == "github"
            else "Use 'kilm add-3d' to add a cloud-based 3D model library."
        )
        raise typer.Exit(1)

    if library_name is None:
        library = _prompt_for_library(
            console, libraries, config.get_current_library(), library_type
        )
    else:
        library = next(
            (library for library in libraries if library["name"] == library_name),
            None,
        )
        if library is None:
            console.print(
                f"No {library_type} library named '{library_name}' found.", markup=False
            )
            console.print(LIST_HINT)
            raise typer.Exit(1)

    try:
        config.set_current_library(library["path"])
    except OSError as e:
        console.print(f"[red]Error setting default library: {escape(str(e))}[/red]")
        raise typer.Exit(1) from e
    console.print(
        f"Set {library_type} library '{library['name']}' as default.", markup=False
    )
    console.print(f"Path: {library['path']}", markup=False)


def _prompt_for_library(
    console: Console,
    libraries: list[LibraryDict],
    current: str | None,
    library_type: str,
) -> LibraryDict:
    """Show a numbered list of libraries and return the one the user picks."""
    console.print(f"\nAvailable {library_type} libraries:", markup=False)
    for number, library in enumerate(libraries, start=1):
        marker = " (current)" if library["path"] == current else ""
        console.print(f"{number}. {library['name']}{marker}", markup=False)
    selection = int(
        typer.prompt(
            "Select library (number)",
            type=click.IntRange(1, len(libraries)),
            default=1,
        )
    )
    return libraries[selection - 1]


def remove(
    library_name: Annotated[str, typer.Argument(help="Name of library to remove")],
    *,
    library_type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Type of library to remove (all=remove from both types)",
        ),
    ] = "all",
    force: Annotated[
        bool, typer.Option("--force", help="Force removal without confirmation")
    ] = False,
) -> None:
    """Unregister a library of one type or of every type, after confirmation.

    Library files stay untouched. Exits with status 1 when no such library
    exists or the configuration cannot be saved.
    """
    console = get_console()
    config = Config()
    any_type = library_type == "all"
    matches = [
        library
        for library in config.get_libraries(None if any_type else library_type)
        if library["name"] == library_name
    ]
    if not matches:
        described = "library" if any_type else f"{library_type} library"
        console.print(f"No {described} named '{library_name}' found.", markup=False)
        console.print(LIST_HINT)
        raise typer.Exit(1)

    current = config.get_current_library()
    if not force and not _confirm_removal(console, matches, current):
        console.print("Operation cancelled.")
        return

    try:
        config.remove_library(library_name, None if any_type else library_type)
    except OSError as e:
        console.print(f"[red]Error removing library: {escape(str(e))}[/red]")
        raise typer.Exit(1) from e
    if len(matches) == 1:
        console.print(
            f"Removed library '{library_name}' from configuration.", markup=False
        )
    else:
        console.print(
            f"Removed {len(matches)} instances of library '{library_name}'"
            " from configuration.",
            markup=False,
        )
    if current is not None and config.get_current_library() != current:
        console.print(
            "Note: The removed library was the default; no default is set now."
        )


def _confirm_removal(
    console: Console, libraries: list[LibraryDict], current: str | None
) -> bool:
    """Describe the libraries about to be removed and ask whether to continue."""
    for library in libraries:
        console.print(
            f"Will remove {library['type']} library '{library['name']}'"
            " from configuration.",
            markup=False,
        )
        console.print(f"Path: {library['path']}", markup=False)
        if library["path"] == current:
            console.print("Warning: This is the current default library.")
    return typer.confirm("Continue?")
