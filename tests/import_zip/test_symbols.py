"""Symbol parsing and merging into a .kicad_sym library."""

import pytest

from kicad_lib_manager.commands.import_zip.errors import ImportZipError
from kicad_lib_manager.commands.import_zip.symbols import (
    extract_symbol_blocks,
    fix_footprint_ref,
    merge_symbols,
    symbol_name,
)
from tests.import_zip.helpers import INCOMING_SYM, SAMPLE_SYM_LIB


def test_extract_symbol_blocks() -> None:
    """Top-level symbol blocks are found whatever the indentation."""
    blocks = extract_symbol_blocks(INCOMING_SYM)
    assert [symbol_name(b) for b in blocks] == ["NewPart", "ExistingPart"]


def test_extract_symbol_blocks_ignores_parens_in_strings() -> None:
    """Parentheses inside quoted strings do not end a symbol block."""
    text = (
        "(kicad_symbol_lib\n"
        '\t(symbol "PartA"\n'
        '\t\t(property "Description" "Filter (LC")\n'  # unbalanced ( in a string
        "\t)\n"
        ")\n"
    )
    assert [symbol_name(b) for b in extract_symbol_blocks(text)] == ["PartA"]


def test_fix_footprint_ref_adds_prefix() -> None:
    """A bare footprint name gets the default footprint library."""
    block = '\t(property "Footprint" "BareFootprint")'
    assert '"Footprint" "SAMPLELIB:BareFootprint"' in fix_footprint_ref(
        block, "SAMPLELIB"
    )


def test_fix_footprint_ref_keeps_existing_prefix() -> None:
    """A footprint name with a library prefix is kept."""
    block = '\t(property "Footprint" "OTHER:Footprint")'
    assert '"Footprint" "OTHER:Footprint"' in fix_footprint_ref(block, "SAMPLELIB")


def test_fix_footprint_ref_prefers_imported_footprint() -> None:
    """A footprint imported with the symbol wins over the vendor prefix."""
    block = '\t(property "Footprint" "SamacSys_Parts:VENDFP")'
    result = fix_footprint_ref(block, "SAMPLELIB", {"VENDFP": "CAT_QFN:VENDFP"})
    assert '"Footprint" "CAT_QFN:VENDFP"' in result


def test_merge_symbols_adds_new_skips_existing() -> None:
    """Symbols the library lacks are added; present ones are skipped."""
    merge = merge_symbols(INCOMING_SYM, SAMPLE_SYM_LIB, "SAMPLELIB")

    assert merge.added == ["NewPart"]
    assert merge.skipped == ["ExistingPart"]
    assert merge.text.startswith(SAMPLE_SYM_LIB[:-2])
    assert merge.text.count('(symbol "ExistingPart"') == 1
    assert '"Footprint" "SAMPLELIB:NewPart"' in merge.text


def test_merge_symbols_adds_repeated_name_once() -> None:
    """A symbol repeated in the source is added once."""
    source = '(kicad_symbol_lib\n\t(symbol "Twice"\n\t)\n\t(symbol "Twice"\n\t)\n)\n'

    merge = merge_symbols(source, SAMPLE_SYM_LIB, "SAMPLELIB")

    assert (merge.added, merge.skipped) == (["Twice"], ["Twice"])
    assert merge.text.count('(symbol "Twice"') == 1


def test_merge_symbols_treats_known_names_as_present() -> None:
    """Names in known are skipped like symbols already in the library."""
    merge = merge_symbols(INCOMING_SYM, SAMPLE_SYM_LIB, "SAMPLELIB", known={"NewPart"})

    assert merge.added == []
    assert merge.text == SAMPLE_SYM_LIB


def test_merge_symbols_rejects_a_non_library_target() -> None:
    """A target that is not a .kicad_sym library raises ImportZipError."""
    with pytest.raises(ImportZipError, match="not a KiCad symbol library"):
        merge_symbols(INCOMING_SYM, "", "SAMPLELIB")
