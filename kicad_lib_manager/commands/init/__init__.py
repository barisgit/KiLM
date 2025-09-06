import typer

from .command import init

# Create Typer app and add the init command as callback
init_app = typer.Typer(
    name="init",
    help="Initialize library configuration",
    rich_markup_mode="rich",
    callback=init,
    invoke_without_command=True,
)

__all__ = ["init", "init_app"]
