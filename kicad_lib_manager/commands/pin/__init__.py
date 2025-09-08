import typer

from .command import pin

# Create Typer app and add the pin command as callback
pin_app = typer.Typer(
    name="pin",
    help="Pin favorite libraries",
    rich_markup_mode="rich",
    callback=pin,
    invoke_without_command=True,
)

__all__ = ["pin", "pin_app"]
