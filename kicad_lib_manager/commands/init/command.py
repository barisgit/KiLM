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

from ...config import Config
from ...utils.metadata import (
    GITHUB_METADATA_FILE,
    generate_env_var_name,
    get_default_github_metadata,
    read_github_metadata,
    write_github_metadata,
)

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
    
    console.print(Panel(
        f"[bold blue]Initializing KiCad library[/bold blue]\n"
        f"[cyan]Location:[/cyan] {current_dir}",
        title="KiLM Library Initialization",
        border_style="blue"
    ))

    # Check for existing metadata
    metadata = read_github_metadata(current_dir)

    if metadata and not force:
        console.print(f"[green]Found existing metadata file[/green] ([cyan]{GITHUB_METADATA_FILE}[/cyan])")
        library_name = metadata.get("name")
        library_description = metadata.get("description")
        library_env_var = metadata.get("env_var")
        console.print(f"[blue]Using existing name:[/blue] {library_name}")

        # Show environment variable if present
        if library_env_var and not no_env_var:
            console.print(f"[blue]Using existing environment variable:[/blue] {library_env_var}")

        # Override with command line parameters if provided
        if name:
            library_name = name
            console.print(f"[yellow]Overriding with provided name:[/yellow] {library_name}")

        if description:
            library_description = description
            console.print(f"[yellow]Overriding with provided description:[/yellow] {library_description}")

        if env_var:
            library_env_var = env_var
            console.print(f"[yellow]Overriding with provided environment variable:[/yellow] {library_env_var}")
        elif no_env_var:
            library_env_var = None
            console.print("[yellow]Disabling environment variable as requested[/yellow]")

        # Update metadata if command line parameters were provided
        if name or description or env_var or no_env_var:
            if library_name is not None:
                metadata["name"] = library_name
            if library_description is not None:
                metadata["description"] = library_description
            if library_env_var and not no_env_var:
                metadata["env_var"] = library_env_var
            else:
                # Don't set env_var if not needed
                pass
            metadata["updated_with"] = "kilm"
            write_github_metadata(current_dir, metadata)
            console.print("[green]Updated metadata file with new information.[/green]")
    else:
        # Create a new metadata file
        if metadata and force:
            console.print(f"[yellow]Overwriting existing metadata file[/yellow] ([cyan]{GITHUB_METADATA_FILE}[/cyan])")
        else:
            console.print(f"[green]Creating new metadata file[/green] ([cyan]{GITHUB_METADATA_FILE}[/cyan])")

        # Generate metadata
        metadata = get_default_github_metadata(current_dir)

        # Override with command line parameters if provided
        if name:
            metadata["name"] = name
            # If name is provided but env_var isn't, regenerate the env_var based on the new name
            if not env_var and not no_env_var:
                metadata["env_var"] = generate_env_var_name(name, "KICAD_LIB")

        if description:
            metadata["description"] = description

        if env_var:
            metadata["env_var"] = env_var
        elif no_env_var:
            metadata["env_var"] = None

        # Write metadata file
        write_github_metadata(current_dir, metadata)
        console.print("[green]Metadata file created.[/green]")

        library_name = metadata["name"]
        library_env_var = metadata.get("env_var")

    # Create library directory structure if folders don't exist
    required_folders = ["symbols", "footprints", "templates"]
    existing_folders = []
    created_folders = []

    for folder in required_folders:
        folder_path = current_dir / folder
        if folder_path.exists():
            existing_folders.append(folder)
        else:
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
                created_folders.append(folder)
            except Exception as e:
                console.print(f"[red]Error creating {folder} directory: {e}[/red]")
                raise typer.Exit(1)

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
            console.print("[green]Created library_descriptions.yaml template file.[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not create library_descriptions.yaml file: {e}[/yellow]")

    # Update the metadata with current capabilities
    updated_capabilities = {
        "symbols": (current_dir / "symbols").exists(),
        "footprints": (current_dir / "footprints").exists(),
        "templates": (current_dir / "templates").exists(),
    }
    metadata["capabilities"] = updated_capabilities
    write_github_metadata(current_dir, metadata)

    # Report on folder status
    if existing_folders:
        console.print(f"[blue]Found existing folders:[/blue] {', '.join(existing_folders)}")
    if created_folders:
        console.print(f"[green]Created new folders:[/green] {', '.join(created_folders)}")

    # Verify if this looks like a KiCad library
    if not created_folders and not existing_folders:
        console.print("[yellow]Warning: No library folders were found or created.[/yellow]")
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
        success_content += f"[cyan]Type:[/cyan] GitHub library (symbols, footprints, templates)\n"
        success_content += f"[cyan]Path:[/cyan] {current_dir}\n"

        if library_env_var:
            success_content += f"[cyan]Environment Variable:[/cyan] {library_env_var}\n"

        if set_current:
            success_content += f"\n[yellow]This is now your current active library.[/yellow]\n"
            success_content += f"[dim]KiLM will use this library for all commands by default.[/dim]"

        console.print(Panel(
            success_content,
            title="✅ Initialization Complete",
            border_style="green"
        ))

        # Add a hint for adding 3D models
        console.print("\n[bold]Next Steps:[/bold]")
        console.print("To add a 3D models directory (typically stored in the cloud), use:")
        console.print("[dim]  kilm add-3d --name my-3d-models --directory /path/to/3d/models[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error initializing library: {e}[/red]")
        raise typer.Exit(1)
