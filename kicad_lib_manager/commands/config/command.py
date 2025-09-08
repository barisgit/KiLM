"""
Configuration commands implementation for KiCad Library Manager.
Provides commands for managing KiCad Library Manager configuration.
"""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...services.config_service import Config
from ...utils.metadata import (
    CLOUD_METADATA_FILE,
    GITHUB_METADATA_FILE,
    read_cloud_metadata,
    read_github_metadata,
)

console = Console()


def list_config(
    library_type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Type of libraries to list (github=symbols/footprints, cloud=3D models)",
        ),
    ] = "all",
    verbose: Annotated[
        bool,
        typer.Option("-v", "--verbose", help="Show more information about libraries"),
    ] = False,
) -> None:
    """List all configured libraries in kilm.

    This shows all libraries stored in the kilm configuration file.
    There are two types of libraries:

    1. GitHub libraries - containing symbols and footprints (type: github)
    2. Cloud libraries - containing 3D models (type: cloud)

    Use --verbose to see metadata information stored in the library directories.
    """
    try:
        config = Config()

        # Get libraries of specified type
        if library_type == "all":
            libraries = config.get_libraries()
        else:
            libraries = config.get_libraries(library_type)

        # Get current library
        current_library = config.get_current_library()

        if not libraries:
            console.print()
            console.print(
                Panel(
                    "[yellow]No libraries configured.[/yellow]\n\n"
                    "[cyan]Get Started:[/cyan]\n"
                    "• Initialize GitHub library: [blue]kilm init[/blue]\n"
                    "• Add 3D model library: [blue]kilm add-3d[/blue]\n"
                    "• Check status: [blue]kilm status[/blue]",
                    title="[bold yellow]⚠️ No Libraries[/bold yellow]",
                    border_style="yellow",
                )
            )
            return

        # Group libraries by type
        types = {"github": [], "cloud": []}
        for lib in libraries:
            lib_type = lib.get("type", "unknown")
            if lib_type in types:
                types[lib_type].append(lib)

        console.print()

        # Display GitHub Libraries
        if library_type in ["all", "github"] and types["github"]:
            console.print(
                "\n[bold cyan]GitHub Libraries[/bold cyan] [dim](symbols, footprints, templates)[/dim]"
            )
            console.print()

            if verbose:
                # Verbose mode: Individual panels for each library
                for lib in types["github"]:
                    name = lib.get("name", "unnamed")
                    path = lib.get("path", "unknown")
                    path_obj = Path(path)

                    # Get metadata
                    metadata = read_github_metadata(path_obj)

                    # Build content
                    content = f"[blue]Path:[/blue] {path}\n"

                    if metadata:
                        if "description" in metadata:
                            content += f"[green]Description:[/green] {metadata['description']}\n"
                        if "version" in metadata:
                            content += (
                                f"[yellow]Version:[/yellow] {metadata['version']}\n"
                            )
                        if "env_var" in metadata and metadata["env_var"]:
                            content += f"[magenta]Environment Variable:[/magenta] {metadata['env_var']}\n"

                        # Capabilities with clear labels
                        if "capabilities" in metadata:
                            caps = metadata["capabilities"]
                            if isinstance(caps, dict):
                                content += "[white]Features:[/white] "
                                features = []
                                if caps.get("symbols"):
                                    features.append("[green]✓ Symbols[/green]")
                                else:
                                    features.append("[red]✗ Symbols[/red]")
                                if caps.get("footprints"):
                                    features.append("[green]✓ Footprints[/green]")
                                else:
                                    features.append("[red]✗ Footprints[/red]")
                                if caps.get("templates"):
                                    features.append("[green]✓ Templates[/green]")
                                else:
                                    features.append("[red]✗ Templates[/red]")
                                content += " | ".join(features)
                    else:
                        content += (
                            f"[dim]No {GITHUB_METADATA_FILE} metadata file found[/dim]"
                        )

                    # Status indicator
                    status = (
                        "[green]✓ CURRENT[/green]"
                        if path == current_library
                        else "[dim]Available[/dim]"
                    )
                    title = f"[bold cyan]{name}[/bold cyan] [{status}]"

                    console.print(
                        Panel(
                            content,
                            title=title,
                            border_style="cyan" if path == current_library else "dim",
                        )
                    )
                    console.print()
            else:
                # Compact mode: Simple table
                table = Table(
                    show_header=True, header_style="bold magenta", border_style="cyan"
                )

                table.add_column("Library", style="cyan", no_wrap=True)
                table.add_column("Status", justify="center", style="green", width=12)
                table.add_column("Path", style="blue")

                for lib in types["github"]:
                    name = lib.get("name", "unnamed")
                    path = lib.get("path", "unknown")

                    status = (
                        "[green]✓ Current[/green]"
                        if path == current_library
                        else "[dim]Available[/dim]"
                    )

                    table.add_row(f"[bold]{name}[/bold]", status, path)

                console.print(table)
                console.print()

        # Display Cloud Libraries
        if library_type in ["all", "cloud"] and types["cloud"]:
            console.print(
                "\n[bold cyan]Cloud Libraries[/bold cyan] [dim](3D models)[/dim]"
            )
            console.print()

            if verbose:
                # Verbose mode: Individual panels for each library
                for lib in types["cloud"]:
                    name = lib.get("name", "unnamed")
                    path = lib.get("path", "unknown")
                    path_obj = Path(path)

                    # Get metadata
                    metadata = read_cloud_metadata(path_obj)

                    # Build content
                    content = f"[blue]Path:[/blue] {path}\n"

                    if metadata:
                        if "description" in metadata:
                            content += f"[green]Description:[/green] {metadata['description']}\n"
                        if "version" in metadata:
                            content += (
                                f"[yellow]Version:[/yellow] {metadata['version']}\n"
                            )
                        if "env_var" in metadata and metadata["env_var"]:
                            content += f"[magenta]Environment Variable:[/magenta] {metadata['env_var']}\n"

                        # Model count
                        if "model_count" in metadata:
                            content += (
                                f"[white]3D Models:[/white] {metadata['model_count']}"
                            )
                        else:
                            # Count models
                            count = 0
                            for ext in [".step", ".stp", ".wrl", ".wings"]:
                                count += len(list(path_obj.glob(f"**/*{ext}")))
                            content += f"[white]3D Models:[/white] {count} [dim](counted)[/dim]"
                    else:
                        content += (
                            f"[dim]No {CLOUD_METADATA_FILE} metadata file found[/dim]"
                        )
                        # Still count models
                        count = 0
                        for ext in [".step", ".stp", ".wrl", ".wings"]:
                            count += len(list(path_obj.glob(f"**/*{ext}")))
                        content += (
                            f"\n[white]3D Models:[/white] {count} [dim](counted)[/dim]"
                        )

                    # Status indicator
                    status = (
                        "[green]✓ CURRENT[/green]"
                        if path == current_library
                        else "[dim]Available[/dim]"
                    )
                    title = f"[bold cyan]{name}[/bold cyan] [{status}]"

                    console.print(
                        Panel(
                            content,
                            title=title,
                            border_style="cyan" if path == current_library else "dim",
                        )
                    )
                    console.print()
            else:
                # Compact mode: Simple table
                table = Table(
                    show_header=True, header_style="bold magenta", border_style="cyan"
                )

                table.add_column("Library", style="cyan", no_wrap=True)
                table.add_column("Status", justify="center", style="green", width=12)
                table.add_column("Path", style="blue")

                for lib in types["cloud"]:
                    name = lib.get("name", "unnamed")
                    path = lib.get("path", "unknown")

                    status = (
                        "[green]✓ Current[/green]"
                        if path == current_library
                        else "[dim]Available[/dim]"
                    )

                    table.add_row(f"[bold]{name}[/bold]", status, path)

                console.print(table)
                console.print()

        # Add summary panel
        total_libs = len(libraries)
        github_count = len(types["github"])
        cloud_count = len(types["cloud"])

        summary_content = f"[green]Total Libraries:[/green] {total_libs}\n"
        summary_content += (
            f"[cyan]GitHub:[/cyan] {github_count}  [blue]Cloud:[/blue] {cloud_count}"
        )

        console.print(
            Panel(
                summary_content,
                title="[bold cyan]Summary[/bold cyan]",
                border_style="cyan",
                width=35,
            )
        )

        # Print helpful message if no libraries match the filter
        if library_type == "github" and not types["github"]:
            console.print(
                Panel(
                    "[yellow]No GitHub libraries configured.[/yellow]\n\n"
                    "[cyan]Get Started:[/cyan]\n"
                    "• Initialize a GitHub library: [blue]kilm init[/blue]",
                    title="[bold yellow]⚠️ No GitHub Libraries[/bold yellow]",
                    border_style="yellow",
                )
            )
        elif library_type == "cloud" and not types["cloud"]:
            console.print(
                Panel(
                    "[yellow]No cloud libraries configured.[/yellow]\n\n"
                    "[cyan]Get Started:[/cyan]\n"
                    "• Add a 3D model library: [blue]kilm add-3d[/blue]",
                    title="[bold yellow]⚠️ No Cloud Libraries[/bold yellow]",
                    border_style="yellow",
                )
            )

    except Exception as e:
        console.print(f"[red]Error listing configurations: {e}[/red]")
        sys.exit(1)


