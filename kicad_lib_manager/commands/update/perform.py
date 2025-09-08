"""Update perform command implementation."""

import importlib.metadata
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from ...services.update_service import UpdateService

console = Console()


def perform_update_command(
    target_version: Annotated[
        Optional[str],
        typer.Option(
            "--target-version",
            "-t",
            help="Specific version to install (default: latest)",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Force update even if already up to date"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would be updated without doing it"),
    ] = False,
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Skip cache and force fresh version check"),
    ] = False,
) -> None:
    """Perform KiLM update installation.

    This command updates KiLM itself by downloading and installing the latest
    version from PyPI. The update method depends on how KiLM was installed
    (pip, pipx, uv tool, etc.).

    ⚠️  DEPRECATION NOTICE:
    In KiLM 0.4.0, the 'update' command now updates KiLM itself.
    To update library content, use 'kilm sync' instead.
    This banner will be removed in a future version.
    """

    # Show deprecation notice
    deprecation_notice = (
        "[bold yellow]⚠️  BREAKING CHANGE NOTICE (KiLM 0.4.0)[/bold yellow]\n\n"
        "The [bold]kilm update[/bold] command now updates KiLM itself.\n"
        "To update library content, use [bold cyan]kilm sync[/bold cyan] instead.\n"
        "This notice will be removed in a future version."
    )
    console.print(Panel(deprecation_notice, expand=False, border_style="yellow"))

    version = importlib.metadata.version("kilm")
    update_service = UpdateService(version)

    if dry_run:
        console.print("[yellow]Dry run mode - showing what would be done[/yellow]")
        console.print()

    # Check if we can auto-update (skip during dry run)
    if not dry_run and not update_service.can_auto_update():
        console.print(
            "[yellow]⚠[/yellow] Automatic update not supported for your installation method."
        )
        method = update_service.get_installation_method()
        update_cmd = update_service.get_update_instructions()

        console.print(f"Installation method: [bold]{method}[/bold]")
        console.print(f"Please run manually: [bold cyan]{update_cmd}[/bold cyan]")
        raise typer.Exit(1)

    # Perform update check first (unless forced)
    if not force and not dry_run:
        update_info = update_service.check_for_updates(use_cache=not no_cache)
        if not update_info["has_update"]:
            console.print(
                f"[green]✓[/green] Already using the latest version ([bold cyan]v{update_info['current_version']}[/bold cyan])"
            )
            console.print("\nUse [cyan]--force[/cyan] to reinstall the current version")
            raise typer.Exit(0)

        current = update_info["current_version"]
        latest = update_info["latest_version"]
        target = target_version or latest

        if not dry_run:
            console.print(
                f"Updating from [blue]{current}[/blue] to [green]{target}[/green]"
            )
            console.print()

    # Perform the update
    success, message = update_service.perform_update(
        target_version=target_version, force=force, dry_run=dry_run
    )

    if dry_run:
        if success:
            console.print(
                "\n[green]✓[/green] Dry run completed - automatic update is supported"
            )
        else:
            console.print("\n[red]✗[/red] Automatic update not available")
            console.print("Manual update will be required")
        raise typer.Exit(0)

    if success:
        console.print("\n[green]✓[/green] Update completed successfully!")
        console.print(
            "You may need to restart your shell or run [cyan]hash -r[/cyan] to use the new version"
        )
    else:
        console.print(f"\n[red]✗[/red] Update failed: {message}")
        console.print("Please try updating manually or check the error messages above")
        raise typer.Exit(1)
