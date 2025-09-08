"""Update info command implementation."""

import importlib.metadata
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from ...services.update_service import UpdateService

console = Console()


def info_command(
    force_check: Annotated[
        bool, typer.Option(help="Force fresh version check, bypass cache")
    ] = False,
) -> None:
    """Show detailed installation and update information."""

    version = importlib.metadata.version("kilm")
    update_service = UpdateService(version)

    # Get installation and update information
    update_info = update_service.check_for_updates(use_cache=not force_check)
    method = update_service.get_installation_method()
    can_auto_update = update_service.can_auto_update()
    update_cmd = update_service.get_update_instructions()

    # Current version status
    version_status = f"[green]{update_info['current_version']}[/green]"
    if update_info["has_update"]:
        version_status += (
            f" → [yellow]{update_info['latest_version']} available[/yellow]"
        )
    else:
        version_status += " [dim](latest)[/dim]"

    # Installation details
    install_details = [
        f"Method: [cyan]{method}[/cyan]",
        f"Auto-update: [{'green' if can_auto_update else 'red'}]{can_auto_update}[/]",
        f"Update command: [cyan]{update_cmd}[/cyan]",
    ]

    # Display information
    console.print(
        Panel(
            f"""[bold]Version Information[/bold]
Current version: {version_status}

[bold]Installation Details[/bold]
{chr(10).join(install_details)}

[bold]Available Commands[/bold]
[cyan]kilm update check[/cyan]    - Check for updates
[cyan]kilm update perform[/cyan]  - Install updates
[cyan]kilm update info[/cyan]     - Show this information""",
            title="[bold blue]KiLM Installation Info[/bold blue]",
            border_style="blue",
        )
    )
