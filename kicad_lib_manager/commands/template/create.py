"""The ``template create`` command: a new project from a template."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"questionary"}

import json
import os
import shutil
from pathlib import Path
from typing import Annotated

import questionary
import typer

from kicad_lib_manager.commands.shared import parse_assignments
from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import TEMPLATE_CONTENT_DIR
from kicad_lib_manager.utils.template.discovery import find_all_templates
from kicad_lib_manager.utils.template.models import (
    DiscoveredTemplate,
    TemplateVariable,
)
from kicad_lib_manager.utils.template.project import create_project_from_template
from kicad_lib_manager.utils.template.rendering import (
    contains_template_syntax,
    render_template_string,
)

PROJECT_NAME = "project_name"
DIRECTORY_NAME = "directory_name"
MAX_LISTED_OLD_SYNTAX_FILES = 3


def create(  # noqa: PLR0913 -- Typer maps each CLI option to one parameter
    name: Annotated[
        str | None, typer.Argument(help="Name of the project to create")
    ] = None,
    directory: Annotated[
        str | None, typer.Argument(help="Directory to create project in")
    ] = None,
    *,
    template: Annotated[
        str | None, typer.Option(help="Name of the template to use")
    ] = None,
    library: Annotated[
        str | None, typer.Option(help="Name of the library containing the template")
    ] = None,
    set_var: Annotated[
        list[str] | None,
        typer.Option("--set-var", help="Set template variable in key=value format"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be created without making changes"
        ),
    ] = False,
    skip_hooks: Annotated[
        bool, typer.Option("--skip-hooks", help="Skip post-creation hooks")
    ] = False,
) -> None:
    """Create a KiCad project from a template in one of the configured libraries.

    The project goes into a subdirectory of DIRECTORY (default: the working
    directory), named by the ``directory_name`` variable or derived from the
    project name. A NAME with a path separator gives both the parent directory
    and the name. Variables not set by NAME or ``--set-var`` are prompted for.
    """
    templates = find_all_templates(Config(), library)
    if not templates:
        where = (
            "any configured libraries" if library is None else f"library '{library}'"
        )
        get_console().print(f"No templates found in {where}.")
        get_console().print("Use 'kilm template make' to create a template first.")
        return

    name, base_directory = _split_name_and_directory(name, directory)
    selected = _select_template(templates, template)
    if selected is None:
        return
    variables = _collect_variables(selected, name, set_var or [])
    if variables is None:
        return
    get_console().print()
    get_console().print(f"Final variables: {json.dumps(variables, indent=2)}")

    project_dir = _target_directory(
        base_directory, selected, variables, dry_run=dry_run
    )
    if project_dir is None:
        return
    if os.name == "nt":
        _warn_old_filename_syntax(Path(selected["path"]) / TEMPLATE_CONTENT_DIR)
    try:
        success = create_project_from_template(
            selected, project_dir, variables, dry_run=dry_run, skip_hooks=skip_hooks
        )
    except OSError as error:
        get_console(stderr=True).print(f"Error during project creation: {error}")
        success = False
    if not success:
        get_console().print()
        get_console(stderr=True).print("Project creation failed.")
    elif not dry_run:
        get_console().print()
        get_console().print(
            f"Project '{variables.get(PROJECT_NAME, name)}' created successfully"
            f" in '{project_dir}'"
        )


def _split_name_and_directory(
    name: str | None, directory: str | None
) -> tuple[str | None, Path]:
    """Resolve the NAME and DIRECTORY arguments into a name and a parent directory.

    A NAME with a path separator is split into its parent and last part; a
    DIRECTORY without a NAME is split the same way. The parent defaults to
    the working directory.
    """
    if name is not None and os.path.sep in name:
        path = Path(name)
        directory, name = str(path.parent), path.name
    if directory is not None and directory and (name is None or not name):
        path = Path(directory)
        name, directory = path.name, str(path.parent)
    if directory is None or not directory:
        return name, Path.cwd()
    return name, Path(directory)


def _select_template(
    templates: dict[str, DiscoveredTemplate], requested: str | None
) -> DiscoveredTemplate | None:
    """Return the requested template, matched case-insensitively, or ask for one.

    Returns None, after explaining why, when the template does not exist or
    the selection is cancelled.
    """
    if requested is None:
        choices = [
            questionary.Choice(title=_describe(name, data), value=name)
            for name, data in templates.items()
        ]
        answer: object = questionary.select(
            "Select template:", choices=choices, use_shortcuts=True
        ).ask()
        if not isinstance(answer, str):
            get_console().print("Template selection cancelled.")
            return None
        return templates[answer]
    if requested in templates:
        return templates[requested]
    wanted = requested.lower()
    for name, data in templates.items():
        if name.lower() == wanted:
            return data
    get_console().print(f"Template '{requested}' not found.")
    get_console().print("Available templates:")
    for name, data in templates.items():
        get_console().print(
            f"  {name} ({data['source_library']}): {data.get('description', '')}"
        )
    return None


def _describe(name: str, data: DiscoveredTemplate) -> str:
    return f"{name} ({data['source_library']}) - {data.get('description', '')}"


def _collect_variables(
    template: DiscoveredTemplate, name: str | None, assignments: list[str]
) -> dict[str, str] | None:
    """Gather the variable values, prompting for each one not given.

    NAME sets ``project_name`` unless ``--set-var`` does. A prompt's default is
    rendered with the values gathered before it. Returns None when a prompt
    is cancelled.
    """
    from_options = parse_assignments(assignments)
    variables: dict[str, str] = {}
    name_given = name is not None and bool(name) and PROJECT_NAME not in from_options
    if name is not None and name_given:
        variables[PROJECT_NAME] = name
    variables.update(from_options)

    console = get_console()
    console.print()
    console.print(f"Using Template: {template['name']}")
    console.print(f"Description: {template.get('description', 'N/A')}")
    use_case = template.get("use_case", "")
    if use_case:
        console.print(f"Use case: {use_case}")
    console.print()
    console.print("Template Variables:")

    for var_name, info in template.get("variables", {}).items():
        description = info["description"]
        if var_name in variables:
            source = (
                "argument" if var_name == PROJECT_NAME and name_given else "--set-var"
            )
            console.print(
                f"  {var_name}: {variables[var_name]} (from {source}) - {description}"
            )
            continue
        default = info["default"]
        if contains_template_syntax(default):
            default = render_template_string(default, variables)
        answer: object = questionary.text(
            f"{var_name} ({description})", default=default
        ).ask()
        if not isinstance(answer, str):
            console.print("Variable input cancelled.")
            return None
        variables[var_name] = answer
    return variables


def _target_directory(
    base: Path,
    template: DiscoveredTemplate,
    variables: dict[str, str],
    *,
    dry_run: bool,
) -> Path | None:
    """Announce the project directory and, unless dry-running, prepare it.

    Returns None, after explaining why, when there is no directory to use.
    """
    project_dir = _project_directory(base, template.get("variables", {}), variables)
    if project_dir is None:
        get_console(stderr=True).print(
            "Error: Cannot determine project directory. Ensure 'project_name' or"
            " 'directory_name' variable is properly handled."
        )
        return None
    get_console().print()
    get_console().print(f"Project will be created in: {project_dir}")
    if dry_run:
        get_console().print("Dry run enabled. No changes will be made.")
    elif not _prepare_project_directory(project_dir):
        return None
    return project_dir


def _project_directory(
    base: Path,
    template_variables: dict[str, TemplateVariable],
    variables: dict[str, str],
) -> Path | None:
    """Choose the project directory inside ``base``.

    Uses ``directory_name`` when it differs from its unrendered default, else
    the rendered Jinja default, else ``project_name`` lower-cased with dashes.
    """
    declared = template_variables.get(DIRECTORY_NAME)
    template_default = "" if declared is None else declared["default"]
    value = variables.get(DIRECTORY_NAME, "")
    if value and value != template_default:
        return base / value
    if "{{" in template_default:
        return base / render_template_string(template_default, variables)
    project_name = variables.get(PROJECT_NAME)
    if project_name is None:
        return None
    project_dir = base / project_name.lower().replace(" ", "-")
    get_console().print(f"Using project_name to determine directory: {project_dir}")
    return project_dir


def _prepare_project_directory(project_dir: Path) -> bool:
    """Remove an existing project directory, after confirmation; create its parents.

    Returns False, after explaining why, when the user declines or the
    directories cannot be changed.
    """
    if project_dir.exists():
        if not typer.confirm(f"Directory '{project_dir}' already exists. Overwrite?"):
            get_console().print("Aborted.")
            return False
        get_console().print(f"Removing existing directory: {project_dir}")
        try:
            shutil.rmtree(project_dir)
        except OSError as error:
            get_console(stderr=True).print(
                f"Error removing existing directory: {error}"
            )
            return False
    try:
        project_dir.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        get_console(stderr=True).print(
            f"Error creating parent directories for {project_dir}: {error}"
        )
        return False
    return True


def _warn_old_filename_syntax(content_dir: Path) -> None:
    """Warn on Windows when template file names use ``{{variable}}`` syntax."""
    old_syntax = [
        file.name
        for file in content_dir.rglob("*")
        if file.is_file() and "{{" in file.name and "}}" in file.name
    ]
    if not old_syntax:
        return
    console = get_console()
    errors = get_console(stderr=True)
    console.print()
    errors.print("WARNING: Windows Compatibility Notice:")
    errors.print(
        "This template uses the old {{variable}} syntax in filenames, which may"
        " not work on Windows."
    )
    errors.print(
        "Consider updating the template to use the new Windows-compatible"
        " %{variable} syntax."
    )
    errors.print("Files with old syntax:")
    for file_name in old_syntax[:MAX_LISTED_OLD_SYNTAX_FILES]:
        errors.print(f"  - {file_name}")
    if len(old_syntax) > MAX_LISTED_OLD_SYNTAX_FILES:
        errors.print(f"  ... and {len(old_syntax) - MAX_LISTED_OLD_SYNTAX_FILES} more")
    console.print()
    errors.print("New syntax examples:")
    errors.print("  - %{project_name}.kicad_pro")
    errors.print("  - %{project_name.lower}.kicad_sch")
    errors.print("  - %{project_name.replace(' ', '-')}.kicad_pcb")
    console.print()
