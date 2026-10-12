"""Typed template metadata and its validation from ``metadata.yaml``."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"yaml"}

from collections.abc import Collection, Mapping
from pathlib import Path
from typing import TypeAlias, TypedDict, cast

import yaml

from kicad_lib_manager.utils.constants import TEMPLATE_METADATA

# Values a template is rendered with, keyed by variable name.
RenderVariables: TypeAlias = Mapping[str, str | int | bool]


class TemplateVariable(TypedDict):
    """A variable that a template asks for when a project is created."""

    description: str
    default: str


class TemplateDependencies(TypedDict):
    """Libraries a template recommends."""

    recommended: list[str]


class TemplateMetadata(TypedDict, total=False):
    """The contents of a template's ``metadata.yaml``.

    Every key is optional in a file that a user wrote; ``template make`` writes
    name, description, use_case, version, and variables.
    """

    name: str
    description: str
    use_case: str
    version: str
    variables: dict[str, TemplateVariable]
    extends: str
    dependencies: TemplateDependencies


class DiscoveredTemplate(TemplateMetadata, total=True):
    """Template metadata plus where the template was found."""

    path: str
    source_library: str
    library_path: str


# The keys each TypedDict declares (inherited ones included). Other keys in
# metadata.yaml are custom and kept as loaded.
_TEMPLATE_KEYS = (
    DiscoveredTemplate.__required_keys__ | DiscoveredTemplate.__optional_keys__
)
_VARIABLE_KEYS = TemplateVariable.__required_keys__ | TemplateVariable.__optional_keys__
_DEPENDENCY_KEYS = (
    TemplateDependencies.__required_keys__ | TemplateDependencies.__optional_keys__
)


class MetadataError(Exception):
    """A ``metadata.yaml`` file could not be read or parsed."""


def read_template_metadata(template_dir: Path) -> TemplateMetadata | None:
    """Read the metadata of the template in ``template_dir``.

    Returns None when the file holds no mapping or an empty one.

    Raises:
        MetadataError: The file is missing, unreadable, or not valid YAML.
    """
    metadata_file = template_dir / TEMPLATE_METADATA
    try:
        with metadata_file.open(encoding="utf-8") as stream:
            raw: object = yaml.safe_load(stream)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        message = f"Error reading template metadata from {metadata_file}: {error}"
        raise MetadataError(message) from error
    return parse_template_metadata(raw)


def parse_template_metadata(raw: object) -> TemplateMetadata | None:
    """Validate loaded YAML as template metadata.

    Known keys are kept with their declared types: scalars become strings, a
    variable without a description or default gets the ones ``template create``
    shows, and malformed values are dropped. Other keys, also inside a
    variable or ``dependencies``, are kept as loaded for hooks and ``template
    list --json``; the keys that discovery adds (``path`` and the library) are
    not taken from the file. Returns None unless ``raw`` is a non-empty mapping.
    """
    fields = _string_keyed(raw)
    if fields is None or not fields:
        return None
    metadata = TemplateMetadata()
    if (name := _text(fields.get("name"))) is not None:
        metadata["name"] = name
    if (description := _text(fields.get("description"))) is not None:
        metadata["description"] = description
    if (use_case := _text(fields.get("use_case"))) is not None:
        metadata["use_case"] = use_case
    if (version := _text(fields.get("version"))) is not None:
        metadata["version"] = version
    if (extends := _text(fields.get("extends"))) is not None:
        metadata["extends"] = extends
    if (variables := _string_keyed(fields.get("variables"))) is not None:
        metadata["variables"] = _variables(variables)
    if (dependencies := _string_keyed(fields.get("dependencies"))) is not None:
        metadata["dependencies"] = _dependencies(dependencies)
    # TypedDicts allow extra keys; the declared ones were checked above.
    return cast(
        "TemplateMetadata",
        _with_custom_keys(dict(metadata), fields, _TEMPLATE_KEYS),
    )


def write_template_metadata(directory: Path, metadata: TemplateMetadata) -> None:
    """Write ``metadata`` to the ``metadata.yaml`` file in ``directory``.

    Raises:
        OSError: The file cannot be written.
    """
    metadata_file = directory / TEMPLATE_METADATA
    with metadata_file.open("w", encoding="utf-8") as stream:
        yaml.dump(dict(metadata), stream, default_flow_style=False)


def default_description(name: str) -> str:
    """Return the description of a variable whose author gave none."""
    return f"Value for {name}"


def _string_keyed(value: object) -> dict[str, object] | None:
    """Return a YAML mapping with its keys as text, or None for other values."""
    if not isinstance(value, Mapping):
        return None
    return {str(key): item for key, item in value.items()}


def _text(value: object) -> str | None:
    """Return a YAML scalar as text, or None for a missing or nested value."""
    if value is None or isinstance(value, (Mapping, list)):
        return None
    return str(value)


def _with_custom_keys(
    validated: dict[str, object],
    fields: Mapping[str, object],
    declared: Collection[str],
) -> dict[str, object]:
    """Return ``validated`` followed by the ``fields`` that are not ``declared``."""
    return {
        **validated,
        **{key: value for key, value in fields.items() if key not in declared},
    }


def _variables(raw: dict[str, object]) -> dict[str, TemplateVariable]:
    variables: dict[str, TemplateVariable] = {}
    for name, value in raw.items():
        fields = _string_keyed(value) or {}
        description = _text(fields.get("description"))
        default = _text(fields.get("default"))
        variable = TemplateVariable(
            description=default_description(name)
            if description is None
            else description,
            default="" if default is None else default,
        )
        # TypedDicts allow extra keys; the declared ones were set above.
        variables[name] = cast(
            "TemplateVariable",
            _with_custom_keys(dict(variable), fields, _VARIABLE_KEYS),
        )
    return variables


def _dependencies(raw: dict[str, object]) -> TemplateDependencies:
    recommended = raw.get("recommended")
    names = recommended if isinstance(recommended, list) else []
    dependencies = TemplateDependencies(
        recommended=[text for item in names if (text := _text(item)) is not None]
    )
    # TypedDicts allow extra keys; the declared one was set above.
    return cast(
        "TemplateDependencies",
        _with_custom_keys(dict(dependencies), raw, _DEPENDENCY_KEYS),
    )
