"""Where ``kilm setup`` finds the libraries it configures.

The command line comes first, then the KiLM configuration, then environment
variables.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import typer
from rich.table import Table

from kicad_lib_manager.commands.shared import given
from kicad_lib_manager.services.config_service import Config, LibraryDict
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import MODELS_DIR_VAR, SYMBOL_DIR_VAR
from kicad_lib_manager.utils.env_vars import find_environment_variables
from kicad_lib_manager.utils.metadata import read_cloud_metadata, read_github_metadata


@dataclass
class LibrarySources:
    """The main library directories setup configures and where each came from.

    Attributes:
        symbol_dir: The main symbol library directory, once known.
        models_dir: The main 3D model directory, once known.
        from_command_line: Directories given as options, by library type.
        from_config: Each selected configured library's environment variable
            and path; setup writes these variables to KiCad too.
        from_environment: Directories found in environment variables.
    """

    symbol_dir: str | None
    models_dir: str | None
    from_command_line: dict[str, str] = field(default_factory=dict)
    from_config: dict[str, str] = field(default_factory=dict)
    from_environment: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class LibrarySelection:
    """Which configured libraries setup uses.

    Attributes:
        all_libraries: Use every configured library.
        symbol_names: Symbol libraries requested by name, or None for the
            current one.
        model_names: 3D model libraries requested by name, or None for the
            current one.
    """

    all_libraries: bool
    symbol_names: list[str] | None
    model_names: list[str] | None


@dataclass(frozen=True)
class _Kind:
    """How setup shows one type of configured library."""

    title: str
    read_metadata: Callable[[Path], Mapping[str, object] | None]


_SYMBOLS = _Kind("Setting up symbol libraries", read_github_metadata)
_MODELS = _Kind("Setting up 3D model libraries", read_cloud_metadata)


def command_line_sources(
    symbol_dir: str | None, models_dir: str | None, *, verbose: bool
) -> LibrarySources:
    """Start the sources from the directories given on the command line."""
    console = get_console()
    sources = LibrarySources(given(symbol_dir), given(models_dir))
    if sources.symbol_dir is not None:
        sources.from_command_line["symbols"] = sources.symbol_dir
        if verbose:
            console.print(
                "Symbol library specified on command line: "
                f"[blue]{sources.symbol_dir}[/blue]"
            )
    if sources.models_dir is not None:
        sources.from_command_line["3d"] = sources.models_dir
        if verbose:
            console.print(
                "3D model library specified on command line: "
                f"[blue]{sources.models_dir}[/blue]"
            )
    return sources


def requested_names(
    option: str | None, kind: str, *, verbose: bool
) -> list[str] | None:
    """Split a comma-separated library name option; None when not given."""
    value = given(option)
    if value is None:
        return None
    names = [name.strip() for name in value.split(",")]
    if verbose:
        get_console().print(f"Requested {kind}: {names}")
    return names


def add_config_libraries(
    sources: LibrarySources, selection: LibrarySelection, *, verbose: bool
) -> None:
    """Add the selected configured libraries to ``sources`` and show them.

    The first selected symbol and 3D model library become the main
    directories unless the command line already set them.

    Raises:
        OSError: The configuration directory cannot be created or read.
    """
    console = get_console()
    config = Config()
    if verbose:
        config_file = config.config_file
        console.print(f"Looking for configuration in: {config_file}")
        exists = "exists" if config_file.exists() else "does not exist"
        console.print(f"Configuration file {exists}")

    symbol_libraries = config.get_libraries("github")
    model_libraries = config.get_libraries("cloud")
    if verbose:
        console.print(
            f"Found {len(symbol_libraries)} symbol libraries and "
            f"{len(model_libraries)} 3D model libraries in config"
        )

    if selection.all_libraries:
        symbols, models = symbol_libraries, model_libraries
    else:
        current_symbols = config.get_symbol_library_path()
        current_models = config.get_3d_library_path()
        symbols = _select(
            symbol_libraries,
            selection.symbol_names,
            None if sources.symbol_dir is not None else current_symbols,
        )
        models = _select(
            model_libraries,
            selection.model_names,
            None if sources.models_dir is not None else current_models,
        )

    if symbols:
        main_var = SYMBOL_DIR_VAR if sources.symbol_dir is None else None
        _show_libraries(_SYMBOLS, symbols, sources, main_var=main_var, verbose=verbose)
        if sources.symbol_dir is None:
            sources.symbol_dir = given(symbols[0].get("path", "unknown"))
    if models:
        _show_libraries(_MODELS, models, sources, main_var=None, verbose=verbose)
        if sources.models_dir is None:
            sources.models_dir = given(models[0].get("path", "unknown"))


def _select(
    libraries: list[LibraryDict], names: list[str] | None, current_path: str | None
) -> list[LibraryDict]:
    """Return the libraries named in ``names``, else the current library."""
    if names is not None:
        found = (_find(libraries, "name", name) for name in names)
        return [library for library in found if library is not None]
    current = given(current_path)
    if current is None:
        return []
    library = _find(libraries, "path", current)
    return [] if library is None else [library]


def _find(
    libraries: list[LibraryDict], key: Literal["name", "path"], value: str
) -> LibraryDict | None:
    """Return the first library whose ``key`` is ``value``."""
    return next((library for library in libraries if library.get(key) == value), None)


def _show_libraries(
    kind: _Kind,
    libraries: list[LibraryDict],
    sources: LibrarySources,
    *,
    main_var: str | None,
    verbose: bool,
) -> None:
    """Show ``libraries`` and record their environment variables.

    When ``main_var`` is set, the first library also provides it unless a
    library's own variable already did.
    """
    table = Table(
        title=f"[bold cyan]{kind.title}[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Library", style="cyan", no_wrap=True)
    table.add_column("Path", style="blue")
    table.add_column("Environment Variable", style="green")
    for index, library in enumerate(libraries):
        path = library.get("path", "unknown")
        env_var, shown = _environment_variable(kind, path, verbose=verbose)
        if env_var is not None:
            sources.from_config[env_var] = path
        if index == 0 and main_var is not None:
            sources.from_config.setdefault(main_var, path)
        table.add_row(f"[bold]{library.get('name', 'unnamed')}[/bold]", path, shown)
    console = get_console()
    console.print()
    console.print(table)


def _environment_variable(
    kind: _Kind, path: str, *, verbose: bool
) -> tuple[str | None, str]:
    """Return a library's environment variable, if any, and how to show it."""
    try:
        metadata = kind.read_metadata(Path(path))
    except OSError as e:
        return None, (f"[red]Error: {e}[/red]" if verbose else "[red]Error[/red]")
    if metadata is None or "env_var" not in metadata:
        return None, "[yellow]No metadata[/yellow]"
    env_var = metadata["env_var"]
    if isinstance(env_var, str) and env_var:
        return env_var, f"[green]{env_var}[/green]"
    return None, "[yellow]Not configured[/yellow]"


