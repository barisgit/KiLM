"""Making a template from an existing project, for ``template make``."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"pathspec"}

import shutil
from collections.abc import Mapping
from pathlib import Path, PurePath

import click
import pathspec

from kicad_lib_manager.utils.constants import HOOKS_DIR, TEMPLATE_CONTENT_DIR
from kicad_lib_manager.utils.template.constants import (
    MARKDOWN_EXT,
    MAX_TEMPLATE_PATH_LENGTH,
    PROJECT_FILENAME_VARIABLE,
)
from kicad_lib_manager.utils.template.hooks import create_hook_script
from kicad_lib_manager.utils.template.kicad_files import (
    process_kicad_pcb_file,
    process_kicad_project_file,
    process_kicad_schematic_file,
    process_markdown_file,
)
from kicad_lib_manager.utils.template.models import (
    TemplateMetadata,
    TemplateVariable,
    write_template_metadata,
)
from kicad_lib_manager.utils.template.selection import (
    MainFileKind,
    plan_template_files,
)

TEMPLATE_VERSION = "1.0.0"


def create_template_metadata(
    name: str,
    description: str | None = None,
    use_case: str | None = None,
    variables: Mapping[str, TemplateVariable] | None = None,
    extends: str | None = None,
) -> TemplateMetadata:
    """Build the metadata of a new template.

    Args:
        name: The template name.
        description: The description; defaults to one naming the template.
        use_case: When to use the template.
        variables: The template variables. ``project_name``,
            ``directory_name``, and ``project_filename`` are appended when no
            variable has that name, ignoring case.
        extends: The name of the parent template.

    Returns:
        The metadata, at version 1.0.0.
    """
    merged = {} if variables is None else dict(variables)
    present = {key.lower() for key in merged}
    for key, variable in _predefined_variables(name).items():
        if key not in present:
            merged[key] = variable
    metadata = TemplateMetadata(
        name=name,
        description=_or_default(description, f"KiCad project template for {name}"),
        use_case=_or_default(use_case, ""),
        version=TEMPLATE_VERSION,
        variables=merged,
    )
    if extends is not None and extends:
        metadata["extends"] = extends
    return metadata


def create_template_structure(
    source_directory: Path,
    template_directory: Path,
    metadata: TemplateMetadata,
    gitignore_spec: pathspec.PathSpec | None = None,
    additional_excludes: list[str] | None = None,
) -> None:
    """Write a template made from ``source_directory`` to ``template_directory``.

    Writes the metadata, the starting post-creation hook, and the files that
    ``plan_template_files`` selects. The main project, schematic, and PCB
    files are renamed after ``project_filename`` and turned into Jinja
    templates, as are Markdown files. Paths longer than 512 characters are
    skipped.
    """
    content_dir = template_directory / TEMPLATE_CONTENT_DIR
    hooks_dir = template_directory / HOOKS_DIR
    content_dir.mkdir(parents=True, exist_ok=True)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    write_template_metadata(template_directory, metadata)
    create_hook_script(hooks_dir)

    if gitignore_spec is not None:
        click.echo("Using .gitignore patterns for exclusion")
    click.echo("Scanning for main KiCad files...")
    plan = plan_template_files(
        source_directory,
        template_directory=template_directory,
        gitignore_spec=gitignore_spec,
        additional_excludes=additional_excludes,
    )
    for kind, path in plan.main_files.items():
        click.echo(f"Found main {kind.label} file: {path.name}")
    for exclusion in plan.excluded:
        click.echo(exclusion.message)

    skipped: set[PurePath] = set()
    for relative in plan.directories:
        target_dir = content_dir / relative
        if len(str(target_dir)) > MAX_TEMPLATE_PATH_LENGTH:
            click.echo(f"Skipping directory due to path length: {relative}")
            skipped.add(relative)
        else:
            target_dir.mkdir(parents=True, exist_ok=True)

    variables = metadata.get("variables", {})
    for relative in plan.files:
        if relative.parent in skipped:
            continue
        kind = plan.main_kind(relative)
        target = content_dir / relative
        if kind is not None:
            target = target.with_name(f"%{{{PROJECT_FILENAME_VARIABLE}}}{kind.value}")
        if len(str(target)) > MAX_TEMPLATE_PATH_LENGTH:
            click.echo(f"Skipping file due to path length: {relative}")
            continue
        _add_file(source_directory / relative, target, kind, variables)


def _add_file(
    source: Path,
    target: Path,
    kind: MainFileKind | None,
    variables: Mapping[str, TemplateVariable],
) -> None:
    """Copy one source file into the template, templating it when needed."""
    if kind is MainFileKind.PROJECT:
        process_kicad_project_file(source, target, variables)
    elif kind is MainFileKind.SCHEMATIC:
        process_kicad_schematic_file(source, target)
    elif kind is MainFileKind.PCB:
        process_kicad_pcb_file(source, target)
    elif source.name.lower().endswith(MARKDOWN_EXT):
        process_markdown_file(source, target, variables)
    else:
        try:
            shutil.copy2(source, target)
        except OSError as error:
            click.echo(f"Error copying file {source.name}: {error}", err=True)


def _predefined_variables(name: str) -> dict[str, TemplateVariable]:
    """The variables every template has, with their defaults."""
    return {
        "project_name": TemplateVariable(
            description="Project name (used in documentation and KiCad files)",
            default=name,
        ),
        "directory_name": TemplateVariable(
            description="Directory/repository name (used for folder structure)",
            default="%{project_name.lower.replace(' ', '-')}",
        ),
        PROJECT_FILENAME_VARIABLE: TemplateVariable(
            description="Main KiCad project filename (without extension)",
            default="%{project_name}",
        ),
    }


def _or_default(value: str | None, default: str) -> str:
    """Return ``value`` unless it is None or empty."""
    return default if value is None or not value else value
