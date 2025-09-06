#!/usr/bin/env python3
"""
Main Typer CLI entry point for KiCad Library Manager
"""

import importlib.metadata
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.traceback import install

from .commands.init import init_app
from .commands.list_libraries import list_app
from .commands.pin import pin_app
from .commands.status import status_app

# Install rich traceback handler for better error display
install(show_locals=True)

# Initialize Rich console
console = Console()

# Create main Typer app
app = typer.Typer(
    name="kilm",
    help="KiCad Library Manager - Manage KiCad libraries across projects and workstations",
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Print version information and exit."""
    if value:
        version = importlib.metadata.version("kilm")
        console.print(f"KiCad Library Manager (KiLM) version [cyan]{version}[/cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
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
    pass


# Register command apps (migrated to Typer)
app.add_typer(status_app, name="status", help="Show current library configuration")
app.add_typer(list_app, name="list", help="List available KiCad libraries")
app.add_typer(init_app, name="init", help="Initialize library configuration")
app.add_typer(pin_app, name="pin", help="Pin favorite libraries")

# TODO: Migrate remaining commands to Typer
# - setup: Configure KiCad to use libraries
# - unpin: Unpin favorite libraries
# - add-3d: Add 3D model libraries
# - config: Manage configuration settings
# - sync: Update/sync library content
# - update: Update KiLM itself
# - add-hook: Add project hooks
# - template: Manage project templates


if __name__ == "__main__":
    app()