def fall_back_to_environment(sources: LibrarySources) -> str:
    """Fill missing main directories from environment variables.

    Returns:
        The main symbol library directory.

    Raises:
        typer.Exit: No symbol library directory is known.
    """
    console = get_console()
    symbol_dir = sources.symbol_dir
    if symbol_dir is None:
        symbol_dir = given(find_environment_variables(SYMBOL_DIR_VAR))
        if symbol_dir is None:
            console.print("[red]Error: KICAD_USER_LIB not set and not provided[/red]")
            console.print(
                "[yellow]Consider initializing a library with 'kilm init' "
                "first.[/yellow]"
            )
            raise typer.Exit(1)
        sources.symbol_dir = symbol_dir
        sources.from_environment[SYMBOL_DIR_VAR] = symbol_dir
        console.print(
            "[green]Using KiCad library from environment variable:[/green] "
            f"[blue]{symbol_dir}[/blue]"
        )

    if sources.models_dir is None:
        models_dir = given(find_environment_variables(MODELS_DIR_VAR))
        if models_dir is None:
            console.print(
                "[yellow]Warning: KICAD_3D_LIB not set, 3D models might not work "
                "correctly[/yellow]"
            )
            console.print(
                "[yellow]Consider adding a 3D model directory with "
                "'kilm add-3d'[/yellow]"
            )
        else:
            sources.models_dir = models_dir
            sources.from_environment[MODELS_DIR_VAR] = models_dir
            console.print(
                "[green]Using 3D model library from environment variable:[/green] "
                f"[blue]{models_dir}[/blue]"
            )
    return symbol_dir


def print_source_summary(sources: LibrarySources) -> None:
    """Print where each library directory came from."""
    console = get_console()
    console.print("\nSummary of library sources:")
    for heading, paths in (
        ("From command line", sources.from_command_line),
        ("From config file", sources.from_config),
        ("From environment variables", sources.from_environment),
    ):
        if paths:
            console.print(f"  {heading}:")
            for library_type, path in paths.items():
                console.print(f"    - {library_type}: {path}")
