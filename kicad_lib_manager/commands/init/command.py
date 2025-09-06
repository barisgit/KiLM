"""
Init command implementation for KiCad Library Manager (Typer version).
Initializes the current directory as a KiCad library directory (symbols, footprints, templates).
"""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from ...services.config_service import Config
from ...services.library_service import LibraryService

console = Console()


def init(
    name: Annotated[
        Optional[str],
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
        Optional[str],
        typer.Option(
            "--description",
            help="Description for this library collection",
        ),
    ] = None,
    env_var: Annotated[
        Optional[str],
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
    """
    Initialize the current directory as a KiCad library collection.

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

    console.print(
        Panel(
            f"[bold blue]Initializing KiCad library[/bold blue]\n"
            f"[cyan]Location:[/cyan] {current_dir}",
            title="KiLM Library Initialization",
            border_style="blue",
        )
    )

    # Use library service to initialize
    library_service = LibraryService()
    try:
        metadata = library_service.initialize_library(
            directory=current_dir,
            name=name,
            description=description,
            env_var=env_var,
            force=force,
            no_env_var=no_env_var,
        )

        library_name = metadata.get("name")
        library_env_var = metadata.get("env_var")

        # Get the directory status
        existing_folders = []
        created_folders = []
        capabilities = metadata.get("capabilities", {})

        for folder_type, exists in capabilities.items():
            if exists:
                folder_path = current_dir / folder_type
                if folder_path.exists():
                    existing_folders.append(folder_type)
                else:
                    created_folders.append(folder_type)

    except Exception as e:
        console.print(f"[red]Error initializing library: {e}[/red]")
        raise typer.Exit(1) from e

    # Create empty library_descriptions.yaml if it doesn't exist
    library_descriptions_file = current_dir / "library_descriptions.yaml"
    if not library_descriptions_file.exists():
        try:
            # Create a template with comments and examples
            template_content = """# Library Descriptions for KiCad
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
            with library_descriptions_file.open("w", encoding="utf-8") as f:
                f.write(template_content)
            console.print(
                "[green]Created library_descriptions.yaml template file.[/green]"
            )
        except Exception as e:
            console.print(
                f"[yellow]Warning: Could not create library_descriptions.yaml file: {e}[/yellow]"
            )

    # Metadata is already updated by the service

    # Report on folder status
    if existing_folders:
        console.print(
            f"[blue]Found existing folders:[/blue] {', '.join(existing_folders)}"
        )
    if created_folders:
        console.print(
            f"[green]Created new folders:[/green] {', '.join(created_folders)}"
        )

    # Verify if this looks like a KiCad library
    if not created_folders and not existing_folders:
        console.print(
            "[yellow]Warning: No library folders were found or created.[/yellow]"
        )
        if not Confirm.ask("Continue anyway?", default=True):
            console.print("[yellow]Initialization cancelled.[/yellow]")
            raise typer.Exit(0)

    # Update the configuration
    try:
        config = Config()
        # Record as a GitHub library (symbols + footprints)
        safe_library_name = str(library_name or current_dir.name)
        config.add_library(safe_library_name, str(current_dir), "github")

        if set_current:
            config.set_current_library(str(current_dir))

        # Create success panel
        success_content = f"[bold green]Library '{safe_library_name}' initialized successfully![/bold green]\n\n"
        success_content += (
            "[cyan]Type:[/cyan] GitHub library (symbols, footprints, templates)\n"
        )
        success_content += f"[cyan]Path:[/cyan] {current_dir}\n"

        if library_env_var:
            success_content += f"[cyan]Environment Variable:[/cyan] {library_env_var}\n"

        if set_current:
            success_content += (
                "\n[yellow]This is now your current active library.[/yellow]\n"
            )
            success_content += (
                "[dim]KiLM will use this library for all commands by default.[/dim]"
            )

        console.print(
            Panel(
                success_content,
                title="✅ Initialization Complete",
                border_style="green",
            )
        )

        # Add a hint for adding 3D models
        console.print("\n[bold]Next Steps:[/bold]")
        console.print(
            "To add a 3D models directory (typically stored in the cloud), use:"
        )
        console.print(
            "[dim]  kilm add-3d --name my-3d-models --directory /path/to/3d/models[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error initializing library: {e}[/red]")
        raise typer.Exit(1) from e
