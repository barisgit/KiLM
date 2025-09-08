"""
Status command implementation for KiCad Library Manager (Typer version).
"""

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ...services.kicad_service import KiCadService
from ...utils.constants import CONFIG_DIR_NAME, CONFIG_FILE_NAME
from ...utils.metadata import read_cloud_metadata, read_github_metadata

console = Console()


def status(
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show detailed configured libraries tables",
        ),
    ] = False,
) -> None:
    """Show the current KiCad configuration status"""
    try:
        # Initialize services
        kicad_service = KiCadService()

        # Show KILM configuration first
        _show_kilm_configuration()

        console.print("\n[bold cyan]KiCad Configuration[/bold cyan]")

        kicad_config = kicad_service.find_kicad_config_dir()
        console.print(f"KiCad configuration directory: [blue]{kicad_config}[/blue]")

        # Check environment variables in KiCad common
        _show_kicad_environment_variables(kicad_config)

        # Check pinned libraries
        _check_pinned_libraries(kicad_config, kicad_service)

        # Check configured libraries (only in verbose mode)
        if verbose:
            _show_configured_libraries(kicad_config, kicad_service)

    except Exception as e:
        console.print(f"[red]Error getting KiCad configuration: {e}[/red]")
        raise typer.Exit(1) from e


def _show_kilm_configuration() -> None:
    """Show KILM configuration section"""
    try:
        config_file = Path.home() / ".config" / CONFIG_DIR_NAME / CONFIG_FILE_NAME
        if config_file.exists():
            console.print("[bold cyan]KILM Configuration[/bold cyan]")
            try:
                with config_file.open() as f:
                    config_data = yaml.safe_load(f)

                if config_data is not None:
                    _show_configured_libraries_table(config_data)
                    _show_kilm_settings(config_data)
                else:
                    console.print(
                        "[yellow]Configuration file is empty or invalid[/yellow]"
                    )

            except Exception as e:
                console.print(f"[red]Error reading configuration: {e}[/red]")
        else:
            console.print(
                "[yellow]No KILM configuration file found. Run 'kilm init' to create one.[/yellow]"
            )
    except Exception as e:
        console.print(f"[red]Error reading KILM configuration: {e}[/red]")


