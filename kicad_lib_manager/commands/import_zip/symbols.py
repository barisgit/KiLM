"""Merging vendor symbols into a KiCad symbol library (.kicad_sym)."""

import re
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Optional

from .errors import ImportFailure


def extract_symbol_blocks(text: str) -> list[str]:
    """Extract top-level `(symbol "...")` blocks by tracking paren depth.

    Depth-based (not indentation-based) so it works regardless of whether
    the generator indents with tabs (SamacSys/Mouser) or spaces
    (UltraLibrarian), and regardless of line endings. Parentheses inside
    quoted strings do not count.
    """
    blocks: list[str] = []
    depth = 0
    in_str = False
    block_start: Optional[int] = None
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_str:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
        elif ch == "(":
            if depth == 1 and text.startswith('(symbol "', i):
                block_start = i
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 1 and block_start is not None:
                blocks.append(text[block_start : i + 1])
                block_start = None
        i += 1
    return blocks


def symbol_name(block: str) -> str:
    """Name of a `(symbol "...")` block, "" when it has none."""
    m = re.match(r'\(symbol "([^"]+)"', block)
    return m.group(1) if m else ""


def fix_footprint_ref(
    block: str, default_lib: str, fp_refs: Optional[Mapping[str, str]] = None
) -> str:
    """Point the symbol's Footprint field at a footprint library.

    fp_refs maps the names of footprints imported with the symbol to their
    "lib:name" reference; those win over any vendor prefix. Other bare names
    get default_lib; other prefixed names are left alone.
    """

    def _replace(m: re.Match[str]) -> str:
        val = m.group(1)
        name = val.split(":", 1)[1] if ":" in val else val
        if fp_refs and name in fp_refs:
            val = fp_refs[name]
        elif ":" not in val:
            val = f"{default_lib}:{val}"
        return f'"Footprint" "{val}"'

    return re.sub(r'"Footprint" "([^"]+)"', _replace, block)


@dataclass(frozen=True)
class SymbolMerge:
    """Merged library text and the symbol names added or skipped, in source order."""

    text: str
    added: list[str]
    skipped: list[str]


def merge_symbols(
    source: str,
    library: str,
    default_fp_lib: str,
    fp_refs: Optional[Mapping[str, str]] = None,
    known: AbstractSet[str] = frozenset(),
) -> SymbolMerge:
    """Append the symbols of source that library lacks.

    library is the raw text of the target .kicad_sym; the new symbols take its
    line endings and go before its closing parenthesis, and the rest of it is
    kept byte for byte. known holds further names to treat as present, such as
    symbols a dry run added earlier in the run. Footprint fields are fixed
    with fix_footprint_ref.

    Raises:
        ImportFailure: library is not a KiCad symbol library.
    """
    if not library.lstrip("\ufeff \t\r\n").startswith("(kicad_symbol_lib"):
        raise ImportFailure("target is not a KiCad symbol library")
    newline = "\r\n" if "\r\n" in library else "\n"
    present = {symbol_name(b) for b in extract_symbol_blocks(library)} | set(known)

    added: list[str] = []
    skipped: list[str] = []
    new_blocks: list[str] = []
    for block in extract_symbol_blocks(source.replace("\r\n", "\n")):
        name = symbol_name(block)
        if name in present:
            skipped.append(name)
            continue
        present.add(name)
        added.append(name)
        block = fix_footprint_ref(block, default_fp_lib, fp_refs)
        new_blocks.append(block.replace("\n", newline))

    if not new_blocks:
        return SymbolMerge(library, added, skipped)
    end = library.rfind(")")
    insert = newline.join(new_blocks) + newline
    return SymbolMerge(library[:end] + insert + library[end:], added, skipped)
