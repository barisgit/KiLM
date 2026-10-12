"""Rendering of template file names and file contents with template variables.

File names use the Windows-compatible ``%{variable.transform}`` placeholders
that ``render_filename_custom`` expands; the Jinja2 ``{{ variable }}`` syntax
still works in file names and is the syntax of content files ending in
``.jinja2``. Rendering problems are reported on stderr and leave the text
unrendered rather than failing the whole project.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"jinja2"}

import re
import shutil
from pathlib import Path

import click
import jinja2

from kicad_lib_manager.utils.template.constants import (
    FILENAME_VAR_PATTERN,
    JINJA_SUFFIX,
)
from kicad_lib_manager.utils.template.models import RenderVariables

REPLACE_PREFIX = "replace("


def contains_template_syntax(text: str) -> bool:
    """Whether ``text`` holds a ``%{...}`` or ``{{ ... }}`` placeholder."""
    return bool(FILENAME_VAR_PATTERN.search(text)) or ("{{" in text and "}}" in text)


def render_template_string(template_str: str, variables: RenderVariables) -> str:
    """Render ``template_str``, preferring the ``%{...}`` syntax over Jinja2.

    Undefined Jinja2 variables render as empty text. On a Jinja2 error the
    warning goes to stderr and ``template_str`` is returned unchanged.
    """
    if FILENAME_VAR_PATTERN.search(template_str):
        return render_filename_custom(template_str, variables)
    try:
        return _environment().from_string(template_str).render(**variables)
    except jinja2.TemplateError as error:
        click.echo(f"Warning: Failed to render template: {error}", err=True)
        return template_str


def render_filename_custom(filename: str, variables: RenderVariables) -> str:
    """Expand the Windows-compatible ``%{variable}`` placeholders in ``filename``.

    A placeholder may chain transformations after the variable name:

    - ``%{project_name.lower}`` and ``%{project_name.upper}`` change case.
    - ``%{project_name.replace(' ', '-')}`` replaces text.
    - ``%{project_name.replace(' ', '_').lower}`` applies both in order.

    A placeholder naming an unknown variable stays as written; unknown or
    malformed transformations are skipped. Both are reported on stderr.
    """
    return FILENAME_VAR_PATTERN.sub(
        lambda match: _expand_placeholder(match, variables), filename
    )


def render_filename(filename: str, variables: RenderVariables) -> str:
    """Render a file or directory name from a template.

    ``%{...}`` placeholders take precedence; otherwise ``{{ ... }}`` is rendered
    with Jinja2, where an undefined variable is an error. On an error the
    warning goes to stderr and ``filename`` is returned unchanged.
    """
    if FILENAME_VAR_PATTERN.search(filename):
        return render_filename_custom(filename, variables)
    if "{{" not in filename or "}}" not in filename:
        return filename
    try:
        return _environment(strict=True).from_string(filename).render(**variables)
    except jinja2.TemplateError as error:
        click.echo(f"Warning: Failed to render filename {filename}: {error}", err=True)
        return filename


def render_template_file(
    source_file: Path,
    target_file: Path,
    variables: RenderVariables,
    *,
    is_binary: bool = False,
) -> bool:
    """Write ``source_file`` to ``target_file``, rendering it if it is a template.

    Binary files are copied. Text files whose name ends in ``.jinja2`` are
    rendered with Jinja2, where an undefined variable is an error, and written
    without that suffix; other text files are copied. When reading or rendering
    fails, the source is copied unchanged.

    Returns:
        False when the file was not rendered as intended or could not be
        written at all, True otherwise.
    """
    target_file.parent.mkdir(parents=True, exist_ok=True)
    if is_binary:
        return _copy(source_file, target_file, "binary file")
    if not source_file.name.endswith(JINJA_SUFFIX):
        return _copy(source_file, target_file, "file")
    try:
        content = source_file.read_text(encoding="utf-8")
        environment = _environment(
            strict=True, loader=jinja2.FileSystemLoader(source_file.parent)
        )
        rendered = environment.from_string(content).render(**variables)
    except jinja2.TemplateError as error:
        click.echo(f"Error rendering template {source_file.name}: {error}", err=True)
        _copy(source_file, target_file, "file")
        return False
    except (OSError, UnicodeDecodeError) as error:
        click.echo(f"Error processing file {source_file}: {error}", err=True)
        return _copy(source_file, target_file, "file")
    rendered_file = Path(str(target_file).removesuffix(JINJA_SUFFIX))
    try:
        rendered_file.write_text(rendered, encoding="utf-8")
    except OSError as error:
        click.echo(f"Error processing file {source_file}: {error}", err=True)
        return _copy(source_file, target_file, "file")
    return True


def _environment(
    *, strict: bool = False, loader: jinja2.BaseLoader | None = None
) -> jinja2.Environment:
    """Return a Jinja2 environment for plain-text output.

    Autoescaping stays off: the output is KiCad files, text, and file names, so
    HTML escaping would turn a value such as ``R&D`` into ``R&amp;D``.
    """
    return jinja2.Environment(
        loader=loader,
        undefined=jinja2.StrictUndefined if strict else jinja2.Undefined,
        autoescape=False,  # noqa: S701 -- output is KiCad files and text, never HTML
    )


def _copy(source_file: Path, target_file: Path, kind: str) -> bool:
    """Copy ``source_file`` unchanged, reporting a failure on stderr."""
    try:
        shutil.copy2(source_file, target_file)
    except OSError as error:
        click.echo(f"Error copying {kind} {source_file}: {error}", err=True)
        return False
    return True


def _expand_placeholder(match: re.Match[str], variables: RenderVariables) -> str:
    """Return the value of one ``%{variable.transform...}`` placeholder."""
    name, *transformations = match.group(1).split(".")
    name = name.strip()
    if name not in variables:
        click.echo(
            f"Warning: Variable '{name}' not found in template variables", err=True
        )
        return match.group(0)
    value = str(variables[name])
    for transformation in transformations:
        value = _transform(value, transformation.strip())
    return value


def _transform(value: str, transformation: str) -> str:
    if transformation == "lower":
        return value.lower()
    if transformation == "upper":
        return value.upper()
    if transformation.startswith(REPLACE_PREFIX):
        return _replace(value, transformation)
    click.echo(f"Warning: Unknown transformation '{transformation}'", err=True)
    return value


def _replace(value: str, transformation: str) -> str:
    """Apply ``replace(old, new)``, where both arguments may be quoted."""
    arguments = transformation[len(REPLACE_PREFIX) : -1]
    if arguments.count(",") != 1:
        click.echo(
            f"Warning: Invalid replace transformation format: {transformation}",
            err=True,
        )
        return value
    old, new = (argument.strip().strip("'\"") for argument in arguments.split(","))
    return value.replace(old, new)
