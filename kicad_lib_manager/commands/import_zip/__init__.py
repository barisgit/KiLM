import typer

from .command import import_zip

import_zip_app = typer.Typer(
    name="import",
    help="Import SamacSys/Mouser/UltraLibrarian/SnapMagic KiCad ZIP(s) into the configured library",
    rich_markup_mode="rich",
    callback=import_zip,
    invoke_without_command=True,
)

__all__ = ["import_zip", "import_zip_app"]
