"""
Update command group for KiCad Library Manager.
Contains subcommands for checking, showing info, and performing updates.
"""

import typer

from .check import check_update_command
from .info import info_command
from .perform import perform_update_command

# Create the update command group
update_app = typer.Typer(
    name="update", help="Update KiLM CLI to the latest version", no_args_is_help=True
)

# Register subcommands
update_app.command("check")(check_update_command)
update_app.command("info")(info_command)
update_app.command("perform")(perform_update_command)
