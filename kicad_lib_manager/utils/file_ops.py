"""Reading and writing KiCad library tables and other files KiLM changes."""

import os
import re
import shutil
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, TypedDict

_DEFAULT_ENCODINGS = ("utf-8", "utf-16", "iso-8859-1")

# One (lib ...) entry per line, as KiCad writes library tables.
_LIB_ENTRY_RE = re.compile(r"^\s*\(lib\s+(.*?)\)\s*$", re.MULTILINE)
_LIB_NAME_RE = re.compile(r'\(name\s+"([^"]+)"\)')
# Optional properties of an entry; "url" is accepted for "uri" too.
_LIB_PROPERTY_RES: dict[Literal["uri", "type", "description"], re.Pattern[str]] = {
    "uri": re.compile(r'\((?:uri|url)\s+"([^"]+)"\)'),
    "type": re.compile(r'\(type\s+"([^"]+)"\)'),
    "description": re.compile(r'\(descr\s+"([^"]+)"\)'),
}


class _LibraryTableProperties(TypedDict, total=False):
    """Optional properties of a library table entry."""

    uri: str
    type: str
    description: str


class LibraryTableEntry(_LibraryTableProperties):
    """A library in sym-lib-table or fp-lib-table; only name is always present."""

    name: str


def read_file_with_encoding(
    file_path: Path, encodings: Sequence[str] = _DEFAULT_ENCODINGS
) -> str:
    """Return the text of file_path in the first of encodings that decodes it.

    Line endings are normalized to LF as in text mode. An empty encodings
    sequence returns "".

    Raises:
        UnicodeDecodeError: No encoding decodes the file; the error is the
            last encoding's.
    """
    data = file_path.read_bytes()
    error: UnicodeDecodeError | None = None
    for encoding in encodings:
        text = _decode(data, encoding)
        if isinstance(text, str):
            return text.replace("\r\n", "\n").replace("\r", "\n")
        error = text
    if error is not None:
        raise error
    return ""


def _decode(data: bytes, encoding: str) -> str | UnicodeDecodeError:
    """Return data decoded with encoding, or the decoding error."""
    try:
        return data.decode(encoding)
    except UnicodeDecodeError as e:
        return e


def write_file_with_encoding(
    file_path: Path, content: str, encoding: str = "utf-8"
) -> None:
    """Replace file_path with content in the given encoding, atomically.

    The content is encoded before the file is touched, and write_atomically
    replaces the file in one step, so a failure leaves the old file intact.
    Line endings are written as given, on every OS.
    """
    write_atomically(file_path, content.encode(encoding))


def write_atomically(path: Path, data: bytes) -> None:
    """Replace path with data so readers see the old or new file, never a partial one.

    The data goes to a hidden sibling first, which keeps the final rename on
    one filesystem and therefore atomic, and is flushed to disk before the
    rename. A symlinked path is followed. The new file takes over an existing
    file's permission bits; a new file gets the default ones (0o666 less the
    umask). On failure the sibling is removed and path is unchanged.
    """
    path = path.resolve()  # write through a symlink instead of replacing it
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    # O_BINARY (Windows only) stops newline translation of the bytes.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(tmp, flags, 0o666)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            shutil.copymode(path, tmp)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def validate_lib_table(
    table_path: Path,
    *,
    create_if_missing: bool = True,
) -> None:
    """Check that table_path is a KiCad library table, creating an empty one if allowed.

    The table kind follows the file name: fp-lib-table is a footprint table,
    anything else a symbol table.

    Raises:
        ValueError: The table is missing and create_if_missing is False, or
            its content is not a table of its kind.
    """
    table_type = "fp" if table_path.name == "fp-lib-table" else "sym"
    if not table_path.exists():
        if not create_if_missing:
            msg = f"Library table not found: {table_path}"
            raise ValueError(msg)
        write_file_with_encoding(
            table_path, f"({table_type}_lib_table\n  (version 7)\n)\n"
        )

    content = read_file_with_encoding(table_path)
    if not content.startswith(
        f"({table_type}_lib_table"
    ) or not content.rstrip().endswith(")"):
        msg = f"Invalid library table format in {table_path}"
        raise ValueError(msg)


def list_libraries(kicad_lib_dir: str) -> tuple[list[str], list[str]]:
    """List the symbol and footprint libraries in a KiLM library directory.

    Symbol libraries are the symbols/*.kicad_sym files, footprint libraries
    the footprints/*.pretty directories; both are returned by name.

    Returns:
        (symbol library names, footprint library names)

    Raises:
        FileNotFoundError: kicad_lib_dir does not exist.
    """
    kicad_lib_path = Path(kicad_lib_dir)
    if not kicad_lib_path.exists():
        msg = f"KiCad library directory not found at {kicad_lib_dir}"
        raise FileNotFoundError(msg)

    symbols = [
        f.stem for f in (kicad_lib_path / "symbols").glob("*.kicad_sym") if f.is_file()
    ]
    footprints = [
        d.stem for d in (kicad_lib_path / "footprints").glob("*.pretty") if d.is_dir()
    ]
    return symbols, footprints


def list_configured_libraries(
    kicad_config: Path,
) -> tuple[list[LibraryTableEntry], list[LibraryTableEntry]]:
    """List the libraries in KiCad's sym-lib-table and fp-lib-table.

    A missing table lists no libraries; entries without a name are skipped.

    Returns:
        (symbol library entries, footprint library entries)
    """
    return (
        _read_lib_table(kicad_config / "sym-lib-table"),
        _read_lib_table(kicad_config / "fp-lib-table"),
    )


def _read_lib_table(table_path: Path) -> list[LibraryTableEntry]:
    if not table_path.exists():
        return []
    content = read_file_with_encoding(table_path)
    entries: list[LibraryTableEntry] = []
    for match in _LIB_ENTRY_RE.finditer(content):
        entry = _parse_lib_entry(str(match.group(1)))
        if entry is not None:
            entries.append(entry)
    return entries


def _parse_lib_entry(entry: str) -> LibraryTableEntry | None:
    name = _LIB_NAME_RE.search(entry)
    if name is None:
        return None
    parsed: LibraryTableEntry = {"name": str(name.group(1))}
    for key, pattern in _LIB_PROPERTY_RES.items():
        value = pattern.search(entry)
        if value is not None:
            parsed[key] = str(value.group(1))
    return parsed
