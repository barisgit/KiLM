"""Tests for file writes that must never leave a file half-written."""

from pathlib import Path

import pytest

from kicad_lib_manager.utils.file_ops import write_file_with_encoding


def test_failed_write_keeps_the_old_file(tmp_path: Path) -> None:
    """Content that cannot be encoded leaves the existing file unchanged.

    Library names come from file names, which can carry undecodable bytes as
    lone surrogates; writing one must not wipe the library table.
    """
    table = tmp_path / "sym-lib-table"
    table.write_text("(sym_lib_table\n)\n", encoding="utf-8")

    with pytest.raises(UnicodeEncodeError):
        write_file_with_encoding(table, '(lib (name "bad\udcff"))')

    assert table.read_text(encoding="utf-8") == "(sym_lib_table\n)\n"
    assert [p.name for p in tmp_path.iterdir()] == ["sym-lib-table"]


def test_write_replaces_the_content(tmp_path: Path) -> None:
    """A successful write replaces the whole file."""
    table = tmp_path / "fp-lib-table"
    table.write_text("old content that is longer", encoding="utf-8")

    write_file_with_encoding(table, "new")

    assert table.read_text(encoding="utf-8") == "new"
