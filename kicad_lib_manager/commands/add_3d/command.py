"""
Add cloud-based 3D models directory command for KiCad Library Manager (Typer version).
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from ...services.config_service import Config
from ...utils.metadata import (
    CLOUD_METADATA_FILE,
    generate_env_var_name,
    get_default_cloud_metadata,
    read_cloud_metadata,
    write_cloud_metadata,
)

console = Console()


def add_3d(
    name: Annotated[
        Optional[str],
        typer.Option(
            help="Name for this 3D models collection (automatic if not provided)"
        ),
    ] = None,
    directory: Annotated[
        Optional[Path],
        typer.Option(
            help="Directory containing 3D models (default: current directory)",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = None,
    description: Annotated[
        Optional[str], typer.Option(help="Description for this 3D models collection")
    ] = None,
    env_var: Annotated[
        Optional[str],
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
    # Use current directory if not specified
    directory = Path.cwd().resolve() if directory is None else directory.resolve()

    console.print(
        f"[bold cyan]Adding cloud-based 3D models directory:[/bold cyan] {directory}"
    )

    # Check for existing metadata
    metadata = read_cloud_metadata(directory)

    if metadata and not force:
        console.print(
            f"[green]Found existing metadata file[/green] ({CLOUD_METADATA_FILE})"
        )
        library_name = metadata.get("name")
        library_description = metadata.get("description")
        library_env_var = metadata.get("env_var")
        console.print(f"Using existing name: [blue]{library_name}[/blue]")

        # Show environment variable if present
        if library_env_var and not no_env_var:
            console.print(
                f"Using existing environment variable: [yellow]{library_env_var}[/yellow]"
            )

        # Override with command line parameters if provided
        if name:
            library_name = name
            console.print(f"Overriding with provided name: [blue]{library_name}[/blue]")

        if description:
            library_description = description
            console.print(
                f"Overriding with provided description: [blue]{library_description}[/blue]"
            )

        if env_var:
            library_env_var = env_var
            console.print(
                f"Overriding with provided environment variable: [yellow]{library_env_var}[/yellow]"
            )
        elif no_env_var:
            library_env_var = None
            console.print(
                "[yellow]Disabling environment variable as requested[/yellow]"
            )

        # Update metadata if command line parameters were provided
        if name or description or env_var or no_env_var:
            metadata["name"] = library_name
            metadata["description"] = library_description
            if library_env_var and not no_env_var:
                metadata["env_var"] = library_env_var
            else:
                metadata["env_var"] = None
            metadata["updated_with"] = "kilm"
            write_cloud_metadata(directory, metadata)
            console.print("[green]Updated metadata file with new information[/green]")
    else:
        # Create a new metadata file
        if metadata and force:
            console.print(
                f"[yellow]Overwriting existing metadata file[/yellow] ({CLOUD_METADATA_FILE})"
            )
        else:
            console.print(
                f"[green]Creating new metadata file[/green] ({CLOUD_METADATA_FILE})"
            )

        # Generate metadata
        metadata = get_default_cloud_metadata(directory)

        # Override with command line parameters if provided
        if name:
            metadata["name"] = name
            # If name is provided but env_var isn't, regenerate the env_var based on the new name
            if not env_var and not no_env_var:
                metadata["env_var"] = generate_env_var_name(name, "KICAD_3D")

        if description:
            metadata["description"] = description

        if env_var:
            metadata["env_var"] = env_var
        elif no_env_var:
            metadata["env_var"] = None

        # Write metadata file
        write_cloud_metadata(directory, metadata)
        console.print("[green]Metadata file created[/green]")

        library_name = metadata["name"]
        library_env_var = metadata.get("env_var")

    # Verify if this looks like a 3D model directory
    model_extensions = [".step", ".stp", ".wrl", ".wings"]
    found_models = False

    # Do a quick check for model files
    for ext in model_extensions:
        if list(directory.glob(f"**/*{ext}")):
            found_models = True
            break

    if not found_models:
        console.print(
            "[yellow]Warning: No 3D model files found in this directory[/yellow]"
        )
        if not typer.confirm("Continue anyway?", default=True):
            console.print("[red]Operation cancelled[/red]")
            raise typer.Exit(0)

    # Update metadata with actual model count
    model_count = 0
    for ext in model_extensions:
        model_count += len(list(directory.glob(f"**/*{ext}")))

    metadata["model_count"] = model_count
    write_cloud_metadata(directory, metadata)

    # Update the configuration
    try:
        config = Config()
        # Add as a cloud-based 3D model library
        if library_name is None:
            library_name = metadata.get("name", directory.name)

        # Ensure library_name is a string
        final_library_name = (
            str(library_name) if library_name is not None else directory.name
        )
        config.add_library(final_library_name, str(directory), "cloud")

        console.print(
            f"[bold green]3D models directory '{final_library_name}' added successfully![/bold green]"
        )
        console.print(f"[blue]Path:[/blue] {directory}")
        if model_count > 0:
            console.print(f"[green]Found {model_count} 3D model files[/green]")

        if library_env_var:
            console.print(
                f"[yellow]Assigned environment variable:[/yellow] {library_env_var}"
            )
            console.print("\n[bold]You can use this directory with:[/bold]")
            console.print(
                f"  [cyan]kilm setup --threed-lib-dirs '{library_name}'[/cyan]"
            )
            console.print("  [dim]# or by setting the environment variable[/dim]")
            console.print(f"  [cyan]export {library_env_var}='{directory}'[/cyan]")

        # Show current cloud libraries
        libraries = config.get_libraries("cloud")
        if len(libraries) > 1:
            console.print(
                "\n[bold]All registered cloud-based 3D model directories:[/bold]"
            )
            for lib in libraries:
                lib_name = lib.get("name", "unnamed")
                lib_path = lib.get("path", "unknown")
                lib_env_var = None

                # Try to get the environment variable from metadata
                try:
                    lib_metadata = read_cloud_metadata(Path(lib_path))
                    if lib_metadata and "env_var" in lib_metadata:
                        lib_env_var = lib_metadata["env_var"]
                except Exception:
                    pass

                if lib_env_var:
                    console.print(
                        f"  - [cyan]{lib_name}[/cyan]: {lib_path} [yellow](ENV: {lib_env_var})[/yellow]"
                    )
                else:
                    console.print(f"  - [cyan]{lib_name}[/cyan]: {lib_path}")
    except Exception as e:
        console.print(f"[red]Error adding 3D models directory: {e}[/red]")
        raise typer.Exit(1) from e
