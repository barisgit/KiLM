import typer

from .command import add_hook

# Create Typer app and add the add_hook command as callback
add_hook_app = typer.Typer(
    name="add-hook",
    help="Add a Git post-merge hook to automatically sync KiCad libraries",
    rich_markup_mode="rich",
    callback=add_hook,
    invoke_without_command=True,
)

__all__ = ["add_hook", "add_hook_app"]