def set_default(
    library_name: Annotated[
        Optional[str], typer.Argument(help="Name of library to set as default")
    ] = None,
    library_type: Annotated[
        str,
        typer.Option(
            "--type",
            help="Type of library to set as default (github=symbols/footprints, cloud=3D models)",
        ),
    ] = "github",
) -> None:
    """Set a library as the default for operations.

    Sets the specified library as the default for future operations.
    The default library is used by commands when no specific library is specified.

    If LIBRARY_NAME is not provided, the command will prompt you to select
    from the available libraries of the specified type.

    Examples:

    \b
    # Set a GitHub library as default
    kilm config set-default my-library

    \b
    # Set a Cloud library as default
    kilm config set-default my-3d-library --type cloud

    \b
    # Interactively select a library to set as default
    kilm config set-default

    \b
    # Interactively select a Cloud library to set as default
    kilm config set-default --type cloud
    """
    try:
        config = Config()

        # Get libraries of specified type
        libraries = config.get_libraries(library_type)

        if not libraries:
            console.print(f"No {library_type} libraries configured.")
            if library_type == "github":
                console.print("Use 'kilm init' to initialize a GitHub library.")
            else:
                console.print(
                    "Use 'kilm add-3d' to add a cloud-based 3D model library."
                )
            sys.exit(1)

        # Get current library path
        current_library = config.get_current_library()

        # If library name not provided, prompt for selection
        if not library_name:
            console.print(f"\nAvailable {library_type} libraries:")

            # Show numbered list of libraries
            for i, lib in enumerate(libraries):
                name = lib.get("name", "unnamed")
                path = lib.get("path", "unknown")

                # Mark current library
                current_marker = ""
                if path == current_library:
                    current_marker = " (current)"

                console.print(f"{i + 1}. {name}{current_marker}")

            # Get selection
            while True:
                try:
                    selection = typer.prompt(
                        "Select library (number)", type=int, default=1
                    )
                    if 1 <= selection <= len(libraries):
                        selected_lib = libraries[selection - 1]
                        library_name = selected_lib.get("name")
                        library_path = selected_lib.get("path")
                        break
                    else:
                        console.print(
                            f"Please enter a number between 1 and {len(libraries)}"
                        )
                except ValueError:
                    console.print("Please enter a valid number")
        else:
            # Find the library by name
            library_path = None
            for lib in libraries:
                if lib.get("name") == library_name:
                    library_path = lib.get("path")
                    break

            if not library_path:
                console.print(
                    f"No {library_type} library named '{library_name}' found."
                )
                console.print("Use 'kilm config list' to see available libraries.")
                sys.exit(1)

        # Set as current library
        if library_path is None:
            console.print(
                f"[red]Error: Could not find path for library '{library_name}'[/red]"
            )
            sys.exit(1)
        config.set_current_library(library_path)
        console.print(f"Set {library_type} library '{library_name}' as default.")
        console.print(f"Path: {library_path}")

    except Exception as e:
        console.print(f"[red]Error setting default library: {e}[/red]")
        sys.exit(1)


