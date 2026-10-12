"""The ``add-3d`` command: register a directory of 3D models with KiLM.

The directory's settings live in a cloud metadata file inside it, so the same
name and environment variable apply on every machine that syncs the folder.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from kicad_lib_manager.commands.shared import given
from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.metadata import (
    CLOUD_METADATA_FILE,
    CloudMetadata,
    generate_env_var_name,
    get_default_cloud_metadata,
    read_cloud_metadata,
    write_cloud_metadata,
)

MODEL_EXTENSIONS = (".step", ".stp", ".wrl", ".wings")


@dataclass(frozen=True)
class _Overrides:
    """Metadata values given on the command line; None means not given."""

    name: str | None
    description: str | None
    env_var: str | None
    no_env_var: bool

    def given(self) -> bool:
        """Return whether any value was given."""
        return (
            self.name is not None
            or self.description is not None
            or self.env_var is not None
            or self.no_env_var
        )


def _present(value: str | int | None) -> bool:
    """Return whether a metadata value is set to something non-empty."""
    return value is not None and bool(value)


def _update_existing(
    directory: Path, metadata: CloudMetadata, overrides: _Overrides
) -> CloudMetadata:
    """Apply ``overrides`` to the directory's metadata and save any change."""
    console = get_console()
    console.print(
        f"[green]Found existing metadata file[/green] ({CLOUD_METADATA_FILE})"
    )
    name = metadata.get("name")
    description = metadata.get("description")
    env_var = metadata.get("env_var")
    console.print(f"Using existing name: [blue]{name}[/blue]")
    if _present(env_var) and not overrides.no_env_var:
        console.print(
            f"Using existing environment variable: [yellow]{env_var}[/yellow]"
        )

    if overrides.name is not None:
        name = overrides.name
        console.print(f"Overriding with provided name: [blue]{name}[/blue]")
    if overrides.description is not None:
        description = overrides.description
        console.print(
            f"Overriding with provided description: [blue]{description}[/blue]"
        )
    if overrides.env_var is not None:
        env_var = overrides.env_var
        console.print(
            f"Overriding with provided environment variable: [yellow]{env_var}[/yellow]"
        )
    elif overrides.no_env_var:
        console.print("[yellow]Disabling environment variable as requested[/yellow]")

    if overrides.given():
        if name is not None:
            metadata["name"] = name
        if description is not None:
            metadata["description"] = description
        metadata["env_var"] = (
            env_var if _present(env_var) and not overrides.no_env_var else None
        )
        metadata["updated_with"] = "kilm"
        write_cloud_metadata(directory, metadata)
        console.print("[green]Updated metadata file with new information[/green]")
    return metadata


def _create_new(
    directory: Path, overrides: _Overrides, *, overwriting: bool
) -> CloudMetadata:
    """Write fresh metadata for the directory, applying ``overrides``."""
    console = get_console()
    if overwriting:
        console.print(
            "[yellow]Overwriting existing metadata file[/yellow] "
            f"({CLOUD_METADATA_FILE})"
        )
    else:
        console.print(
            f"[green]Creating new metadata file[/green] ({CLOUD_METADATA_FILE})"
        )

    metadata = get_default_cloud_metadata(directory)
    if overrides.name is not None:
        metadata["name"] = overrides.name
        # A new name implies a matching variable unless one is given or refused.
        if overrides.env_var is None and not overrides.no_env_var:
            metadata["env_var"] = generate_env_var_name(overrides.name, "KICAD_3D")
    if overrides.description is not None:
        metadata["description"] = overrides.description
    if overrides.env_var is not None:
        metadata["env_var"] = overrides.env_var
    elif overrides.no_env_var:
        metadata["env_var"] = None

    write_cloud_metadata(directory, metadata)
    console.print("[green]Metadata file created[/green]")
    return metadata


def _count_models(directory: Path) -> int:
    """Return the number of 3D model files below ``directory``."""
    return sum(
        len(list(directory.glob(f"**/*{extension}"))) for extension in MODEL_EXTENSIONS
    )


def _confirm_models(model_count: int) -> None:
    """Ask before registering a directory without models; exit on refusal."""
    if model_count > 0:
        return
    console = get_console()
    console.print("[yellow]Warning: No 3D model files found in this directory[/yellow]")
    if not typer.confirm("Continue anyway?", default=True):
        console.print("[red]Operation cancelled[/red]")
        raise typer.Exit(0)


