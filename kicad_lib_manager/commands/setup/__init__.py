import typer

from .command import setup

# Create Typer app and add the setup command as callback
setup_app = typer.Typer(
    name="setup",
    help="Configure KiCad to use libraries",
    rich_markup_mode="rich",
    callback=setup,
    invoke_without_command=True,
)

__all__ = ["setup", "setup_app"]
