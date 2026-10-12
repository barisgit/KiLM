"""The ``template make`` command: a template from an existing project."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

from kicad_lib_manager.services.config_service import Config, LibraryDict
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import (
    HOOKS_DIR,
    TEMPLATE_CONTENT_DIR,
    TEMPLATE_METADATA,
    TEMPLATES_DIR,
)
from kicad_lib_manager.utils.template.authoring import (
    create_template_metadata,
    create_template_structure,
)
from kicad_lib_manager.utils.template.constants import (
    MARKDOWN_EXT,
    POST_CREATE_HOOK,
    PROJECT_FILENAME_VARIABLE,
)
from kicad_lib_manager.utils.template.models import TemplateVariable
from kicad_lib_manager.utils.template.selection import (
    TemplatePlan,
    find_potential_variables,
    get_gitignore_spec,
    plan_template_files,
)

GITHUB_LIBRARY = "github"


@dataclass(frozen=True)
class TemplateTarget:
    """Where a new template comes from and goes to, with its descriptions."""

    name: str
    source: Path
    output: Path
    description: str | None
    use_case: str | None


def make(  # noqa: PLR0913 -- Typer maps each CLI option to one parameter
    name: Annotated[
        str | None, typer.Argument(help="Name of the template to create")
    ] = None,
    source_directory: Annotated[
        Path | None, typer.Argument(help="Source project directory")
    ] = None,
    *,
    description: Annotated[
        str | None, typer.Option(help="Template description")
    ] = None,
    use_case: Annotated[
        str | None, typer.Option("--use-case", help="Template use case description")
    ] = None,
    output_directory: Annotated[
        Path | None,
        typer.Option(
            "--output-directory", help="Directory where the template will be created"
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(help="Additional patterns to exclude (gitignore format)"),
    ] = None,
    variable: Annotated[
        list[str] | None,
        typer.Option(help="Define a template variable in name=value format"),
    ] = None,
    extends: Annotated[
        str | None, typer.Option(help="Parent template that this template extends")
    ] = None,
    non_interactive: Annotated[
        bool,
        typer.Option(
            "--non-interactive",
            help="Non-interactive mode (don't prompt for variables or configuration)",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be created without making changes"
        ),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing template if it exists")
    ] = False,
) -> None:
    r"""Create a template from an existing project.

    Creates a new KiCad project template from an existing project. If NAME
    is provided, it will be used as the template name. If SOURCE_DIRECTORY is
    provided, it will be used as the source project directory. Otherwise,
    the current directory will be used.

    By default, the command runs in interactive mode, automatically identifying
    potential template variables and prompting for confirmation. Use
    --non-interactive to disable prompts.

    Examples:
    \b
    # Create a template named 'basic-project' from the current directory
    kilm template make basic-project

    \b
    # Create a template from a specific directory
    kilm template make basic-project path/to/project

    \b
    # Create a template with a description and use case
    kilm template make basic-project --description "Basic KiCad project" \
        --use-case "Starting point for simple PCB designs"

    \b
    # Create a template with variables
    kilm template make basic-project --variable "author=John Doe"

    \b
    # Create a template without prompts
    kilm template make basic-project --non-interactive

    \b
    # Create a template that extends another template
    kilm template make advanced-project --extends basic-project
    """
    config = Config()
    libraries = config.get_libraries(library_type=GITHUB_LIBRARY)
    if not libraries:
        get_console().print(
            "No GitHub libraries configured. Use 'kilm init' to create one first."
        )
        raise typer.Exit(1)

    requested = TemplateTarget(
        name="" if name is None else name,
        source=Path.cwd() if source_directory is None else source_directory,
        output=Path() if output_directory is None else output_directory,
        description=description,
        use_case=use_case,
    )
    if non_interactive:
        target = _complete_without_prompts(
            config, requested, has_output=output_directory is not None
        )
    else:
        target = _complete_with_prompts(
            libraries,
            requested,
            has_source=source_directory is not None,
            has_output=output_directory is not None,
        )
    if target is None:
        return
    if target.output.exists() and not force:
        get_console().print(
            f"Template '{target.name}' already exists at {target.output}"
        )
        get_console().print("Use --force to overwrite.")
        return

    excludes = exclude or []
    _print_request(target, excludes, extends)
    variables = _parse_variables(variable or [])
    if not non_interactive:
        variables = {**_ask_variables(target.source), **variables}
    metadata = create_template_metadata(
        name=target.name,
        description=target.description,
        use_case=target.use_case,
        variables=variables,
        extends=extends,
    )
    gitignore_spec = get_gitignore_spec(target.source)
    if dry_run:
        _print_plan(
            plan_template_files(
                target.source,
                template_directory=target.output,
                gitignore_spec=gitignore_spec,
                additional_excludes=excludes or None,
            )
        )
        get_console().print("\nDry run complete. No changes were made.")
        return
    try:
        create_template_structure(
            target.source,
            target.output,
            metadata,
            gitignore_spec=gitignore_spec,
            additional_excludes=excludes or None,
        )
    except OSError as error:
        get_console(stderr=True).print(f"Error creating template: {error!s}")
        raise typer.Exit(1) from error
    _print_next_steps(target)


def _complete_with_prompts(
    libraries: list[LibraryDict],
    requested: TemplateTarget,
    *,
    has_source: bool,
    has_output: bool,
) -> TemplateTarget:
    """Ask for each part of the target that was not given on the command line."""
    source = requested.source
    if not has_source:
        answer = Path(
            str(typer.prompt("Source project directory", default=str(source)))
        )
        source = answer if answer.is_absolute() else Path.cwd() / answer
    name = requested.name or str(typer.prompt("Template name", default=source.name))
    description = requested.description
    if description is None or not description:
        description = str(
            typer.prompt("Template description", default=f"{name} template")
        )
    use_case = requested.use_case
    if use_case is None or not use_case:
        use_case = str(typer.prompt("Template use case", default=""))
    output = requested.output
    if not has_output:
        output = Path(_ask_library(libraries)) / TEMPLATES_DIR / name
        get_console().print(f"Template will be created in: {output}")
    return TemplateTarget(name, source, output, description, use_case)


def _ask_library(libraries: list[LibraryDict]) -> str:
    """Ask which library stores the template and return its path."""
    get_console().print("\nChoose a library to store the template:")
    for number, library in enumerate(libraries, start=1):
        get_console().print(f"{number}. {library['name']} ({library['path']})")
    while True:
        selection: object = typer.prompt("Select library (number)", type=int, default=1)
        if isinstance(selection, int) and 1 <= selection <= len(libraries):
            return libraries[selection - 1]["path"]
        get_console().print(f"Please enter a number between 1 and {len(libraries)}")


def _complete_without_prompts(
    config: Config, requested: TemplateTarget, *, has_output: bool
) -> TemplateTarget | None:
    """Default the name to the source directory and the output to the library.

    Returns None, after explaining why, when no library path is configured.
    """
    name = requested.name or requested.source.name
    output = requested.output
    if not has_output:
        library_path = config.get_symbol_library_path()
        if library_path is None or not library_path:
            get_console().print(
                "No library configured. Use 'kilm init' to create one first."
            )
            return None
        output = Path(library_path) / TEMPLATES_DIR / name
    return TemplateTarget(
        name, requested.source, output, requested.description, requested.use_case
    )


def _print_request(
    target: TemplateTarget, excludes: list[str], extends: str | None
) -> None:
    console = get_console()
    console.print(f"Creating template '{target.name}' from {target.source}")
    console.print(f"Output directory: {target.output}")
    if target.description is not None and target.description:
        console.print(f"Description: {target.description}")
    if target.use_case is not None and target.use_case:
        console.print(f"Use case: {target.use_case}")
    if excludes:
        console.print("Additional exclusions:")
        for pattern in excludes:
            console.print(f"  {pattern}")
    if extends is not None and extends:
        console.print(f"Extends: {extends}")


def _parse_variables(assignments: list[str]) -> dict[str, TemplateVariable]:
    """Parse ``--variable name=value`` options and show them."""
    variables: dict[str, TemplateVariable] = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        if separator:
            key = key.strip()
            variables[key] = TemplateVariable(
                description=f"Value for {key}", default=value.strip()
            )
    if variables:
        get_console().print("\nTemplate variables:")
        for key, info in variables.items():
            get_console().print(f"  {key}: {info['default']} - {info['description']}")
    return variables


def _ask_variables(source: Path) -> dict[str, TemplateVariable]:
    """Offer the values found in the source as variables, then ask for more."""
    variables: dict[str, TemplateVariable] = {}
    potential = find_potential_variables(source)
    if potential:
        get_console().print("\nFound potential template variables:")
    for var_name, values in potential.items():
        get_console().print(f"  {var_name}: {', '.join(values)}")
        if typer.confirm(f"  Use '{var_name}' as a template variable?", default=True):
            description = typer.prompt("  Description", default=f"Value for {var_name}")
            variables[var_name] = TemplateVariable(
                description=str(description), default=values[0]
            )
    while typer.confirm(
        "Would you like to define additional template variables?", default=False
    ):
        var_name = str(typer.prompt("Variable name"))
        default = str(typer.prompt("Default value", default=""))
        description = typer.prompt("Description", default=f"Value for {var_name}")
        variables[var_name] = TemplateVariable(
            description=str(description), default=default
        )
    return variables


def _print_plan(plan: TemplatePlan) -> None:
    """Show the files a dry run would include, template, and exclude."""
    console = get_console()
    included = sorted(str(path) for path in plan.files)
    console.print("\nFiles that will be included in the template:")
    for file in included:
        console.print(f"  + {file}")
    markdown = [file for file in included if file.lower().endswith(MARKDOWN_EXT)]
    if markdown:
        console.print("\nMarkdown files that will be converted to Jinja templates:")
        for file in markdown:
            console.print(f"  * {file}")
    if plan.main_files:
        console.print("\nKiCad project files that will be templated:")
        for kind, path in plan.main_files.items():
            console.print(f"  * {path} → %{{{PROJECT_FILENAME_VARIABLE}}}{kind.value}")
    console.print("\nFiles that will be excluded from the template:")
    for exclusion in sorted(exclusion.path for exclusion in plan.excluded):
        console.print(f"  - {exclusion}")


def _print_next_steps(target: TemplateTarget) -> None:
    console = get_console()
    console.print(f"\nTemplate '{target.name}' created successfully at {target.output}")
    console.print("\nNext steps:")
    console.print(
        f"1. Edit {target.output / TEMPLATE_METADATA} to customize template metadata"
    )
    console.print(
        f"2. Customize template files in {target.output / TEMPLATE_CONTENT_DIR}"
    )
    console.print(
        f"3. Edit post-creation hook in {target.output / HOOKS_DIR / POST_CREATE_HOOK}"
        " if needed"
    )
    console.print(
        "4. Use your template with:"
        f" kilm template create MyProject --template {target.name}"
    )
    console.print("\nFilename Templating:")
    console.print("For Windows compatibility, use %{variable} syntax in filenames:")
    console.print("  - %{project_name}.kicad_pro")
    console.print("  - %{project_name.lower}.kicad_sch")
    console.print("  - %{project_name.replace(' ', '-')}.kicad_pcb")
    console.print("  - %{project_name.upper.replace(' ', '_')}.md")
    console.print(
        "(Old {{variable}} syntax still works but may cause issues on Windows)"
    )
