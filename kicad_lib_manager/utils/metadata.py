"""Library metadata files: kilm.yaml and .kilm_metadata.

kilm.yaml describes a symbol/footprint library, .kilm_metadata a 3D model
library. Reading validates the fields KiLM knows: a field with the wrong type
is left out, as if absent. Fields KiLM does not know are kept, so a read,
change, and write cycle preserves what users or other tools added to the file.
kilm.yaml entries that the typed view cannot hold at all (non-string keys and
mistyped known fields) come back separately from `read_github_metadata_file`
for `write_github_metadata` to put back.
Read and write failures are reported on stderr and returned as None or False,
because every caller treats unreadable metadata as missing.
"""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"yaml"}

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final, NamedTuple, TypedDict, cast

import yaml

from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.constants import (
    CLOUD_METADATA_FILE,
    GITHUB_METADATA_FILE,
    MAX_ENV_VAR_NAME_LENGTH,
    MODEL_EXTENSIONS,
)

__all__ = [
    "CLOUD_METADATA_FILE",
    "GITHUB_METADATA_FILE",
    "LIBRARY_FOLDERS",
    "CloudMetadata",
    "GitHubMetadata",
    "GitHubMetadataFile",
    "LibraryCapabilities",
    "count_model_files",
    "generate_env_var_name",
    "get_default_cloud_metadata",
    "get_default_github_metadata",
    "library_capabilities",
    "read_cloud_metadata",
    "read_github_metadata",
    "read_github_metadata_file",
    "write_cloud_metadata",
    "write_github_metadata",
]


LIBRARY_FOLDERS: Final = ("symbols", "footprints", "templates")
"""The top-level content folders of a symbol/footprint library.

`LibraryCapabilities` has one flag per folder, in this order.
"""


class LibraryCapabilities(TypedDict, total=False):
    """Which kinds of content a library has, by its top-level directories."""

    symbols: bool
    footprints: bool
    templates: bool


class _LibraryMetadata(TypedDict, total=False):
    """Fields shared by both metadata files. Every field may be absent.

    env_var names the environment variable that KiCad resolves to the
    library path; None or absent means the library has none.
    """

    name: str
    description: str
    type: str
    version: str
    env_var: str | None
    created_with: str
    updated_with: str


class GitHubMetadata(_LibraryMetadata, total=False):
    """kilm.yaml of a symbol/footprint library. Every field may be absent."""

    capabilities: LibraryCapabilities


class CloudMetadata(_LibraryMetadata, total=False):
    """.kilm_metadata of a 3D model library. Every field may be absent."""

    model_count: int


class GitHubMetadataFile(NamedTuple):
    """A kilm.yaml split into its typed fields and the entries they cannot hold.

    unsupported has the entries with non-string keys and the known fields of
    the wrong type. Passing it back to `write_github_metadata` keeps them, so
    rewriting the file loses nothing.
    """

    metadata: GitHubMetadata
    unsupported: dict[object, object]


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
    return all(isinstance(flags.get(key, False), bool) for key in LIBRARY_FOLDERS)


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


def _split_fields(
    document: object, fields: Mapping[str, FieldCheck]
) -> tuple[dict[str, object], dict[object, object]]:
    """Split document into its valid string-keyed entries and all the others.

    The others are the non-string keys and the known fields of the wrong type.
    A document that is not a mapping counts as empty.
    """
    valid: dict[str, object] = {}
    others: dict[object, object] = {}
    if isinstance(document, dict):
        for key, value in cast("dict[object, object]", document).items():
            if isinstance(key, str) and fields.get(key, _is_anything)(value):
                valid[key] = value
            else:
                others[key] = value
    return valid, others


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
    loaded = read_github_metadata_file(directory)
    return None if loaded is None else loaded.metadata


def read_github_metadata_file(directory: Path) -> GitHubMetadataFile | None:
    """Read directory's kilm.yaml with the entries its metadata cannot hold.

    Returns:
        The file's contents (both parts empty when it holds no mapping), or
        None when the file is missing or unreadable.
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
    valid, unsupported = _split_fields(document, _GITHUB_FIELDS)
    # The known fields in valid were checked against GitHubMetadata.
    return GitHubMetadataFile(cast("GitHubMetadata", valid), unsupported)


def write_github_metadata(
    directory: Path,
    metadata: GitHubMetadata,
    unsupported: Mapping[object, object] | None = None,
) -> bool:
    """Write metadata to directory's kilm.yaml; return whether it succeeded.

    Entries of unsupported (from `read_github_metadata_file`) are written
    too, unless metadata has a field of the same name.
    """
    document: dict[object, object] = {
        key: value for key, value in (unsupported or {}).items() if key not in metadata
    }
    document.update(metadata)
    metadata_file = directory / GITHUB_METADATA_FILE
    try:
        with metadata_file.open("w", encoding="utf-8") as f:
            yaml.dump(document, f, default_flow_style=False)
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
    return cast("CloudMetadata", _split_fields(document, _CLOUD_FIELDS)[0])


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

    Capabilities come from `library_capabilities`; env_var is
    KICAD_LIB_<NAME>.
    """
    name = directory.name
    return {
        "name": name,
        "description": f"KiCad library {name}",
        "type": "github",
        "version": "1.0.0",
        "env_var": generate_env_var_name(name, "KICAD_LIB"),
        "capabilities": library_capabilities(directory),
        "created_with": "kilm",
        "updated_with": "kilm",
    }


def library_capabilities(directory: Path) -> LibraryCapabilities:
    """Return which of the `LIBRARY_FOLDERS` exist in directory."""
    return {
        "symbols": (directory / "symbols").exists(),
        "footprints": (directory / "footprints").exists(),
        "templates": (directory / "templates").exists(),
    }


def count_model_files(directory: Path) -> int:
    """Return the number of files below ``directory`` named like 3D models.

    Matches MODEL_EXTENSIONS case-sensitively at any depth, in one walk.
    """
    return sum(
        1
        for file in directory.rglob("*")
        if file.suffix in MODEL_EXTENSIONS and file.is_file()
    )


def get_default_cloud_metadata(directory: Path) -> CloudMetadata:
    """Metadata for a new 3D model library in directory, named after the directory.

    model_count counts the model files anywhere below directory; env_var is
    KICAD_3D_<NAME>.
    """
    name = directory.name
    model_count = count_model_files(directory)
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
