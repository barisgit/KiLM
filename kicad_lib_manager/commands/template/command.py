"""The ``template`` command group: create, make, and list project templates."""

import typer

from kicad_lib_manager.commands.template.create import create
from kicad_lib_manager.commands.template.listing import list_templates
from kicad_lib_manager.commands.template.make import make


def main_callback() -> None:
    """Manage KiCad project templates.

    This command group allows you to create new KiCad projects from templates,
    and create new templates from existing projects.
    """


template_app = typer.Typer(
    name="template",
    help="Manage KiCad project templates",
    rich_markup_mode="rich",
    callback=main_callback,
    invoke_without_command=True,
    no_args_is_help=True,
)
template_app.command("create", help="Create a new KiCad project from a template")(
    create
)
template_app.command("make", help="Create a template from an existing project")(make)
template_app.command("list", help="List all available templates")(list_templates)
