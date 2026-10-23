"""Discovery of the templates in the configured libraries."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypedDict

import typer

from kicad_lib_manager.utils.constants import TEMPLATE_METADATA, TEMPLATES_DIR
from kicad_lib_manager.utils.template.models import (
    DiscoveredTemplate,
    MetadataError,
    discovered_template,
    read_template_metadata,
)


class ConfiguredLibrary(TypedDict):
    """The fields of a configured library that template discovery reads."""

    name: str
    path: str


class LibrarySource(Protocol):
    """Lists the configured libraries in priority order, as ``Config`` does."""

    def get_libraries(self) -> Sequence[ConfiguredLibrary]:
        """Return every configured library."""
        ...


def list_templates_in_directory(directory: Path) -> list[DiscoveredTemplate]:
    """List the templates in the ``templates`` directory of a library.

    A template is a subdirectory with a non-empty ``metadata.yaml``; the
    library's directory name is recorded as its source library. Metadata that
    cannot be read is reported on stderr and the template is skipped.
    """
    templates_dir = directory / TEMPLATES_DIR
    if not templates_dir.is_dir():
        return []
    templates: list[DiscoveredTemplate] = []
    for template_dir in templates_dir.iterdir():
        if not (template_dir / TEMPLATE_METADATA).is_file():
            continue
        try:
            metadata = read_template_metadata(template_dir)
        except MetadataError as error:
            typer.echo(str(error), err=True)
            continue
        if metadata is not None:
            templates.append(discovered_template(metadata, template_dir, directory))
    return templates


def find_all_templates(
    config: LibrarySource, library: str | None = None
) -> dict[str, DiscoveredTemplate]:
    """Find the templates of every configured library, keyed by template name.

    Args:
        config: The configured libraries, searched in their configured order.
        library: Only search the library with this name (case-insensitive).

    Returns:
        The templates by name. Templates without a name are left out. When
        two libraries define the same name, the first library's template is
        kept and the clash is reported on stderr.
    """
    wanted = None if library is None else library.lower()
    templates: dict[str, DiscoveredTemplate] = {}
    for configured in config.get_libraries():
        if wanted is not None and configured["name"].lower() != wanted:
            continue
        library_path = configured["path"]
        if not library_path or not Path(library_path).exists():
            continue
        for template in list_templates_in_directory(Path(library_path)):
            name = template.get("name")
            if name is None or not name:
                continue
            if name in templates:
                _report_duplicate(name, templates[name], template)
                continue
            template["source_library"] = configured["name"]
            template["library_path"] = library_path
            templates[name] = template
    return templates


def _report_duplicate(
    name: str, kept: DiscoveredTemplate, ignored: DiscoveredTemplate
) -> None:
    typer.echo(f"Warning: Duplicate template name '{name}' found.", err=True)
    typer.echo(f"  Using: {kept['path']}", err=True)
    typer.echo(f"  Ignoring: {ignored['path']}", err=True)
