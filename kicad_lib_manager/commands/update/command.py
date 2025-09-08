"""
Update command implementation for KiCad Library Manager (Typer version).
Updates KiLM itself to the latest version.
"""

import importlib.metadata
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel

from ...services.update_service import UpdateManager

console = Console()


def update(
    check: Annotated[
        bool, typer.Option(help="Check for updates without installing")
    ] = False,
    force: Annotated[
        bool, typer.Option(help="Force update even if already up to date")
    ] = False,
) -> None:
    """Update KiLM to the latest version.

    This command updates KiLM itself by downloading and installing the latest
    version from PyPI. The update method depends on how KiLM was installed
    (pip, pipx, conda, etc.).

    ⚠️  DEPRECATION NOTICE:
    In KiLM 0.4.0, the 'update' command now updates KiLM itself.
    To update library content, use 'kilm sync' instead.
    This banner will be removed in a future version.

    Use --check to see if updates are available without installing.
    """

    deprecation_notice = (
        "[bold yellow]⚠️  BREAKING CHANGE NOTICE (KiLM 0.4.0)[/bold yellow]\n\n"
        "The [bold]kilm update[/bold] command now updates KiLM itself.\n"
        "To update library content, use [bold cyan]kilm sync[/bold cyan] instead.\n"
        "This notice will be removed in a future version."
    )
    console.print(Panel(deprecation_notice, expand=False, border_style="yellow"))

    version = importlib.metadata.version("kilm")

    update_manager = UpdateManager(version)

    console.print(
        f"[blue]Current KiLM version:[/blue] [bold cyan]v{version}[/bold cyan]"
    )
    console.print(
        f"[blue]Installation method:[/blue] {update_manager.installation_method}"
    )
    console.print("\n[bold cyan]Checking for updates...[/bold cyan]")

    latest_version = update_manager.check_latest_version()

    if latest_version is None:
        console.print("[red]Could not check for updates. Please try again later.[/red]")
        return

    if not update_manager.is_newer_version_available(latest_version):
        if not force:
            console.print(
                f"[green]KiLM is up to date[/green] [bold green]v{version}[/bold green]"
            )
            return
        else:
            console.print(
                f"[yellow]Forcing update to v{latest_version}[/yellow] (current: v{version})"
            )
    else:
        console.print(
            f"[green]New version available:[/green] [bold green]v{latest_version}[/bold green]"
        )

    if check:
        if update_manager.is_newer_version_available(latest_version):
            console.print(
                f"\n[green]Update available:[/green] [bold green]v{latest_version}[/bold green]"
            )
            console.print(
                f"[blue]To update, run:[/blue] [cyan]{update_manager.get_update_instruction()}[/cyan]"
            )
        else:
            console.print("[green]No updates available[/green]")
        return

    # Perform the update
    if update_manager.can_auto_update():
        console.print(
            f"\n[bold cyan]Updating KiLM to version {latest_version}...[/bold cyan]"
        )
        success, message = update_manager.perform_update()

        if success:
            console.print(f"[bold green]✅ {message}[/bold green]")
            console.print(
                f"[green]KiLM has been updated to version {latest_version}[/green]"
            )
        else:
            console.print(f"[bold red]❌ {message}[/bold red]")
    else:
        instruction = update_manager.get_update_instruction()
        console.print(
            f"\n[yellow]Manual update required for {update_manager.installation_method} installation.[/yellow]"
        )
        console.print(f"[blue]Please run:[/blue] [cyan]{instruction}[/cyan]")
