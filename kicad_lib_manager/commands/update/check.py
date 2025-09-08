"""Update check command implementation."""

import importlib.metadata
from typing import Annotated

import typer
from rich.console import Console

from ...services.update_service import UpdateService

console = Console()


def check_update_command(
    force: Annotated[
        bool, typer.Option(help="Force fresh check, bypass cache")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Only show output if update is available"),
    ] = False,
) -> None:
    """Check for available updates without installing."""

    version = importlib.metadata.version("kilm")
    update_service = UpdateService(version)

    # Use force flag to bypass cache
    update_info = update_service.check_for_updates(use_cache=not force)

    if update_info["has_update"]:
        current = update_info["current_version"]
        latest = update_info["latest_version"]
        method = update_info["method"]
        can_auto_update = update_info["supports_auto_update"]

        console.print("[yellow]Update available![/yellow]")
        console.print(f"Current version: [blue]{current}[/blue]")
        console.print(f"Latest version: [green]{latest}[/green]")
        console.print(f"Installation method: [cyan]{method}[/cyan]")

        if can_auto_update:
            console.print("\nRun [bold cyan]kilm update perform[/bold cyan] to update")
        else:
            update_cmd = update_service.get_update_instructions()
            console.print(f"\nManual update required: [cyan]{update_cmd}[/cyan]")

        # Exit with code 1 to indicate update available
        raise typer.Exit(1)
    else:
        if not quiet:
            console.print(
                f"[green]✓[/green] You are using the latest version ([bold cyan]v{update_info['current_version']}[/bold cyan])"
            )
        # Exit with code 0 for no update needed
        raise typer.Exit(0)
