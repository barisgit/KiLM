"""Update perform command implementation."""

import importlib.metadata
from typing import Annotated

import typer
from packaging.version import InvalidVersion, Version
from rich.panel import Panel

from kicad_lib_manager.utils.console import get_console

from ...services.update_service import UpdateService


def perform_update_command(
    target_version: Annotated[
        str | None,
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
    get_console().print(Panel(deprecation_notice, expand=False, border_style="yellow"))

    version = importlib.metadata.version("kilm")
    if target_version is not None:
        try:
            Version(target_version)
        except InvalidVersion:
            raise typer.BadParameter(
                f"'{target_version}' is not a version number",
                param_hint="--target-version",
            ) from None
    update_service = UpdateService(version)

    if dry_run:
        get_console().print(
            "[yellow]Dry run mode - showing what would be done[/yellow]"
        )
        get_console().print()

    # A dry run fails the same way as the real update would.
    if not update_service.can_auto_update():
        get_console().print(
            "[yellow]⚠[/yellow] Automatic update not supported for your installation method."
        )
        method = update_service.get_installation_method()
        update_cmd = update_service.get_update_instructions()

        get_console().print(f"Installation method: [bold]{method}[/bold]")
        get_console().print(f"Update manually: [bold cyan]{update_cmd}[/bold cyan]")
        raise typer.Exit(1)

    if target_version is not None and not force and not dry_run:
        if Version(target_version) == Version(version):
            get_console().print(
                f"[green]✓[/green] Already using version [bold cyan]{version}[/bold cyan]"
            )
            raise typer.Exit(0)
        get_console().print(
            f"Updating from [blue]{version}[/blue] to [green]{target_version}[/green]"
        )
        get_console().print()
    elif not force and not dry_run:
        update_info = update_service.check_for_updates(use_cache=not no_cache)
        if not update_info["has_update"]:
            get_console().print(
                f"[green]✓[/green] Already using the latest version ([bold cyan]v{update_info['current_version']}[/bold cyan])"
            )
            get_console().print(
                "\nUse [cyan]--force[/cyan] to reinstall the current version"
            )
            raise typer.Exit(0)

        current = update_info["current_version"]
        latest = update_info["latest_version"]
        get_console().print(
            f"Updating from [blue]{current}[/blue] to [green]{latest}[/green]"
        )
        get_console().print()

    # Perform the update
    success, message = update_service.perform_update(
        target_version=target_version, force=force, dry_run=dry_run
    )

    if dry_run:
        if success:
            get_console().print(
                "\n[green]✓[/green] Dry run completed - automatic update is supported"
            )
            raise typer.Exit(0)
        get_console().print("\n[red]✗[/red] Automatic update not available")
        get_console().print("Manual update will be required")
        raise typer.Exit(1)

    if success:
        get_console().print("\n[green]✓[/green] Update completed successfully!")
        get_console().print(
            "You may need to restart your shell or run [cyan]hash -r[/cyan] to use the new version"
        )
    else:
        get_console().print(f"\n[red]✗[/red] Update failed: {message}")
        get_console().print(
            "Please try updating manually or check the error messages above"
        )
        raise typer.Exit(1)
