"""Turning a source project's files into Jinja templates for ``template make``.

Each function writes ``<target>.jinja2``. When the source cannot be read or
the template cannot be written, the error is reported on stderr and the file
is copied unchanged instead.
"""

import json
import re
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

import click

from kicad_lib_manager.utils.template.constants import (
    JINJA_SUFFIX,
    KICAD_PROJECT_EXT,
    KICAD_SCHEMATIC_EXT,
    PROJECT_FILENAME_VARIABLE,
    PROJECT_NAME_VARIABLES,
)
from kicad_lib_manager.utils.template.models import TemplateVariable

PROJECT_FILENAME_TEMPLATE = f"{{{{ {PROJECT_FILENAME_VARIABLE} }}}}"
SCHEMATIC_PROJECT_PATTERN = re.compile(r'\(project\s+"([^"]+)"')
PCB_SHEETFILE_PATTERN = re.compile(r'\(sheetfile\s+"([^"]+)"')

# Wraps the variable list so that rendering a project removes it.
MARKDOWN_HEADER_START = (
    "{# This file is a Jinja template. The section below will be removed when"
    " creating a project. #}\n\n{% if false %}\n# Template Variables\n\n"
    "This template supports the following variables:\n\n"
)
MARKDOWN_HEADER_END = (
    "\nUse these variables in your content with `{{ variable_name }}`.\n{% endif %}\n"
)


def process_markdown_file(
    source_file: Path,
    target_file: Path,
    variables: Mapping[str, TemplateVariable],
) -> None:
    """Template a Markdown file, prefixing a removable list of the variables."""
    listing = "".join(
        f'- `{{ {name} }}`: {info["description"]} (default: "{info["default"]}")\n'
        for name, info in variables.items()
    )

    def add_header(content: str) -> str:
        return MARKDOWN_HEADER_START + listing + MARKDOWN_HEADER_END + content

    _write_template(source_file, target_file, "Markdown file", add_header)


def process_kicad_project_file(
    source_file: Path,
    target_file: Path,
    variables: Mapping[str, TemplateVariable],
) -> None:
    """Template a ``.kicad_pro`` file's ``meta.filename`` as the project filename.

    The filename is only templated when ``variables`` has a project name
    variable. A file that is not JSON is copied unchanged with a warning.
    """
    rename = any(name.lower() in PROJECT_NAME_VARIABLES for name in variables)

    def template_filename(content: str) -> str | None:
        try:
            project: object = json.loads(content)
        except json.JSONDecodeError:
            click.echo(
                f"Warning: Could not parse {source_file.name} as JSON."
                " Copying without changes."
            )
            return None
        if rename:
            project = _with_templated_filename(project)
        return json.dumps(project, indent=2)

    _write_template(source_file, target_file, "KiCad project file", template_filename)


def process_kicad_schematic_file(source_file: Path, target_file: Path) -> None:
    """Template the ``(project "...")`` references of a ``.kicad_sch`` file."""

    def template_project(content: str) -> str:
        click.echo(
            "  Templated schematic project name references with"
            f" '{PROJECT_FILENAME_TEMPLATE}'"
        )
        return SCHEMATIC_PROJECT_PATTERN.sub(
            f'(project "{PROJECT_FILENAME_TEMPLATE}"', content
        )

    _write_template(source_file, target_file, "KiCad schematic file", template_project)


def process_kicad_pcb_file(source_file: Path, target_file: Path) -> None:
    """Template the ``(sheetfile "...")`` references to the main schematic.

    A reference counts as the main schematic when its file name contains the
    PCB file's stem.
    """
    schematic = f"{PROJECT_FILENAME_TEMPLATE}{KICAD_SCHEMATIC_EXT}"

    def template_sheet(match: re.Match[str]) -> str:
        if source_file.stem in match.group(1):
            return f'(sheetfile "{schematic}"'
        return match.group(0)

    def template_sheets(content: str) -> str:
        click.echo(f"  Templated PCB sheet references with '{schematic}'")
        return PCB_SHEETFILE_PATTERN.sub(template_sheet, content)

    _write_template(source_file, target_file, "KiCad PCB file", template_sheets)


def _with_templated_filename(project: object) -> object:
    """Return ``project`` with ``meta.filename`` templated, if it has one."""
    if not isinstance(project, dict):
        return project
    fields = {str(key): value for key, value in project.items()}
    meta_value = fields.get("meta")
    if not isinstance(meta_value, dict):
        return project
    meta = {str(key): value for key, value in meta_value.items()}
    if "filename" not in meta:
        return project
    templated = f"{PROJECT_FILENAME_TEMPLATE}{KICAD_PROJECT_EXT}"
    click.echo(f"  Templated project filename: '{meta['filename']}' → '{templated}'")
    meta["filename"] = templated
    fields["meta"] = meta
    return fields


def _write_template(
    source_file: Path,
    target_file: Path,
    kind: str,
    transform: Callable[[str], str | None],
) -> None:
    """Write ``transform(source)`` to ``<target>.jinja2``.

    When ``transform`` returns None, or reading or writing fails, the source
    is copied to ``target_file`` unchanged.
    """
    target_template = target_file.with_name(target_file.name + JINJA_SUFFIX)
    try:
        content = transform(source_file.read_text(encoding="utf-8"))
        if content is not None:
            target_template.write_text(content, encoding="utf-8")
    except (OSError, UnicodeError) as error:
        click.echo(f"Error processing {kind} {source_file.name}: {error}", err=True)
        content = None
    if content is None:
        shutil.copy2(source_file, target_file)
        return
    click.echo(f"Processed {kind}: {source_file.name} → {target_template.name}")
