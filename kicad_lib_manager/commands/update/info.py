"""`kilm update info`: show how KiLM is installed and how it updates."""

import importlib.metadata
from typing import Annotated

import typer
from rich.panel import Panel

from kicad_lib_manager.services.update_service import UpdateService
from kicad_lib_manager.utils.console import get_console


def info_command(
    *,
    force_check: Annotated[
        bool, typer.Option(help="Force fresh version check, bypass cache")
    ] = False,
) -> None:
    """Show detailed installation and update information."""
    update_service = UpdateService(importlib.metadata.version("kilm"))
    status = update_service.check_for_updates(use_cache=not force_check)

    version_status = f"[green]{status['current_version']}[/green]"
    if status["has_update"]:
        version_status += f" → [yellow]{status['latest_version']} available[/yellow]"
    else:
        version_status += " [dim](latest)[/dim]"

    auto_update = status["supports_auto_update"]
    auto_update_color = "green" if auto_update else "red"
    instruction = update_service.update_instruction()
    get_console().print(
        Panel(
            "\n".join(
                [
                    "[bold]Version Information[/bold]",
                    f"Current version: {version_status}",
                    "",
                    "[bold]Installation Details[/bold]",
                    f"Method: [cyan]{status['method']}[/cyan]",
                    f"Auto-update: [{auto_update_color}]{auto_update}[/]",
                    f"Update command: [cyan]{instruction}[/cyan]",
                    "",
                    "[bold]Available Commands[/bold]",
                    "[cyan]kilm update check[/cyan]    - Check for updates",
                    "[cyan]kilm update perform[/cyan]  - Install updates",
                    "[cyan]kilm update info[/cyan]     - Show this information",
                ]
            ),
            title="[bold blue]KiLM Installation Info[/bold blue]",
            border_style="blue",
        )
    )
