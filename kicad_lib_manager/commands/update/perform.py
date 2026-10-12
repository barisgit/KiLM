"""`kilm update perform`: install a new KiLM release with its own installer."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"packaging.version"}

import importlib.metadata
from typing import Annotated

import typer
from packaging.version import InvalidVersion, Version
from rich.panel import Panel

from kicad_lib_manager.services.update_service import UpdateService
from kicad_lib_manager.utils.console import get_console

BREAKING_CHANGE_NOTICE = (
    "[bold yellow]BREAKING CHANGE NOTICE (KiLM 0.4.0)[/bold yellow]\n\n"
    "The [bold]kilm update[/bold] command now updates KiLM itself.\n"
    "To update library content, use [bold cyan]kilm sync[/bold cyan] instead.\n"
    "This notice will be removed in a future version."
)


def perform_update_command(
    *,
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

    DEPRECATION NOTICE:
    In KiLM 0.4.0, the 'update' command now updates KiLM itself.
    To update library content, use 'kilm sync' instead.
    This banner will be removed in a future version.
    """
    console = get_console()
    console.print(Panel(BREAKING_CHANGE_NOTICE, expand=False, border_style="yellow"))
    if target_version is not None:
        _validate_version(target_version)
    update_service = UpdateService(importlib.metadata.version("kilm"))

    if dry_run:
        console.print("[yellow]Dry run mode - showing what would be done[/yellow]")
        console.print()
    # A dry run fails the same way as the real update would.
    if not update_service.can_auto_update:
        _exit_with_manual_instruction(update_service)
    if dry_run:
        _show_update_plan(update_service, target_version)
        raise typer.Exit(0)
    if not force:
        _announce_update_or_exit(update_service, target_version, use_cache=not no_cache)

    result = update_service.perform_update(target_version)
    if not result.success:
        console.print(f"\n[red]Update failed:[/red] {result.message}")
        raise typer.Exit(1)
    console.print("\n[green]Update completed successfully![/green]")
    console.print(
        "You may need to restart your shell or run [cyan]hash -r[/cyan]"
        " to use the new version"
    )


def _validate_version(target_version: str) -> None:
    """Reject a --target-version that is not a version number (exit status 2)."""
    try:
        Version(target_version)
    except InvalidVersion:
        message = f"'{target_version}' is not a version number"
        raise typer.BadParameter(message, param_hint="--target-version") from None


def _exit_with_manual_instruction(update_service: UpdateService) -> None:
    """Explain how to update an installation KiLM cannot update, then exit 1."""
    console = get_console()
    console.print(
        "[yellow]Warning:[/yellow] Automatic update not supported"
        " for your installation method."
    )
    console.print(f"Installation method: [bold]{update_service.method}[/bold]")
    instruction = update_service.update_instruction()
    console.print(f"Update manually: [bold cyan]{instruction}[/bold cyan]")
    raise typer.Exit(1)


def _announce_update_or_exit(
    update_service: UpdateService, target_version: str | None, *, use_cache: bool
) -> None:
    """Print what the update installs, or exit 0 when nothing would change."""
    console = get_console()
    current = update_service.current_version
    if target_version is not None:
        if Version(target_version) == Version(current):
            console.print(
                f"[green]Already using version[/green] [bold cyan]{current}[/bold cyan]"
            )
            raise typer.Exit(0)
        target = target_version
    else:
        status = update_service.check_for_updates(use_cache=use_cache)
        if not status["has_update"]:
            console.print(
                "[green]Already using the latest version[/green]"
                f" ([bold cyan]v{current}[/bold cyan])"
            )
            console.print("\nUse [cyan]--force[/cyan] to reinstall the current version")
            raise typer.Exit(0)
        target = status["latest_version"]
    console.print(f"Updating from [blue]{current}[/blue] to [green]{target}[/green]")
    console.print()


def _show_update_plan(
    update_service: UpdateService, target_version: str | None
) -> None:
    """Print the installer command a real update would run."""
    package_spec = "kilm" if target_version is None else f"kilm=={target_version}"
    command = update_service.update_instruction(target_version)
    get_console().print(
        Panel(
            "\n".join(
                [
                    "[bold]Update Plan (Dry Run)[/bold]",
                    "",
                    f"Installation method: [cyan]{update_service.method}[/cyan]",
                    f"Target package: [green]{package_spec}[/green]",
                    "Auto-update supported: [green]True[/green]",
                    "",
                    "Command that would be executed:",
                    f"[bold cyan]{command}[/bold cyan]",
                ]
            ),
            title="[bold yellow]Dry Run[/bold yellow]",
            border_style="yellow",
        )
    )
    get_console().print("\nDry run completed - automatic update is supported")
