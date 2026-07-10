"""
Tests for the kilm import command.
"""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.commands.import_zip.command import (
    _extract_symbol_blocks,
    _fix_3d_path,
    _fix_footprint_ref,
    _merge_symbols,
    _safe_extractall,
    _symbol_name,
)
from kicad_lib_manager.main import app

runner = CliRunner()

# ── Unit tests for helpers ────────────────────────────────────────────────────

SAMPLE_SYM_LIB = """\
(kicad_symbol_lib
\t(symbol "ExistingPart"
\t\t(property "Footprint" "SAMPLELIB:ExistingPart")
\t)
)
"""

INCOMING_SYM = """\
(kicad_symbol_lib
\t(symbol "NewPart"
\t\t(property "Footprint" "NewPart")
\t)
\t(symbol "ExistingPart"
\t\t(property "Footprint" "SAMPLELIB:ExistingPart")
\t)
)
"""


def test_extract_symbol_blocks():
    blocks = _extract_symbol_blocks(INCOMING_SYM)
    assert len(blocks) == 2
    assert _symbol_name(blocks[0]) == "NewPart"
    assert _symbol_name(blocks[1]) == "ExistingPart"


def test_fix_footprint_ref_adds_prefix():
    block = '\t(property "Footprint" "BareFootprint")'
    result = _fix_footprint_ref(block, "SAMPLELIB")
    assert '"Footprint" "SAMPLELIB:BareFootprint"' in result


def test_fix_footprint_ref_keeps_existing_prefix():
    block = '\t(property "Footprint" "OTHER:Footprint")'
    result = _fix_footprint_ref(block, "SAMPLELIB")
    assert '"Footprint" "OTHER:Footprint"' in result


def test_extract_symbol_blocks_ignores_parens_in_strings():
    # A property value with unbalanced parens must not break depth tracking
    text = (
        "(kicad_symbol_lib\n"
        '\t(symbol "PartA"\n'
        '\t\t(property "Description" "Filter (LC")\n'  # unbalanced ( inside string
        "\t)\n"
        ")\n"
    )
    blocks = _extract_symbol_blocks(text)
    assert len(blocks) == 1
    assert _symbol_name(blocks[0]) == "PartA"


def test_safe_extractall_rejects_zip_slip(tmp_path: Path):
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../outside.txt", "malicious content")
    dest = tmp_path / "extract"
    dest.mkdir()
    with zipfile.ZipFile(zip_path) as zf, pytest.raises(ValueError, match="Unsafe ZIP entry"):
        _safe_extractall(zf, dest)
    assert not (tmp_path / "outside.txt").exists()


def test_fix_3d_path_normalises():
    text = '(model "C:/SamacSys/somepart.stp"'
    result = _fix_3d_path(text, "SAMPLELIB.3dshapes")
    assert "${KICAD_3RD_PARTY}/SAMPLELIB.3dshapes/somepart.stp" in result


@pytest.mark.parametrize(
    "raw",
    [
        '(model "C:/Vendor/somepart.step"',
        '(model "C:/Vendor/somepart.stp.gz"',
        '(model "C:/Vendor/somepart.step.gz"',
        "(model somepart.stp",
        "(model somepart.step",
        "(model somepart.stp.gz",
        "(model somepart.step.gz",
    ],
)
def test_fix_3d_path_handles_all_extensions_without_truncation(raw: str):
    # Regression: chained re.sub passes (or misordered alternation) previously
    # matched a compound extension's own prefix (e.g. "step" inside
    # "step.gz"), leaving the rest of the extension as dangling text.
    result = _fix_3d_path(raw, "SAMPLELIB.3dshapes")
    assert result.count('"') == 2
    assert result.endswith('"')


