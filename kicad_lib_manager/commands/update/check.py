"""`kilm update check`: report whether a newer KiLM release exists."""

import importlib.metadata
from typing import Annotated

import typer

from kicad_lib_manager.services.update_service import UpdateService
from kicad_lib_manager.utils.console import get_console


def check_update_command(
    *,
    force: Annotated[
        bool, typer.Option(help="Force fresh check, bypass cache")
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Only show output if update is available"),
    ] = False,
) -> None:
    """Check for available updates without installing.

    Exits with status 1 when an update is available, 0 otherwise.
    """
    console = get_console()
    update_service = UpdateService(importlib.metadata.version("kilm"))
    status = update_service.check_for_updates(use_cache=not force)

    if not status["has_update"]:
        if not quiet:
            console.print(
                "[green]You are using the latest version[/green]"
                f" ([bold cyan]v{status['current_version']}[/bold cyan])"
            )
        raise typer.Exit(0)

    console.print("[yellow]Update available![/yellow]")
    console.print(f"Current version: [blue]{status['current_version']}[/blue]")
    console.print(f"Latest version: [green]{status['latest_version']}[/green]")
    console.print(f"Installation method: [cyan]{status['method']}[/cyan]")
    if status["supports_auto_update"]:
        console.print("\nRun [bold cyan]kilm update perform[/bold cyan] to update")
    else:
        instruction = update_service.update_instruction()
        console.print(f"\nManual update required: [cyan]{instruction}[/cyan]")
    raise typer.Exit(1)
