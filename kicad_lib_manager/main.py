#!/usr/bin/env python3
"""
Main Typer CLI entry point for KiCad Library Manager
"""

import importlib.metadata
from typing import Annotated, Optional

import typer
from rich.align import Align
from rich.console import Console
from rich.text import Text
from rich.traceback import install
from typer.core import TyperGroup

from .commands.add_3d import add_3d_app
from .commands.add_hook import add_hook_app
from .commands.config import config_app
from .commands.init import init_app
from .commands.list_libraries import list_app
from .commands.pin import pin_app
from .commands.setup import setup_app
from .commands.status import status_app
from .commands.sync import sync_app
from .commands.template import template_app
from .commands.unpin import unpin_app
from .commands.update import update_app
from .utils.banner import show_banner

TAGLINE = "Professional KiCad library management"

# Install rich traceback handler for better error display
install(show_locals=True)

# Initialize Rich console
console = Console()


class BannerGroup(TyperGroup):
    """Custom group that shows banner before help."""

    def format_help(self, ctx, formatter):
        # Show banner before help
        show_banner(console, justify="center")
        console.print()
        console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
        console.print()
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
        Optional[bool],
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


# Register command apps (migrated to Typer)
app.add_typer(status_app, name="status", help="Show current library configuration")
app.add_typer(list_app, name="list", help="List available KiCad libraries")
app.add_typer(init_app, name="init", help="Initialize library configuration")
app.add_typer(pin_app, name="pin", help="Pin favorite libraries")
app.add_typer(unpin_app, name="unpin", help="Unpin favorite libraries")
app.add_typer(setup_app, name="setup", help="Configure KiCad to use libraries")
app.add_typer(config_app, name="config", help="Manage configuration settings")
app.add_typer(template_app, name="template", help="Manage project templates")
app.add_typer(add_3d_app, name="add-3d", help="Add 3D model libraries")
app.add_typer(sync_app, name="sync", help="Update/sync library content")
app.add_typer(update_app, name="update", help="Update KiLM itself")
app.add_typer(add_hook_app, name="add-hook", help="Add project hooks")


if __name__ == "__main__":
    app()
