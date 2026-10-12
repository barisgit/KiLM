"""Library writes: atomic replacement, backups, and line endings."""

import errno
import os
import stat
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kicad_lib_manager.utils.file_ops import write_atomically

from .helpers import (
    SAMPLE_SYM_LIB,
    run_import,
    samacsys_zip,
    ultralibrarian_zip,
    zip_with,
)


def _no_space(_fd: int) -> None:
    raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))


def test_failed_symbol_write_leaves_library_intact(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    zip_path = zip_with(
        tmp_path,
        "S",
        {"S/KiCad/S.kicad_sym": '(kicad_symbol_lib\n\t(symbol "S"\n\t)\n)\n'},
    )

    with patch("kicad_lib_manager.utils.file_ops.os.fsync", side_effect=_no_space):
        result = run_import(str(zip_path))

    assert result.exit_code == 1, result.output
    assert "No space left on device" in result.output
    assert sym_lib.read_text(encoding="utf-8") == SAMPLE_SYM_LIB
    backups = list(sym_lib.parent.glob("SAMPLELIB.kicad_sym.backup.*"))
    assert [b.read_text(encoding="utf-8") for b in backups] == [SAMPLE_SYM_LIB]
    assert not list(sym_lib.parent.glob(".*.tmp"))


def test_symbol_library_is_backed_up_once_per_run(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    (tmp_path / "a").mkdir()

    result = run_import(
        str(samacsys_zip(tmp_path / "a", "PartA")), str(samacsys_zip(tmp_path, "PartB"))
    )

    assert result.exit_code == 0, result.output
    backups = list(sym_lib.parent.glob("SAMPLELIB.kicad_sym.backup.*"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == SAMPLE_SYM_LIB
    assert f"Backup: {backups[0]}" in result.output


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_written_files_keep_library_line_endings(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock, newline: str
) -> None:
    # Rewriting every line ending of a git-tracked library (Windows text-mode
    # writes, or CRLF vendor files) would bury the import in a whole-file diff.
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    sym_lib.write_bytes(SAMPLE_SYM_LIB.replace("\n", newline).encode())

    result = run_import(str(ultralibrarian_zip(tmp_path, "EolPart")))

    assert result.exit_code == 0, result.output
    data = sym_lib.read_bytes()
    assert b'(symbol "EolPart"' in data
    rest = data.replace(newline.encode(), b"")
    assert b"\r" not in rest
    assert b"\n" not in rest
    fp = library_tree / "footprints" / "SAMPLELIB.pretty" / "EolPart.kicad_mod"
    assert b"\r" not in fp.read_bytes()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_write_atomically_keeps_permissions(tmp_path: Path) -> None:
    path = tmp_path / "lib.kicad_sym"
    path.write_text("old")
    path.chmod(0o664)

    write_atomically(path, b"new")

    assert path.read_bytes() == b"new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o664
