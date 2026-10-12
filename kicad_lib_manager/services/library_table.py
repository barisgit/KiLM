"""Add a KiLM library's symbols and footprints to KiCad's library tables."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"yaml"}

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

import yaml

from kicad_lib_manager.utils.console import get_console
from kicad_lib_manager.utils.env_vars import expand_user_path
from kicad_lib_manager.utils.file_ops import (
    list_configured_libraries,
    list_libraries,
    validate_lib_table,
    write_atomically,
)

LibraryKind = Literal["symbols", "footprints"]
"""The library subdirectory of a KiLM library, and so the KiCad table it goes in."""

TABLE_FILES: Final[dict[LibraryKind, str]] = {
    "symbols": "sym-lib-table",
    "footprints": "fp-lib-table",
}

LIBRARY_SUFFIXES: Final[dict[LibraryKind, str]] = {
    "symbols": ".kicad_sym",
    "footprints": ".pretty",
}

DESCRIPTIONS_FILE: Final = "library_descriptions.yaml"
"""Optional file in a KiLM library mapping kind and library name to a description."""

DEFAULT_DESCRIPTIONS: Final[dict[LibraryKind, str]] = {
    "symbols": "{name} symbol library",
    "footprints": "{name} footprint library",
}


@dataclass(frozen=True)
class TableEntry:
    """A library to add to a KiCad library table."""

    name: str
    uri: str
    description: str
    options: str = ""

    def to_sexpr(self) -> str:
        """Return the `(lib ...)` line for this entry, indented for a table."""
        return (
            f"  (lib (name {_quote(self.name)})"
            '(type "KiCad")'
            f"(uri {_quote(_unwrap_absolute(self.uri))})"
            f"(options {_quote(self.options)})"
            f"(descr {_quote(self.description)}))"
        )


def add_libraries(
    kicad_lib_dir: str,
    kicad_config: Path,
    *,
    kicad_3d_dir: str | None = None,
    additional_3d_dirs: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> tuple[set[str], bool]:
    """Add the libraries in a KiLM library that KiCad's tables do not list yet.

    Args:
        kicad_lib_dir: The KiLM library: a path, an environment variable
            name, or `${NAME}`. Anything that is not an absolute path is
            looked up as an environment variable.
        kicad_config: KiCad's configuration directory, holding the tables.
        kicad_3d_dir: Main 3D model directory; it must exist.
        additional_3d_dirs: Further 3D model directories by environment
            variable name; missing ones are reported and skipped.
        dry_run: Report what would be added without writing.

    Returns:
        The names of the libraries added (or to add), and whether any are.

    Raises:
        FileNotFoundError: The environment variable is not set, or the
            library or main 3D model directory does not exist.
        ValueError: The library has neither symbols nor footprints, or a
            table is not a valid KiCad library table.
    """
    library_dir = _resolve_library_dir(kicad_lib_dir, os.environ)
    _check_3d_dirs(kicad_3d_dir, additional_3d_dirs or {})

    symbols, footprints = list_libraries(library_dir)
    if not symbols and not footprints:
        msg = f"No libraries found in {library_dir}"
        raise ValueError(msg)

    configured_symbols, configured_footprints = list_configured_libraries(kicad_config)
    descriptions = _read_descriptions(Path(library_dir))
    added: set[str] = set()
    kinds: tuple[tuple[LibraryKind, list[str], set[str]], ...] = (
        ("symbols", symbols, {entry["name"] for entry in configured_symbols}),
        ("footprints", footprints, {entry["name"] for entry in configured_footprints}),
    )
    for kind, available, configured in kinds:
        entries = [
            TableEntry(
                name=name,
                uri=format_uri(library_dir, name, kind),
                description=_description(descriptions, kind, name),
            )
            for name in available
            if name not in configured
        ]
        if entries and not dry_run:
            add_entries_to_table(kicad_config / TABLE_FILES[kind], entries)
        added.update(entry.name for entry in entries)
    return added, bool(added)


def _resolve_library_dir(kicad_lib_dir: str, environ: Mapping[str, str]) -> str:
    """Return the existing library directory that kicad_lib_dir names."""
    if kicad_lib_dir.startswith("${") and kicad_lib_dir.endswith("}"):
        variable: str | None = kicad_lib_dir[2:-1]
    elif _is_absolute(kicad_lib_dir):
        variable = None
    else:
        variable = kicad_lib_dir
    if variable is not None:
        value = environ.get(variable)
        if value is None:
            msg = f"Environment variable {variable} not found"
            raise FileNotFoundError(msg)
        kicad_lib_dir = value

    library_dir = expand_user_path(kicad_lib_dir)
    if not Path(library_dir).exists():
        msg = f"KiCad library directory not found: {library_dir}"
        raise FileNotFoundError(msg)
    return library_dir


def _check_3d_dirs(main: str | None, additional: Mapping[str, str]) -> None:
    """Require the main 3D model directory; warn about missing additional ones."""
    if main is not None:
        models_dir = expand_user_path(main)
        if not Path(models_dir).exists():
            msg = f"KiCad 3D models directory not found: {models_dir}"
            raise FileNotFoundError(msg)
    for path in additional.values():
        models_dir = expand_user_path(path)
        if not Path(models_dir).exists():
            get_console(stderr=True).print(
                f"Warning: 3D models directory not found: {models_dir} (skipping)",
                markup=False,
                highlight=False,
            )


def _read_descriptions(library_dir: Path) -> dict[str, object]:
    """Return the library's descriptions file as a mapping; empty if unusable."""
    try:
        with (library_dir / DESCRIPTIONS_FILE).open(encoding="utf-8") as f:
            data: object = yaml.safe_load(f)
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return cast("dict[str, object]", data) if isinstance(data, dict) else {}


