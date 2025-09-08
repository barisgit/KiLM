import typer

from .command import update

update_app = typer.Typer(
    name="update",
    help="Update KiLM itself to the latest version",
    rich_markup_mode="rich",
    callback=update,
    invoke_without_command=True,
)

__all__ = ["update", "update_app"]
