import typer

from .command import create, list_templates, main_callback, make

# Create Typer app with subcommands
template_app = typer.Typer(
    name="template",
    help="Manage KiCad project templates",
    rich_markup_mode="rich",
    callback=main_callback,
    invoke_without_command=True,
    no_args_is_help=True,
)

# Add subcommands
template_app.command("create", help="Create a new KiCad project from a template")(
    create
)
template_app.command("make", help="Create a template from an existing project")(make)
template_app.command("list", help="List all available templates")(list_templates)

__all__ = ["template_app", "create", "make", "list_templates"]