def _description(
    descriptions: Mapping[str, object], kind: LibraryKind, name: str
) -> str:
    """Return the described text for a library, or a default naming its kind."""
    of_kind = descriptions.get(kind)
    if isinstance(of_kind, dict):
        text = cast("dict[object, object]", of_kind).get(name)
        if text is not None:
            return str(text)
    return DEFAULT_DESCRIPTIONS[kind].format(name=name)


def format_uri(base_path: str, lib_name: str, lib_type: str) -> str:
    """Return the table URI of a library inside base_path.

    Backslashes become forward slashes. An absolute base_path (also inside
    `${...}`) is used as is; anything else is an environment variable and
    is written as `${NAME}`.

    Raises:
        ValueError: base_path is empty or an unclosed `${`, or lib_type is
            neither "symbols" nor "footprints".
    """
    if not base_path:
        msg = "Base path cannot be empty"
        raise ValueError(msg)
    if lib_type not in LIBRARY_SUFFIXES:
        msg = f"Invalid library type: {lib_type}"
        raise ValueError(msg)
    if base_path.startswith("${") and not base_path.endswith("}"):
        msg = f"Invalid environment variable format: {base_path}"
        raise ValueError(msg)

    base_path = base_path.replace("\\", "/")
    if base_path.startswith("${"):
        inner = base_path[2:-1]
        if _is_absolute(inner):
            base_path = inner
    elif not _is_absolute(base_path):
        base_path = f"${{{base_path}}}"
    kind = cast("LibraryKind", lib_type)
    return f"{base_path}/{kind}/{lib_name}{LIBRARY_SUFFIXES[kind]}"


def _is_absolute(path: str) -> bool:
    """Return whether path is absolute on Unix or Windows (drive, root, or UNC)."""
    return path.startswith(("/", "\\")) or (len(path) > 1 and path[1] == ":")


def add_entries_to_table(table_path: Path, entries: Sequence[TableEntry]) -> None:
    """Insert entries before the closing parenthesis of a library table.

    The table is replaced atomically.

    Raises:
        ValueError: The table is missing, is not a library table, or has no
            line holding only its closing parenthesis.
    """
    validate_lib_table(table_path, create_if_missing=False)
    lines = table_path.read_text(encoding="utf-8").splitlines()
    closing = next(
        (i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == ")"), None
    )
    if closing is None:
        msg = f"Could not find closing parenthesis in library table: {table_path}"
        raise ValueError(msg)
    lines[closing:closing] = [entry.to_sexpr() for entry in entries]
    write_atomically(table_path, ("\n".join(lines) + "\n").encode("utf-8"))


def _unwrap_absolute(uri: str) -> str:
    """Remove a `${...}` wrapper around an absolute path, which KiCad cannot resolve."""
    if uri.startswith(("${/", "${\\")):
        end = uri.rfind("}")
        if end != -1:
            return uri[2:end] + uri[end + 1 :]
    return uri


def _quote(value: str) -> str:
    """Quote value as a KiCad S-expression string, as KiCad's own writer does."""
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'
