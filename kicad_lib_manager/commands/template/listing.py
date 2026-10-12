"""The ``template list`` command."""

import json
from typing import Annotated

import typer
from rich.panel import Panel
from rich.table import Table

from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.template.discovery import find_all_templates
from kicad_lib_manager.utils.template.models import DiscoveredTemplate

MAX_LISTED_VARIABLES = 3
NONE_MARKUP = "[dim]None[/dim]"


def list_templates(
    library: Annotated[
        str | None, typer.Option(help="Filter templates by library name")
    ] = None,
    *,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v", "--verbose", help="Show detailed information including variables"
        ),
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output in JSON format")
    ] = False,
) -> None:
    r"""List all available templates.

    Displays all available templates across all configured libraries,
    with their descriptions, source libraries, and other metadata.

    Examples:
    \b
    # List all templates
    kilm template list

    \b
    # List templates with detailed information
    kilm template list --verbose

    \b
    # List templates from a specific library
    kilm template list --library my-library

    \b
    # Output template list in JSON format
    kilm template list --json
    """
    templates = find_all_templates(Config(), library)
    if not templates:
        _print_no_templates(library)
        return
    if json_output:
        # Plain echo: a Rich console would wrap long values and break the JSON.
        typer.echo(json.dumps(templates, indent=2))
        return

    by_library: dict[str, list[tuple[str, DiscoveredTemplate]]] = {}
    for name, data in templates.items():
        by_library.setdefault(data["source_library"], []).append((name, data))
    console = get_console()
    console.print()
    for library_name, library_templates in by_library.items():
        console.print(_library_table(library_name, library_templates, verbose=verbose))
        console.print()
    console.print(
        Panel(
            "[cyan]Usage:[/cyan] kilm template create <name> --template"
            " <template_name>\n"
            "[cyan]Verbose:[/cyan] kilm template list --verbose\n"
            "[cyan]Filter:[/cyan] kilm template list --library <library_name>",
            title="[bold blue]Quick Tips[/bold blue]",
            border_style="blue",
        )
    )
    console.print(
        Panel(
            f"[green]Libraries:[/green] {len(by_library)}\n"
            f"[green]Templates:[/green] {len(templates)}",
            title="[bold cyan]Summary[/bold cyan]",
            border_style="cyan",
            width=30,
        )
    )


def _print_no_templates(library: str | None) -> None:
    """Explain that there are no templates and what to do about it."""
    get_console().print()
    if library is not None:
        panel = Panel(
            f"[yellow]No templates found in library '[cyan]{library}[/cyan]'."
            "[/yellow]\n\n"
            "[cyan]Try:[/cyan]\n"
            "• List all libraries: [blue]kilm config list[/blue]\n"
            "• Create a template: [blue]kilm template make[/blue]\n"
            "• List all templates: [blue]kilm template list[/blue]",
            title="[bold yellow]No Templates Found[/bold yellow]",
            border_style="yellow",
        )
    else:
        panel = Panel(
            "[yellow]No templates found in any configured libraries.[/yellow]\n\n"
            "[cyan]Get Started:[/cyan]\n"
            "• Create a template: [blue]kilm template make[/blue]\n"
            "• Check library configuration: [blue]kilm config list[/blue]",
            title="[bold yellow]No Templates[/bold yellow]",
            border_style="yellow",
        )
    get_console().print(panel)


def _library_table(
    library_name: str,
    templates: list[tuple[str, DiscoveredTemplate]],
    *,
    verbose: bool,
) -> Table:
    """Build the table of one library's templates, sorted by name."""
    table = Table(
        title=f"[bold cyan]{library_name}[/bold cyan] Templates",
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
    )
    table.add_column("Template", style="cyan", no_wrap=True)
    table.add_column("Version", justify="center", style="blue", width=8)
    table.add_column("Description", style="green")
    if verbose:
        table.add_column("Variables", style="yellow", max_width=30)
        table.add_column("Extends", style="magenta", max_width=15)
    for name, data in sorted(templates, key=lambda item: item[0]):
        row = [
            f"[bold]{name}[/bold]",
            data.get("version", "1.0.0"),
            data.get("description", "No description"),
        ]
        if verbose:
            extends = data.get("extends", "")
            row += [_variables_summary(data), extends or NONE_MARKUP]
        table.add_row(*row)
    return table


def _variables_summary(template: DiscoveredTemplate) -> str:
    """Name the first variables of a template and count the rest."""
    names = list(template.get("variables", {}))
    if not names:
        return NONE_MARKUP
    summary = ", ".join(names[:MAX_LISTED_VARIABLES])
    if len(names) > MAX_LISTED_VARIABLES:
        summary += f", +{len(names) - MAX_LISTED_VARIABLES} more"
    return summary
