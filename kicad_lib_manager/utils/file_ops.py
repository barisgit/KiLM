"""Reading and writing KiCad library tables and other files KiLM changes."""

import os
import re
import shutil
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, NamedTuple, TypedDict

from kicad_lib_manager.utils.constants import FOOTPRINT_TABLE_FILE, SYMBOL_TABLE_FILE

_DEFAULT_ENCODINGS = ("utf-8", "utf-16", "iso-8859-1")

# One (lib ...) entry per line, as KiCad writes library tables.
_LIB_ENTRY_RE = re.compile(r"^\s*\(lib\s+(.*?)\)\s*$", re.MULTILINE)
# A token of an entry: a quoted string (group 1, escapes undecoded) or else a
# parenthesis or an unquoted atom (group 2).
_TOKEN_RE = re.compile(r'"((?:[^"\\]|\\.)*)"|([()]|[^\s()"]+)', re.DOTALL)
# An escape in a quoted string: hex bytes, octal bytes, or any other character.
_ESCAPE_RE = re.compile(rb"\\(?:x[0-9A-Fa-f]{1,2}|[0-7]{1,3}|.)", re.DOTALL)
_OCTAL_DIGITS = frozenset(b"01234567")
_NAMED_ESCAPES = {
    b'"': b'"',
    b"\\": b"\\",
    b"a": b"\a",
    b"b": b"\b",
    b"f": b"\f",
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"v": b"\v",
    b"x": b"x",
}
_Property = Literal["name", "uri", "type", "description"]
# Entry properties by keyword; "url" is accepted for "uri" too.
_PROPERTY_KEYWORDS: dict[str, _Property] = {
    "name": "name",
    "uri": "uri",
    "url": "uri",
    "type": "type",
    "descr": "description",
}
_OPTIONAL_PROPERTIES: tuple[Literal["uri", "type", "description"], ...] = (
    "uri",
    "type",
    "description",
)


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
    table_type = "fp" if table_path.name == FOOTPRINT_TABLE_FILE else "sym"
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
    Quoted values are decoded as KiCad reads them, so they equal the values
    that KiCad or KiLM wrote.

    Returns:
        (symbol library entries, footprint library entries)
    """
    return (
        _read_lib_table(kicad_config / SYMBOL_TABLE_FILE),
        _read_lib_table(kicad_config / FOOTPRINT_TABLE_FILE),
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


class _Token(NamedTuple):
    """A token of a table entry; text is decoded when quoted."""

    text: str
    quoted: bool


_OPEN = _Token("(", quoted=False)
_CLOSE = _Token(")", quoted=False)


def _parse_lib_entry(entry: str) -> LibraryTableEntry | None:
    """Read the `(keyword value)` properties of one entry's content.

    The first non-empty value of each property counts. Returns None when the
    entry has no name.
    """
    tokens = [
        _Token(_unescape(match.group(1)), quoted=True)
        if match.group(2) is None
        else _Token(match.group(2), quoted=False)
        for match in _TOKEN_RE.finditer(entry)
    ]
    found: dict[_Property, str] = {}
    for opening, keyword, value, closing in zip(
        tokens, tokens[1:], tokens[2:], tokens[3:], strict=False
    ):
        prop = _PROPERTY_KEYWORDS.get(keyword.text) if not keyword.quoted else None
        is_value = value.quoted or value not in {_OPEN, _CLOSE}
        if opening == _OPEN and closing == _CLOSE and prop and is_value and value.text:
            found.setdefault(prop, value.text)
    name = found.get("name")
    if name is None:
        return None
    parsed: LibraryTableEntry = {"name": name}
    for key in _OPTIONAL_PROPERTIES:
        if key in found:
            parsed[key] = found[key]
    return parsed


def _unescape(text: str) -> str:
    """Decode the escapes of a quoted string as KiCad's S-expression reader does.

    KiCad decodes escapes to bytes and reads the result as UTF-8, so this
    works on the UTF-8 bytes too; other characters pass through unchanged.
    An unknown escape keeps its backslash.
    """
    return _ESCAPE_RE.sub(_escaped_bytes, text.encode("utf-8")).decode(
        "utf-8", errors="replace"
    )


def _escaped_bytes(match: re.Match[bytes]) -> bytes:
    r"""Return the bytes that one escape, such as `\n` or `\x41`, stands for."""
    body = match.string[match.start() + 1 : match.end()]  # after the backslash
    if body in _NAMED_ESCAPES:
        return _NAMED_ESCAPES[body]
    if body.startswith(b"x"):
        return bytes([int(body[1:], 16)])
    if body[0] in _OCTAL_DIGITS:
        # KiCad stores the value in a char, keeping the low byte.
        return bytes([int(body, 8) & 0xFF])
    return b"\\" + body
