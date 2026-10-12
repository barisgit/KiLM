#!/usr/bin/env python3
"""
Main Typer CLI entry point for KiCad Library Manager
"""

import importlib.metadata
from typing import Annotated

import typer
from rich.align import Align
from rich.console import Console
from rich.text import Text
from rich.traceback import install
from typer.core import TyperGroup

from .commands.add_3d import add_3d
from .commands.add_hook import add_hook
from .commands.config import config_app
from .commands.import_zip import import_zip
from .commands.init import init
from .commands.list_libraries import list_cmd
from .commands.pin import pin
from .commands.setup import setup
from .commands.status import status
from .commands.sync import sync
from .commands.template import template_app
from .commands.unpin import unpin
from .commands.update import update_app
from .services.config_service import ConfigService
from .services.update_service import UpdateService
from .utils.banner import show_banner

TAGLINE = "Professional KiCad library management"

# Install rich traceback handler for better error display
install(show_locals=True)

# Initialize Rich console
console = Console()


def _check_for_updates_if_needed() -> None:
    """Check for updates if configured to do so, non-intrusively."""
    try:
        config_service = ConfigService()
        config = config_service._config

        # Skip if update checking is disabled
        if not config.get("update_check", True):
            return

        version = importlib.metadata.version("kilm")
        update_service = UpdateService(version)

        # Always show notification if update is available, regardless of frequency
        # Only respect frequency for the actual PyPI API calls
        if config.should_check_updates():
            # Time to make a fresh API call
            if update_service.show_update_notification(quiet=True):
                config.mark_update_check_performed()
        else:
            # Use cached data to show notification if update available
            update_info = update_service.check_for_updates(use_cache=True)
            if update_info["has_update"]:
                update_service.show_update_notification(quiet=True)

    except Exception:
        # Silently fail - don't break CLI functionality
        pass


class BannerGroup(TyperGroup):
    """Custom group that shows banner before help."""

    def format_help(self, ctx, formatter):
        # Show banner before help
        show_banner(console, justify="center")
        console.print()
        console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
        console.print()
        _check_for_updates_if_needed()
        super().format_help(ctx, formatter)


# Create main Typer app
app = typer.Typer(
    name="kilm",
    help="KiCad Library Manager - Manage KiCad libraries across projects and workstations",
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    invoke_without_command=True,
    cls=BannerGroup,
)


def version_callback(value: bool) -> None:
    """Print version information and exit."""
    if value:
        show_banner(console, justify="left")
        console.print()

        version = importlib.metadata.version("kilm")
        console.print(f"KiCad Library Manager (KiLM) version [cyan]{version}[/cyan]")
        raise typer.Exit()


@app.callback()
def main(
    _version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Show version information and exit",
        ),
    ] = None,
) -> None:
    """
    [bold blue]KiCad Library Manager[/bold blue] - Professional KiCad library management

    This tool helps you configure and manage KiCad libraries across your projects
    and workstations with a modern, type-safe CLI interface.

    [bold]Common Commands:[/bold]
    • [cyan]kilm status[/cyan]     - Show current configuration
    • [cyan]kilm setup[/cyan]      - Configure KiCad to use libraries
    • [cyan]kilm list[/cyan]       - List available libraries
    • [cyan]kilm sync[/cyan]       - Update library content
    """
    # Show banner when no arguments are provided, centered
    import sys

    if not sys.argv[1:]:
        show_banner(console)
        console.print()
        console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
        console.print()
        console.print(
            "[dim]Use 'kilm --help' to see all commands.[/dim]", justify="center"
        )
    else:
        # Check for updates if configured to do so only if not banner
        _check_for_updates_if_needed()


# Leaf commands are registered as plain commands: a Typer sub-app with only a
# callback renders as a group, and its usage line gets a spurious COMMAND [ARGS]...
app.command("status", help="Show current library configuration")(status)
app.command("list", help="List available KiCad libraries")(list_cmd)
app.command("init", help="Initialize library configuration")(init)
app.command("pin", help="Pin favorite libraries")(pin)
app.command("unpin", help="Unpin favorite libraries")(unpin)
app.command("setup", help="Configure KiCad to use libraries")(setup)
app.command("sync", help="Update/sync library content")(sync)
app.command("add-3d", help="Add 3D model libraries")(add_3d)
app.command("add-hook", help="Add project hooks")(add_hook)
app.command(
    "import",
    help="Import SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP(s) into the library",
)(import_zip)
# Groups keep their subcommands.
app.add_typer(config_app, name="config", help="Manage configuration settings")
app.add_typer(template_app, name="template", help="Manage project templates")
app.add_typer(update_app, name="update", help="Update KiLM itself")


if __name__ == "__main__":
    app()
