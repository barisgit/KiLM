import typer

from .command import list_cmd

# Create Typer app and add the list command as callback
list_app = typer.Typer(
    name="list",
    help="List available KiCad libraries",
    rich_markup_mode="rich",
    callback=list_cmd,
    invoke_without_command=True,
)

__all__ = ["list_cmd", "list_app"]