def _show_configured_libraries_table(config_data: dict) -> None:
    """Show configured libraries in a table format"""
    if not config_data or not config_data.get("libraries"):
        console.print("[yellow]  No libraries configured[/yellow]")
        return

    # Create tables for different library types
    github_libs = [
        lib for lib in config_data["libraries"] if lib.get("type") == "github"
    ]
    cloud_libs = [lib for lib in config_data["libraries"] if lib.get("type") == "cloud"]

    current_library = config_data.get("current_library", "")

    if github_libs:
        table = Table(title="GitHub Libraries (symbols/footprints)", show_header=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Path", style="blue")
        table.add_column("Status", justify="center")
        table.add_column("Metadata", justify="center")

        for lib in github_libs:
            name = lib.get("name", "unnamed")
            path = lib.get("path", "unknown")
            is_current = "✓ Current" if current_library == path else ""

            # Check metadata
            try:
                has_metadata = "✓" if read_github_metadata(Path(path)) else "✗"
            except Exception:
                has_metadata = "?"

            table.add_row(name, path, is_current, has_metadata)

        console.print(table)

    if cloud_libs:
        table = Table(title="Cloud Libraries (3D models)", show_header=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Path", style="blue")
        table.add_column("Status", justify="center")
        table.add_column("Metadata", justify="center")

        for lib in cloud_libs:
            name = lib.get("name", "unnamed")
            path = lib.get("path", "unknown")
            is_current = "✓ Current" if current_library == path else ""

            # Check metadata
            try:
                has_metadata = "✓" if read_cloud_metadata(Path(path)) else "✗"
            except Exception:
                has_metadata = "?"

            table.add_row(name, path, is_current, has_metadata)

        console.print(table)


def _show_kilm_settings(config_data: dict) -> None:
    """Show KILM settings"""
    if not config_data:
        return

    settings_text = Text()

    # Current library
    current_lib = config_data.get("current_library")
    if current_lib:
        settings_text.append(f"Current Library: {current_lib}\n", style="green")
    else:
        settings_text.append("No current library set\n", style="yellow")

    # Max backups
    max_backups = config_data.get("max_backups")
    if max_backups is not None:
        settings_text.append(f"Max Backups: {max_backups}", style="blue")

    if settings_text.plain:
        console.print(Panel(settings_text, title="Settings", border_style="blue"))


def _show_kicad_environment_variables(kicad_config: Path) -> None:
    """Show KiCad environment variables"""
    kicad_common = kicad_config / "kicad_common.json"
    if not kicad_common.exists():
        console.print("[yellow]No kicad_common.json found[/yellow]")
        return

    try:
        with kicad_common.open() as f:
            common_config = json.load(f)

        console.print("\n[bold]Environment Variables in KiCad:[/bold]")

        if "environment" in common_config and "vars" in common_config["environment"]:
            env_vars = common_config["environment"]["vars"]
            if env_vars:
                table = Table(show_header=True)
                table.add_column("Variable", style="cyan", no_wrap=True)
                table.add_column("Value", style="blue")

                for key, value in env_vars.items():
                    table.add_row(key, str(value))

                console.print(table)
            else:
                console.print("[yellow]  No environment variables set[/yellow]")
        else:
            console.print("[yellow]  No environment variables found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error reading KiCad common configuration: {e}[/red]")


def _check_pinned_libraries(kicad_config: Path, kicad_service: KiCadService) -> None:
    """Check and display pinned libraries"""
    _ = kicad_service  # Suppress unused warning, TODO: implement functionality
    kicad_common = kicad_config / "kicad_common.json"
    if kicad_common.exists():
        try:
            with kicad_common.open() as f:
                common_config = json.load(f)

            found_pinned = False
            console.print("\n[bold]Pinned Libraries in KiCad:[/bold]")

            # Check for pinned symbol libraries
            if (
                "session" in common_config
                and "pinned_symbol_libs" in common_config["session"]
            ):
                sym_libs = common_config["session"]["pinned_symbol_libs"]
                if sym_libs:
                    found_pinned = True
                    console.print("[cyan]Symbol Libraries:[/cyan]")
                    for lib in sym_libs:
                        console.print(f"  • {lib}")

            # Check for pinned footprint libraries
            if (
                "session" in common_config
                and "pinned_fp_libs" in common_config["session"]
            ):
                fp_libs = common_config["session"]["pinned_fp_libs"]
                if fp_libs:
                    found_pinned = True
                    console.print("[cyan]Footprint Libraries:[/cyan]")
                    for lib in fp_libs:
                        console.print(f"  • {lib}")

            if not found_pinned:
                console.print(
                    "[yellow]  No pinned libraries found in kicad_common.json[/yellow]"
                )

            return
        except Exception as e:
            console.print(
                f"[red]Error reading pinned libraries from kicad_common.json: {e}[/red]"
            )

    # Fall back to the old method of looking for a separate pinned file
    pinned_libs = kicad_config / "pinned"
    if pinned_libs.exists():
        try:
            with pinned_libs.open() as f:
                pinned_config = json.load(f)

            console.print("\n[bold]Pinned Libraries in KiCad (legacy format):[/bold]")
            found_pinned = False

            if "pinned_symbol_libs" in pinned_config:
                sym_libs = pinned_config["pinned_symbol_libs"]
                if sym_libs:
                    found_pinned = True
                    console.print("[cyan]Symbol Libraries:[/cyan]")
                    for lib in sym_libs:
                        console.print(f"  • {lib}")

            if "pinned_footprint_libs" in pinned_config:
                fp_libs = pinned_config["pinned_footprint_libs"]
                if fp_libs:
                    found_pinned = True
                    console.print("[cyan]Footprint Libraries:[/cyan]")
                    for lib in fp_libs:
                        console.print(f"  • {lib}")

            if not found_pinned:
                console.print("[yellow]  No pinned libraries found[/yellow]")
        except Exception as e:
            console.print(f"[red]Error reading pinned libraries: {e}[/red]")
    else:
        console.print("\n[yellow]No pinned libraries file found[/yellow]")


def _show_configured_libraries(kicad_config: Path, kicad_service: KiCadService) -> None:
    """Show configured libraries in KiCad"""
    try:
        sym_libs, fp_libs = kicad_service.get_configured_libraries(kicad_config)

        console.print("\n[bold]Configured Symbol Libraries:[/bold]")
        if sym_libs:
            table = Table(show_header=True)
            table.add_column("Library Name", style="cyan", no_wrap=True)
            table.add_column("URI", style="blue")

            for lib in sym_libs:
                table.add_row(lib.get("name", ""), lib.get("uri", ""))

            console.print(table)
        else:
            console.print("[yellow]  No symbol libraries configured[/yellow]")

        console.print("\n[bold]Configured Footprint Libraries:[/bold]")
        if fp_libs:
            table = Table(show_header=True)
            table.add_column("Library Name", style="cyan", no_wrap=True)
            table.add_column("URI", style="blue")

            for lib in fp_libs:
                table.add_row(lib.get("name", ""), lib.get("uri", ""))

            console.print(table)
        else:
            console.print("[yellow]  No footprint libraries configured[/yellow]")
    except Exception as e:
        console.print(f"[red]Error listing configured libraries: {e}[/red]")
