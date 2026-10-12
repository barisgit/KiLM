"""Library metadata files: kilm.yaml and .kilm_metadata.

kilm.yaml describes a symbol/footprint library, .kilm_metadata a 3D model
library. Reading validates the fields KiLM knows: a field with the wrong type
is left out, as if absent. Fields KiLM does not know are kept, so a read,
change, and write cycle preserves what users or other tools added to the file.
Read and write failures are reported on stderr and returned as None or False,
because every caller treats unreadable metadata as missing.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"yaml"}

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypedDict, cast

import yaml

from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import (
    CLOUD_METADATA_FILE,
    GITHUB_METADATA_FILE,
    MAX_ENV_VAR_NAME_LENGTH,
)

__all__ = [
    "CLOUD_METADATA_FILE",
    "GITHUB_METADATA_FILE",
    "CloudMetadata",
    "GitHubMetadata",
    "LibraryCapabilities",
    "generate_env_var_name",
    "get_default_cloud_metadata",
    "get_default_github_metadata",
    "read_cloud_metadata",
    "read_github_metadata",
    "write_cloud_metadata",
    "write_github_metadata",
]

_MODEL_SUFFIXES = (".step", ".stp", ".wrl", ".wings")


class LibraryCapabilities(TypedDict, total=False):
    """Which kinds of content a library has, by its top-level directories."""

    symbols: bool
    footprints: bool
    templates: bool


class GitHubMetadata(TypedDict, total=False):
    """kilm.yaml of a symbol/footprint library. Every field may be absent.

    env_var names the environment variable that KiCad resolves to the
    library path; None or absent means the library has none.
    """

    name: str
    description: str
    type: str
    version: str
    env_var: str | None
    capabilities: LibraryCapabilities
    created_with: str
    updated_with: str


class CloudMetadata(TypedDict, total=False):
    """.kilm_metadata of a 3D model library. Every field may be absent."""

    name: str
    description: str
    type: str
    version: str
    env_var: str | None
    model_count: int
    created_with: str
    updated_with: str


FieldCheck = Callable[[object], bool]


def _is_str(value: object) -> bool:
    return isinstance(value, str)


def _is_optional_str(value: object) -> bool:
    return value is None or isinstance(value, str)


def _is_count(value: object) -> bool:
    # bool is an int subclass; YAML true is not a count.
    return isinstance(value, int) and not isinstance(value, bool)


def _is_capabilities(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    flags = cast("dict[object, object]", value)
    return all(
        isinstance(flags.get(key, False), bool)
        for key in LibraryCapabilities.__annotations__
    )


_COMMON_FIELDS: dict[str, FieldCheck] = {
    "name": _is_str,
    "description": _is_str,
    "type": _is_str,
    "version": _is_str,
    "env_var": _is_optional_str,
    "created_with": _is_str,
    "updated_with": _is_str,
}
_GITHUB_FIELDS: dict[str, FieldCheck] = {
    **_COMMON_FIELDS,
    "capabilities": _is_capabilities,
}
_CLOUD_FIELDS: dict[str, FieldCheck] = {**_COMMON_FIELDS, "model_count": _is_count}


def _valid_fields(
    document: object, fields: Mapping[str, FieldCheck]
) -> dict[str, object]:
    """The string-keyed entries of document, minus known fields of the wrong type.

    A document that is not a mapping counts as empty.
    """
    if not isinstance(document, dict):
        return {}
    entries = cast("dict[object, object]", document)
    return {
        key: value
        for key, value in entries.items()
        if isinstance(key, str) and fields.get(key, _is_anything)(value)
    }


def _is_anything(_value: object) -> bool:
    return True


def _report(message: str) -> None:
    get_console(stderr=True).print(message, markup=False, highlight=False)


def read_github_metadata(directory: Path) -> GitHubMetadata | None:
    """Read directory's kilm.yaml.

    Returns:
        The metadata (empty when the file holds no mapping), or None when the
        file is missing or unreadable.
    """
    metadata_file = directory / GITHUB_METADATA_FILE
    if not metadata_file.exists():
        return None
    try:
        with metadata_file.open(encoding="utf-8") as f:
            document: object = yaml.safe_load(f)
    except (OSError, ValueError, yaml.YAMLError) as e:
        _report(f"Error reading metadata file: {e}")
        return None
    # The known fields were checked against GitHubMetadata just above.
    return cast("GitHubMetadata", _valid_fields(document, _GITHUB_FIELDS))


def write_github_metadata(directory: Path, metadata: GitHubMetadata) -> bool:
    """Write metadata to directory's kilm.yaml; return whether it succeeded."""
    metadata_file = directory / GITHUB_METADATA_FILE
    try:
        with metadata_file.open("w", encoding="utf-8") as f:
            yaml.dump(metadata, f, default_flow_style=False)
    except (OSError, yaml.YAMLError) as e:
        _report(f"Error writing metadata file: {e}")
        return False
    return True


