"""The ``kilm`` command line: the Typer app and its command registry."""

import importlib.metadata
import logging
from typing import Annotated

import click
import typer
from rich.align import Align
from rich.text import Text
from typer.core import TyperGroup
from typing_extensions import override

from kicad_lib_manager.commands.add_3d import add_3d
from kicad_lib_manager.commands.add_hook import add_hook
from kicad_lib_manager.commands.config import config_app
from kicad_lib_manager.commands.import_zip import import_zip
from kicad_lib_manager.commands.init import init
from kicad_lib_manager.commands.list_libraries import list_cmd
from kicad_lib_manager.commands.pin import pin
from kicad_lib_manager.commands.setup import setup
from kicad_lib_manager.commands.status import status
from kicad_lib_manager.commands.sync import sync
from kicad_lib_manager.commands.template import template_app
from kicad_lib_manager.commands.unpin import unpin
from kicad_lib_manager.commands.update import update_app
from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.services.update_service import UpdateService
from kicad_lib_manager.utils.banner import show_banner
from kicad_lib_manager.utils.console import get_console

TAGLINE = "Professional KiCad library management"

logger = logging.getLogger(__name__)


def _show_title() -> None:
    """Print the centered banner and tagline."""
    console = get_console()
    show_banner(console, justify="center")
    console.print()
    console.print(Align.center(Text(TAGLINE, style="italic bright_yellow")))
    console.print()


def _check_for_updates_if_needed() -> None:
    """Show a notice when a newer KiLM is available, unless disabled.

    Both branches answer from the day-long PyPI cache and refresh it from
    PyPI once it has expired; a check the configured frequency calls for is
    recorded once it has run, update found or not. Any failure is logged
    at debug level and ignored, because an update check must never break the
    command the user ran.
    """
    try:
        config = Config()
        enabled = config.get("update_check", True)
        if enabled is None or not enabled:
            return
        update_service = UpdateService(importlib.metadata.version("kilm"))
        if config.should_check_updates():
            update_service.show_update_notification(quiet=True, stderr=True)
            config.mark_update_check_performed()
        elif update_service.check_for_updates(use_cache=True)["has_update"]:
            update_service.show_update_notification(quiet=True, stderr=True)
    except Exception:
        logger.debug("Update check failed", exc_info=True)


class BannerGroup(TyperGroup):
    """Root command group that prints the banner above its help."""

    @override
    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Print the banner, then the regular help.

        The update check is deliberately left out: help output must not
        depend on the network or on the cache being fresh.
        """
        _show_title()
        super().format_help(ctx, formatter)


app = typer.Typer(
    name="kilm",
    help=(
        "KiCad Library Manager - Manage KiCad libraries across projects and "
        "workstations"
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    invoke_without_command=True,
    cls=BannerGroup,
)


def version_callback(*, value: bool) -> None:
    """Print the banner and installed version, then exit, when ``value`` is set."""
    if not value:
        return
    console = get_console()
    show_banner(console, justify="left")
    console.print()
    version = importlib.metadata.version("kilm")
    console.print(f"KiCad Library Manager (KiLM) version [cyan]{version}[/cyan]")
    raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    *,
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
    """Show the banner when no command is given; otherwise check for updates.

    The root help text comes from the ``help`` argument of ``app``, not from
    this docstring.
    """
    if ctx.invoked_subcommand is not None:
        _check_for_updates_if_needed()
        return
    _show_title()
    get_console().print(
        "[dim]Use 'kilm --help' to see all commands.[/dim]", justify="center"
    )


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
    help=(
        "Import SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP(s) into the library"
    ),
)(import_zip)
# Groups keep their subcommands.
app.add_typer(config_app, name="config", help="Manage configuration settings")
app.add_typer(template_app, name="template", help="Manage project templates")
app.add_typer(update_app, name="update", help="Update KiLM itself")


if __name__ == "__main__":
    app()