def _print_usage(name: str, directory: Path, env_var: str | int | None) -> None:
    """Explain how to use the library through its environment variable."""
    if not _present(env_var):
        return
    console = get_console()
    console.print(f"[yellow]Assigned environment variable:[/yellow] {env_var}")
    console.print("\n[bold]You can use this directory with:[/bold]")
    console.print(f"  [cyan]kilm setup --threed-lib-dirs '{name}'[/cyan]")
    console.print("  [dim]# or by setting the environment variable[/dim]")
    console.print(f"  [cyan]export {env_var}='{directory}'[/cyan]")


def _print_cloud_libraries(config: Config) -> None:
    """List every registered 3D model directory when there is more than one."""
    libraries = config.get_libraries("cloud")
    if len(libraries) <= 1:
        return
    console = get_console()
    console.print("\n[bold]All registered cloud-based 3D model directories:[/bold]")
    for library in libraries:
        name = library.get("name", "unnamed")
        path = library.get("path", "unknown")
        metadata = read_cloud_metadata(Path(path))
        env_var = None if metadata is None else metadata.get("env_var")
        if not _present(env_var):
            console.print(f"  - [cyan]{name}[/cyan]: {path}")
        else:
            console.print(
                f"  - [cyan]{name}[/cyan]: {path} [yellow](ENV: {env_var})[/yellow]"
            )


def add_3d(  # noqa: PLR0913 -- each CLI option is a Typer parameter
    *,
    name: Annotated[
        str | None,
        typer.Option(
            help="Name for this 3D models collection (automatic if not provided)"
        ),
    ] = None,
    directory: Annotated[
        Path | None,
        typer.Option(
            help="Directory containing 3D models (default: current directory)",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    description: Annotated[
        str | None, typer.Option(help="Description for this 3D models collection")
    ] = None,
    env_var: Annotated[
        str | None,
        typer.Option(
            "--env-var",
            help="Custom environment variable name for this 3D model library",
        ),
    ] = None,
    force: Annotated[
        bool, typer.Option(help="Overwrite existing metadata file if present")
    ] = False,
    no_env_var: Annotated[
        bool,
        typer.Option(
            "--no-env-var", help="Don't assign an environment variable to this library"
        ),
    ] = False,
) -> None:
    """Add a cloud-based 3D models directory to the configuration.

    This command registers a directory containing 3D models that are typically
    stored in cloud storage (Dropbox, Google Drive, etc.) rather than in GitHub.

    Each 3D model library gets its own unique environment variable name, which
    will be used when setting up KiCad. This allows you to have multiple 3D model
    libraries and reference them individually.

    If a metadata file (.kilm_metadata) already exists, information from it will be
    used unless overridden by command line options.

    If no directory is specified, the current directory will be used.
    """
    directory = Path.cwd().resolve() if directory is None else directory.resolve()
    console = get_console()
    console.print(
        f"[bold cyan]Adding cloud-based 3D models directory:[/bold cyan] {directory}"
    )

    overrides = _Overrides(
        name=given(name),
        description=given(description),
        env_var=given(env_var),
        no_env_var=no_env_var,
    )
    existing = read_cloud_metadata(directory)
    has_existing = existing is not None and len(existing) > 0
    if existing is not None and has_existing and not force:
        metadata = _update_existing(directory, existing, overrides)
    else:
        metadata = _create_new(directory, overrides, overwriting=has_existing)

    model_count = _count_models(directory)
    _confirm_models(model_count)
    metadata["model_count"] = model_count
    write_cloud_metadata(directory, metadata)

    raw_name = metadata.get("name")
    library_name = directory.name if raw_name is None else str(raw_name)
    try:
        config = Config()
        config.add_library(library_name, str(directory), "cloud")
        console.print(
            f"[bold green]3D models directory '{library_name}' added "
            "successfully![/bold green]"
        )
        console.print(f"[blue]Path:[/blue] {directory}")
        if model_count > 0:
            console.print(f"[green]Found {model_count} 3D model files[/green]")
        _print_usage(library_name, directory, metadata.get("env_var"))
        _print_cloud_libraries(config)
    except Exception as e:
        console.print(f"[red]Error adding 3D models directory: {e}[/red]")
        raise typer.Exit(1) from e
