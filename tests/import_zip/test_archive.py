"""Archive extraction: safety, vendor junk, and unreadable members."""

import struct
import zipfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kicad_lib_manager.commands.import_zip.archive import extract_part_files
from kicad_lib_manager.commands.import_zip.errors import ImportZipError
from tests.import_zip.helpers import run_import, samacsys_zip, summary, zip_with


def _set_header_field(path: Path, local: int, central: int, value: int) -> None:
    """Overwrite a 2-byte field in every local and central directory header."""
    data = bytearray(path.read_bytes())
    for signature, offset in ((b"PK\x03\x04", local), (b"PK\x01\x02", central)):
        i = data.find(signature)
        while i != -1:
            data[i + offset : i + offset + 2] = value.to_bytes(2, "little")
            i = data.find(signature, i + 4)
    path.write_bytes(bytes(data))


def _encrypted(path: Path) -> Path:
    _set_header_field(path, local=6, central=8, value=0x1)  # flag bit 0
    return path


def _imploded(path: Path) -> Path:
    _set_header_field(path, local=8, central=10, value=6)  # method 6: implode
    return path


def _corrupt_lzma(path: Path) -> Path:
    """Recompress path with LZMA and give every member invalid LZMA properties."""
    with zipfile.ZipFile(path) as zf:
        members = {name: zf.read(name) for name in zf.namelist()}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_LZMA) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    data = bytearray(path.read_bytes())
    i = data.find(b"PK\x03\x04")
    while i != -1:
        name_len, extra_len = struct.unpack("<HH", data[i + 26 : i + 30])
        # Member data: 2-byte LZMA version, 2-byte properties size, properties.
        data[i + 30 + name_len + extra_len + 4] = 0xFF
        i = data.find(b"PK\x03\x04", i + 4)
    path.write_bytes(bytes(data))
    return path


def _invalid_utf8_name(path: Path) -> Path:
    """Mark every member name as UTF-8 and make its first byte invalid UTF-8."""
    _set_header_field(path, local=6, central=8, value=0x800)  # flag bit 11
    data = bytearray(path.read_bytes())
    for signature, name_offset in ((b"PK\x03\x04", 30), (b"PK\x01\x02", 46)):
        i = data.find(signature)
        while i != -1:
            data[i + name_offset] = 0xFF
            i = data.find(signature, i + 4)
    path.write_bytes(bytes(data))
    return path


def test_zip_slip_entry_rejects_the_archive(tmp_path: Path) -> None:
    zip_path = zip_with(tmp_path, "evil", {"../../outside.kicad_mod": "x"})
    dest = tmp_path / "extract"
    dest.mkdir()

    with pytest.raises(ImportZipError, match="unsafe ZIP entry"):
        extract_part_files(zip_path, dest)
    assert not (tmp_path / "outside.kicad_mod").exists()


def test_only_part_files_are_extracted(tmp_path: Path) -> None:
    zip_path = samacsys_zip(tmp_path, "P")
    with zipfile.ZipFile(zip_path, "a") as zf:
        zf.writestr("P/readme.html", "<html></html>")
        zf.writestr("__MACOSX/P/KiCad/._P.kicad_mod", b"\x00\x05\x16\x07")
        zf.writestr("P/.hidden/P2.kicad_mod", "x")
    dest = tmp_path / "extract"
    dest.mkdir()

    files = extract_part_files(zip_path, dest)

    assert sorted(f.name for f in files) == ["P.kicad_mod", "P.kicad_sym", "P.stp"]


@pytest.mark.parametrize(
    "damage", [_encrypted, _imploded, _corrupt_lzma, _invalid_utf8_name]
)
def test_unreadable_members_fail_only_their_zip(
    tmp_path: Path,
    library_tree: Path,
    mock_config: MagicMock,
    damage: Callable[[Path], Path],
) -> None:
    (tmp_path / "bad").mkdir()
    bad = damage(samacsys_zip(tmp_path / "bad", "BadPart"))
    good = samacsys_zip(tmp_path, "GoodPart")

    result = run_import(str(bad), str(good))

    assert result.exit_code == 1, result.output
    assert "error: LIB_BadPart.zip" in result.output
    assert summary(result.output)[0] == "  Symbols   added: 1"
    sym_text = (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    assert '(symbol "GoodPart"' in sym_text
    assert "BadPart" not in sym_text


def test_macos_metadata_entries_are_ignored(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    zip_path = samacsys_zip(tmp_path, "MacPart")
    with zipfile.ZipFile(zip_path, "a") as zf:
        for name in ("._MacPart.kicad_mod", "._MacPart.kicad_sym", "._MacPart.stp"):
            zf.writestr(f"__MACOSX/MacPart/KiCad/{name}", b"\x00\x05\x16\x07\xff\xfe")

    result = run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert summary(result.output) == [
        "  Symbols   added: 1",
        "  Footprints added: 1",
        "  3D models  added: 1",
    ]
    assert not list((library_tree / "footprints").rglob("._*"))


def test_missing_or_invalid_zip_fails_the_run_after_importing_the_rest(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    not_zip = tmp_path / "notes.zip"
    not_zip.write_text("not a zip")
    good = samacsys_zip(tmp_path, "GoodPart")

    result = run_import(str(tmp_path / "missing.zip"), str(not_zip), str(good))

    assert result.exit_code == 1
    assert "Failed to import: missing.zip, notes.zip" in result.output
    sym_text = (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    assert '(symbol "GoodPart"' in sym_text