def test_merge_symbols_adds_new_skips_existing(tmp_path: Path):
    sym_lib = tmp_path / "SAMPLELIB.kicad_sym"
    sym_lib.write_text(SAMPLE_SYM_LIB, encoding="utf-8")

    src = tmp_path / "incoming.kicad_sym"
    src.write_text(INCOMING_SYM, encoding="utf-8")

    added, skipped = _merge_symbols(src, sym_lib, "SAMPLELIB", dry_run=False)
    assert added == ["NewPart"]
    assert skipped == ["ExistingPart"]

    merged = sym_lib.read_text(encoding="utf-8")
    assert "NewPart" in merged
    assert merged.count("ExistingPart") == 2  # original + new


def test_merge_symbols_dry_run_does_not_write(tmp_path: Path):
    sym_lib = tmp_path / "SAMPLELIB.kicad_sym"
    sym_lib.write_text(SAMPLE_SYM_LIB, encoding="utf-8")
    src = tmp_path / "incoming.kicad_sym"
    src.write_text(INCOMING_SYM, encoding="utf-8")

    original_content = sym_lib.read_text(encoding="utf-8")
    added, _ = _merge_symbols(src, sym_lib, "SAMPLELIB", dry_run=True)

    assert added == ["NewPart"]
    assert sym_lib.read_text(encoding="utf-8") == original_content


# ── CLI integration test ──────────────────────────────────────────────────────


def _make_samacsys_zip(tmp_path: Path, part_name: str) -> Path:
    """Build a minimal SamacSys-style ZIP for testing."""
    zip_path = tmp_path / f"LIB_{part_name}.zip"

    sym_content = f"""\
(kicad_symbol_lib
\t(symbol "{part_name}"
\t\t(property "Footprint" "{part_name}")
\t)
)
"""
    fp_content = f"""\
(footprint "{part_name}"
)
"""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{part_name}/KiCad/{part_name}.kicad_sym", sym_content)
        zf.writestr(f"{part_name}/KiCad/{part_name}.kicad_mod", fp_content)
        zf.writestr(f"{part_name}/3D/{part_name}.stp", "STEP data")

    return zip_path


def _make_ultralibrarian_zip(tmp_path: Path, part_name: str) -> Path:
    """Build a minimal UltraLibrarian-style ZIP for testing.

    UltraLibrarian differs from SamacSys/Mouser: the KiCad dir is named
    "KiCADv6" (not "KiCad"), footprints live in a nested "*.pretty" dir,
    and symbol files use 2-space indents with CRLF line endings.
    """
    zip_path = tmp_path / f"ul_{part_name}.zip"

    sym_content = (
        "(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)\r\n"
        f'  (symbol "{part_name}" (in_bom yes) (on_board yes)\r\n'
        f'    (property "Footprint" "{part_name}")\r\n'
        f'    (symbol "{part_name}_0_1"\r\n'
        "    )\r\n"
        "  )\r\n"
        ")\r\n"
    )
    fp_content = f'(footprint "{part_name}"\n)\n'

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{part_name}/KiCADv6/2026-01-01_00-00-00.kicad_sym", sym_content)
        zf.writestr(
            f"{part_name}/KiCADv6/footprints.pretty/{part_name}.kicad_mod", fp_content
        )

    return zip_path


def _make_snapmagic_zip(tmp_path: Path, part_name: str) -> Path:
    """Build a minimal SnapMagic-style ZIP for testing.

    SnapMagic differs from every other vendor: there is no wrapping
    "KiCad"/"3D" dir at all - the .kicad_sym, .kicad_mod, and .step files
    sit directly at the ZIP root.
    """
    zip_path = tmp_path / f"{part_name}.zip"

    sym_content = f"""\
(kicad_symbol_lib
\t(symbol "{part_name}"
\t\t(property "Footprint" "FP_{part_name}")
\t)
)
"""
    fp_content = f"""\
(footprint "FP_{part_name}"
)
"""
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{part_name}.kicad_sym", sym_content)
        zf.writestr(f"FP_{part_name}.kicad_mod", fp_content)
        zf.writestr(f"{part_name}.step", "STEP data")
        zf.writestr("how-to-import.htm", "<html></html>")

    return zip_path


