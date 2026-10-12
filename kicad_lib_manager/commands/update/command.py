"""Registration of the `kilm update` subcommands."""

import typer

from kicad_lib_manager.commands.update.check import check_update_command
from kicad_lib_manager.commands.update.info import info_command
from kicad_lib_manager.commands.update.perform import perform_update_command

update_app = typer.Typer(
    name="update", help="Update KiLM CLI to the latest version", no_args_is_help=True
)
update_app.command("check")(check_update_command)
update_app.command("info")(info_command)
update_app.command("perform")(perform_update_command)
