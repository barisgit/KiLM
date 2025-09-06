import typer

from .command import status

# Create Typer app and add the status command as callback
status_app = typer.Typer(
    name="status",
    help="Show current library configuration status",
    rich_markup_mode="rich",
    callback=status,
    invoke_without_command=True,
)

__all__ = ["status", "status_app"]