@pytest.fixture
def library_tree(tmp_path: Path) -> Path:
    """Set up a minimal library tree with kilm.yaml."""
    lib = tmp_path / "mylib"
    (lib / "symbols").mkdir(parents=True)
    (lib / "footprints" / "SAMPLELIB.pretty").mkdir(parents=True)
    (lib / "symbols" / "SAMPLELIB.kicad_sym").write_text(
        SAMPLE_SYM_LIB, encoding="utf-8"
    )
    (lib / "kilm.yaml").write_text("name: mylib\n", encoding="utf-8")
    return lib


@pytest.fixture
def mock_config(library_tree: Path, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    config_mock = MagicMock()
    config_mock.get_libraries.return_value = [
        {"name": "mylib", "path": str(library_tree), "type": "github"}
    ]
    monkeypatch.setattr(
        "kicad_lib_manager.commands.import_zip.command.Config", lambda: config_mock
    )
    return config_mock


def test_import_zip_cli_adds_part(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
):
    zip_path = _make_samacsys_zip(tmp_path, "TestPart")

    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        result = runner.invoke(app, ["import", str(zip_path)])

    assert result.exit_code == 0, result.output
    assert "add: TestPart" in result.output

    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    assert "TestPart" in sym_lib.read_text(encoding="utf-8")

    fp_file = library_tree / "footprints" / "SAMPLELIB.pretty" / "TestPart.kicad_mod"
    assert fp_file.exists()

    model_file = library_tree / "SAMPLELIB.3dshapes" / "TestPart.stp"
    assert model_file.exists()


def test_import_zip_cli_dry_run_no_changes(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
):
    zip_path = _make_samacsys_zip(tmp_path, "DryPart")

    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        result = runner.invoke(app, ["import", "--dry-run", str(zip_path)])

    assert result.exit_code == 0, result.output
    assert "add: DryPart" in result.output

    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    assert "DryPart" not in sym_lib.read_text(encoding="utf-8")
    assert not (library_tree / "SAMPLELIB.3dshapes" / "DryPart.stp").exists()


def test_import_zip_cli_adds_ultralibrarian_part(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
):
    zip_path = _make_ultralibrarian_zip(tmp_path, "UlPart")

    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        result = runner.invoke(app, ["import", str(zip_path)])

    assert result.exit_code == 0, result.output
    assert "SYM  add: UlPart" in result.output
    assert "FP   add: UlPart.kicad_mod" in result.output

    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    assert "UlPart" in sym_lib.read_text(encoding="utf-8")

    fp_file = library_tree / "footprints" / "SAMPLELIB.pretty" / "UlPart.kicad_mod"
    assert fp_file.exists()


def test_import_zip_cli_adds_snapmagic_part(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
):
    zip_path = _make_snapmagic_zip(tmp_path, "SnapPart")

    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        result = runner.invoke(app, ["import", str(zip_path)])

    assert result.exit_code == 0, result.output
    assert "SYM  add: SnapPart" in result.output
    assert "FP   add: FP_SnapPart.kicad_mod" in result.output
    assert "3D   add: SnapPart.step" in result.output

    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    assert "SnapPart" in sym_lib.read_text(encoding="utf-8")

    fp_file = library_tree / "footprints" / "SAMPLELIB.pretty" / "FP_SnapPart.kicad_mod"
    assert fp_file.exists()

    model_file = library_tree / "SAMPLELIB.3dshapes" / "SnapPart.step"
    assert model_file.exists()


def test_import_zip_cli_skips_existing(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
):
    zip_path = _make_samacsys_zip(tmp_path, "ExistingPart")

    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        result = runner.invoke(app, ["import", str(zip_path)])

    assert result.exit_code == 0, result.output
    assert "skip (exists): ExistingPart" in result.output
