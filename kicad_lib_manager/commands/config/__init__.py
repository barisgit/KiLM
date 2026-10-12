"""The `kilm config` command group."""

import typer

from kicad_lib_manager.commands.config.command import list_config, remove, set_default

config_app = typer.Typer(
    name="config",
    help="Manage KiCad Library Manager configuration",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

config_app.command("list", help="List all configured libraries in kilm")(list_config)
config_app.command("set-default", help="Set a library as the default for operations")(
    set_default
)
config_app.command("remove", help="Remove a library from the configuration")(remove)

__all__ = ["config_app", "list_config", "remove", "set_default"]
