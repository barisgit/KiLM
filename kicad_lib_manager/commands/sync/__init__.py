import typer

from .command import sync

# Create Typer app and add the sync command as callback
sync_app = typer.Typer(
    name="sync",
    help="Update/sync library content from git repositories",
    rich_markup_mode="rich",
    callback=sync,
    invoke_without_command=True,
)

__all__ = ["sync", "sync_app"]