def read_cloud_metadata(directory: Path) -> CloudMetadata | None:
    """Read directory's .kilm_metadata.

    Returns:
        The metadata (empty when the file holds no JSON object), or None when
        the file is missing or unreadable.
    """
    metadata_file = directory / CLOUD_METADATA_FILE
    if not metadata_file.exists():
        return None
    try:
        with metadata_file.open(encoding="utf-8") as f:
            document: object = json.load(f)
    except (OSError, ValueError) as e:
        _report(f"Error reading cloud metadata file: {e}")
        return None
    # The known fields were checked against CloudMetadata just above.
    return cast("CloudMetadata", _valid_fields(document, _CLOUD_FIELDS))


def write_cloud_metadata(directory: Path, metadata: CloudMetadata) -> bool:
    """Write metadata to directory's .kilm_metadata; return whether it succeeded."""
    metadata_file = directory / CLOUD_METADATA_FILE
    try:
        with metadata_file.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except (OSError, TypeError, ValueError) as e:
        _report(f"Error writing cloud metadata file: {e}")
        return False
    return True


def generate_env_var_name(name: str, prefix: str = "") -> str:
    """Derive a valid environment variable name from a library name.

    The result is upper case, has every character other than A-Z and 0-9
    replaced by "_", starts with prefix and "_" when prefix is given, starts
    with a letter ("LIB_" is prepended otherwise), and is cut to
    MAX_ENV_VAR_NAME_LENGTH characters.
    """
    clean_name = re.sub(r"[^a-zA-Z0-9]", "_", name.upper())
    if prefix:
        clean_name = f"{prefix}_{clean_name}"
    if not clean_name[:1].isalpha():
        clean_name = f"LIB_{clean_name}"
    return clean_name[:MAX_ENV_VAR_NAME_LENGTH]


def get_default_github_metadata(directory: Path) -> GitHubMetadata:
    """Metadata for a new library in directory, named after the directory.

    Capabilities reflect which of the symbols, footprints, and templates
    directories exist; env_var is KICAD_LIB_<NAME>.
    """
    name = directory.name
    return {
        "name": name,
        "description": f"KiCad library {name}",
        "type": "github",
        "version": "1.0.0",
        "env_var": generate_env_var_name(name, "KICAD_LIB"),
        "capabilities": {
            "symbols": (directory / "symbols").exists(),
            "footprints": (directory / "footprints").exists(),
            "templates": (directory / "templates").exists(),
        },
        "created_with": "kilm",
        "updated_with": "kilm",
    }


def get_default_cloud_metadata(directory: Path) -> CloudMetadata:
    """Metadata for a new 3D model library in directory, named after the directory.

    model_count counts the model files anywhere below directory; env_var is
    KICAD_3D_<NAME>.
    """
    name = directory.name
    model_count = sum(
        len(list(directory.glob(f"**/*{suffix}"))) for suffix in _MODEL_SUFFIXES
    )
    return {
        "name": name,
        "description": f"KiCad 3D model library {name}",
        "type": "cloud",
        "version": "1.0.0",
        "env_var": generate_env_var_name(name, "KICAD_3D"),
        "model_count": model_count,
        "created_with": "kilm",
        "updated_with": "kilm",
    }
