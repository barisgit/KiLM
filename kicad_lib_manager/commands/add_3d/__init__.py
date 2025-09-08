import typer

from .command import add_3d

add_3d_app = typer.Typer(
    name="add-3d",
    help="Add cloud-based 3D model libraries to KiCad configuration",
    rich_markup_mode="rich",
    callback=add_3d,
    invoke_without_command=True,
)

__all__ = ["add_3d", "add_3d_app"]