def remove(
    library_name: Annotated[str, typer.Argument(help="Name of library to remove")],
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
    """Remove a library from the configuration.

    Removes the specified library from the KiCad Library Manager configuration.
    This does not delete any files, it only removes the library from the configuration.

    Examples:

    \b
    # Remove a library (prompts for confirmation)
    kilm config remove my-library

    \b
    # Remove a specific library type
    kilm config remove my-library --type github

    \b
    # Force removal without confirmation
    kilm config remove my-library --force
    """
    try:
        config = Config()

        # Get current library path
        current_library = config.get_current_library()

        # Get all libraries
        all_libraries = config.get_libraries()

        # Find libraries matching the name and type
        matching_libraries = []
        for lib in all_libraries:
            if lib.get("name") == library_name and (
                library_type == "all" or lib.get("type") == library_type
            ):
                matching_libraries.append(lib)

        if not matching_libraries:
            if library_type == "all":
                console.print(f"No library named '{library_name}' found.")
            else:
                console.print(
                    f"No {library_type} library named '{library_name}' found."
                )
            console.print("Use 'kilm config list' to see available libraries.")
            sys.exit(1)

        # Confirm removal
        if not force:
            for lib in matching_libraries:
                lib_type = lib.get("type", "unknown")
                lib_path = lib.get("path", "unknown")
                console.print(
                    f"Will remove {lib_type} library '{library_name}' from configuration."
                )
                console.print(f"Path: {lib_path}")

                if lib_path == current_library:
                    console.print("Warning: This is the current default library.")

            if not typer.confirm("Continue?"):
                console.print("Operation cancelled.")
                return

        # Remove libraries
        removed_count = 0
        for lib in matching_libraries:
            lib_type = lib.get("type", "unknown")
            removed = config.remove_library(library_name, lib_type)
            if removed:
                removed_count += 1

        if removed_count > 0:
            if removed_count == 1:
                console.print(f"Removed library '{library_name}' from configuration.")
            else:
                console.print(
                    f"Removed {removed_count} instances of library '{library_name}' from configuration."
                )

            # Check if we removed the current library
            current_library_new = config.get_current_library()
            if current_library and current_library != current_library_new:
                console.print(
                    "Note: Default library was changed as the previous default was removed."
                )
        else:
            console.print("No libraries were removed.")

    except Exception as e:
        console.print(f"[red]Error removing library: {e}[/red]")
        sys.exit(1)
