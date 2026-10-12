"""Creating a project from a template, for ``template create``."""

import os
import traceback
from pathlib import Path
from typing import NamedTuple

import click

from kicad_lib_manager.utils.constants import HOOKS_DIR, TEMPLATE_CONTENT_DIR
from kicad_lib_manager.utils.template.constants import (
    BINARY_EXTENSIONS,
    JINJA_SUFFIX,
    POST_CREATE_HOOK,
    SYSTEM_FILES_TO_IGNORE,
)
from kicad_lib_manager.utils.template.hooks import run_post_create_hook
from kicad_lib_manager.utils.template.models import (
    DiscoveredTemplate,
    RenderVariables,
)
from kicad_lib_manager.utils.template.rendering import (
    render_filename,
    render_template_file,
)


class PlannedFile(NamedTuple):
    """A template file and the project file it renders to."""

    source: Path
    target: Path
    is_binary: bool


class ProjectPlan(NamedTuple):
    """The directories and files a template creates, in template walk order."""

    directories: list[Path]
    files: list[PlannedFile]


def create_project_from_template(
    template: DiscoveredTemplate,
    project_dir: Path,
    variables: RenderVariables,
    *,
    dry_run: bool = False,
    skip_hooks: bool = False,
) -> bool:
    """Render a template into ``project_dir`` and run its post-creation hook.

    A non-empty ``project_dir`` is merged into, with a warning. A dry run only
    prints the directories and files that would be created.

    Returns:
        False when the template has no content directory, otherwise True.
        Files that fail to render and hooks that fail are reported on stderr.
    """
    template_dir = Path(template["path"])
    content_dir = template_dir / TEMPLATE_CONTENT_DIR
    if not content_dir.is_dir():
        click.echo(
            f"Error: Template content directory {content_dir} does not exist",
            err=True,
        )
        return False
    if not dry_run and project_dir.is_dir() and any(project_dir.iterdir()):
        click.echo(f"Warning: Target directory {project_dir} is not empty", err=True)
    extends = template.get("extends")
    if extends is not None and extends:
        click.echo("Warning: Template inheritance not fully implemented yet", err=True)

    plan = plan_project(content_dir, project_dir, variables)
    if dry_run:
        _print_plan(plan)
        return True

    for directory in plan.directories:
        directory.mkdir(parents=True, exist_ok=True)
    for planned in plan.files:
        if not render_template_file(
            planned.source, planned.target, variables, is_binary=planned.is_binary
        ):
            click.echo(f"Warning: Failed to create {planned.target}", err=True)
    if not skip_hooks:
        _run_hook(
            template_dir / HOOKS_DIR / POST_CREATE_HOOK,
            project_dir,
            variables,
            template,
        )
    return True


def plan_project(
    content_dir: Path, project_dir: Path, variables: RenderVariables
) -> ProjectPlan:
    """Map a template's content directory onto ``project_dir``.

    Directory and file names are rendered with ``variables``, the ``.jinja2``
    suffix is dropped, and system files such as ``.DS_Store`` are skipped.
    """
    plan = ProjectPlan(directories=[], files=[])
    for root, _directories, names in os.walk(content_dir):
        relative = Path(root).relative_to(content_dir)
        target_dir = project_dir
        if relative.parts:
            target_dir = project_dir / render_filename(str(relative), variables)
            plan.directories.append(target_dir)
        for name in names:
            if name in SYSTEM_FILES_TO_IGNORE:
                continue
            target_name = name.removesuffix(JINJA_SUFFIX)
            plan.files.append(
                PlannedFile(
                    source=Path(root) / name,
                    target=target_dir / render_filename(target_name, variables),
                    is_binary=target_name.lower().endswith(tuple(BINARY_EXTENSIONS)),
                )
            )
    return plan


def _print_plan(plan: ProjectPlan) -> None:
    """Show what a dry run would create."""
    for directory in plan.directories:
        click.echo(f"Would create directory: {directory}")
    click.echo()
    click.echo("The following files would be created:")
    for planned in plan.files:
        click.echo(f"  {planned.target}")


def _run_hook(
    hook_script: Path,
    project_dir: Path,
    variables: RenderVariables,
    template: DiscoveredTemplate,
) -> None:
    """Run the template's post-creation hook, reporting any failure."""
    if not hook_script.exists():
        return
    try:
        run_post_create_hook(hook_script, project_dir, variables, template)
    except Exception as error:  # noqa: BLE001 -- the hook is template code and may raise anything
        click.echo(f"Error running post-creation hook: {error}", err=True)
        traceback.print_exc()
