import typer

from .command import unpin

# Create Typer app and add the unpin command as callback
unpin_app = typer.Typer(
    name="unpin",
    help="Unpin libraries in KiCad for quick access",
    rich_markup_mode="rich",
    callback=unpin,
    invoke_without_command=True,
)

__all__ = ["unpin", "unpin_app"]
