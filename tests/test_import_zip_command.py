"""
Tests for the kilm import command.
"""

import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import Result
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


@pytest.fixture(autouse=True)
def _fixed_console_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin terminal width so Rich doesn't wrap output lines differently per host."""
    monkeypatch.setenv("COLUMNS", "200")


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


def test_extract_symbol_blocks() -> None:
    blocks = _extract_symbol_blocks(INCOMING_SYM)
    assert len(blocks) == 2
    assert _symbol_name(blocks[0]) == "NewPart"
    assert _symbol_name(blocks[1]) == "ExistingPart"


def test_fix_footprint_ref_adds_prefix() -> None:
    block = '\t(property "Footprint" "BareFootprint")'
    result = _fix_footprint_ref(block, "SAMPLELIB")
    assert '"Footprint" "SAMPLELIB:BareFootprint"' in result


def test_fix_footprint_ref_keeps_existing_prefix() -> None:
    block = '\t(property "Footprint" "OTHER:Footprint")'
    result = _fix_footprint_ref(block, "SAMPLELIB")
    assert '"Footprint" "OTHER:Footprint"' in result


def test_extract_symbol_blocks_ignores_parens_in_strings() -> None:
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


def test_safe_extractall_rejects_zip_slip(tmp_path: Path) -> None:
    zip_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../../outside.txt", "malicious content")
    dest = tmp_path / "extract"
    dest.mkdir()
    with (
        zipfile.ZipFile(zip_path) as zf,
        pytest.raises(ValueError, match="Unsafe ZIP entry"),
    ):
        _safe_extractall(zf, dest)
    assert not (tmp_path / "outside.txt").exists()


def test_fix_3d_path_normalises() -> None:
    text = '(model "C:/SamacSys/somepart.stp"'
    result = _fix_3d_path(text, "${KICAD_3RD_PARTY}/SAMPLELIB.3dshapes")
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
def test_fix_3d_path_handles_all_extensions_without_truncation(raw: str) -> None:
    # Regression: chained re.sub passes (or misordered alternation) previously
    # matched a compound extension's own prefix (e.g. "step" inside
    # "step.gz"), leaving the rest of the extension as dangling text.
    result = _fix_3d_path(raw, "${KICAD_3RD_PARTY}/SAMPLELIB.3dshapes")
    assert result.count('"') == 2
    assert result.endswith('"')


def test_merge_symbols_adds_new_skips_existing(tmp_path: Path) -> None:
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


def test_merge_symbols_dry_run_does_not_write(tmp_path: Path) -> None:
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
    libs = [{"name": "mylib", "path": str(library_tree), "type": "github"}]
    config_mock.libs = libs
    config_mock.get_libraries.side_effect = lambda library_type=None: [
        lib for lib in libs if library_type in (None, lib["type"])
    ]
    monkeypatch.setattr(
        "kicad_lib_manager.commands.import_zip.command.Config", lambda: config_mock
    )
    return config_mock


def test_import_zip_cli_adds_part(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
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
) -> None:
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
) -> None:
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
) -> None:
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
) -> None:
    zip_path = _make_samacsys_zip(tmp_path, "ExistingPart")

    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        result = runner.invoke(app, ["import", str(zip_path)])

    assert result.exit_code == 0, result.output
    assert "skip (exists): ExistingPart" in result.output


# ── Category libraries ────────────────────────────────────────────────────────


@pytest.fixture
def category_tree(library_tree: Path, mock_config: MagicMock) -> Path:
    """Split library: two symbol libs, two footprint libs, a registered 3D lib."""
    (library_tree / "symbols" / "CAT_IC.kicad_sym").write_text(
        SAMPLE_SYM_LIB, encoding="utf-8"
    )
    (library_tree / "footprints" / "CAT_QFN.pretty").mkdir()
    models = library_tree / "CAT.3dshapes"
    models.mkdir()
    (models / ".kilm_metadata").write_text(
        '{"env_var": "KICAD_3D_CAT_MODELS"}', encoding="utf-8"
    )
    mock_config.libs.append({"name": "cat-3d", "path": str(models), "type": "cloud"})
    return library_tree


def _run_import(*args: str) -> Result:
    with patch(
        "kicad_lib_manager.commands.import_zip.command._detect_kicad_cli",
        return_value=None,
    ):
        return runner.invoke(app, ["import", *args])


def test_import_zip_requires_lib_choice_when_several(
    tmp_path: Path, category_tree: Path
) -> None:
    result = _run_import(str(_make_samacsys_zip(tmp_path, "AmbPart")))

    assert result.exit_code == 1
    assert "--symbol-lib" in result.output
    assert "CAT_IC" in result.output


def test_import_zip_unknown_lib_lists_available(
    tmp_path: Path, category_tree: Path
) -> None:
    result = _run_import(
        "--symbol-lib",
        "NOPE",
        "--footprint-lib",
        "CAT_QFN",
        str(_make_samacsys_zip(tmp_path, "XPart")),
    )

    assert result.exit_code == 1
    assert "No symbol library 'NOPE'" in result.output


def test_import_zip_into_category_libs(tmp_path: Path, category_tree: Path) -> None:
    zip_path = _make_samacsys_zip(tmp_path, "CatPart")
    with zipfile.ZipFile(zip_path, "a") as zf:
        zf.writestr(
            "CatPart/KiCad/CatPartFP.kicad_mod",
            '(footprint "CatPartFP"\n\t(model "C:/x/CatPart.stp"\n\t)\n)\n',
        )

    result = _run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    sym_text = (category_tree / "symbols" / "CAT_IC.kicad_sym").read_text()
    assert '"Footprint" "CAT_QFN:CatPart"' in sym_text
    assert (
        "CatPart" not in (category_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    )

    fp = category_tree / "footprints" / "CAT_QFN.pretty" / "CatPartFP.kicad_mod"
    assert '(model "${KICAD_3D_CAT_MODELS}/CatPart.stp"' in fp.read_text()
    assert (category_tree / "CAT.3dshapes" / "CatPart.stp").exists()
    assert not (category_tree / "CAT_IC.3dshapes").exists()


def test_import_zip_rejects_missing_kicad_cli_path(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    zip_path = _make_samacsys_zip(tmp_path, "CliPart")

    result = runner.invoke(
        app,
        ["import", "--kicad-cli", str(tmp_path / "nope" / "kicad-cli"), str(zip_path)],
    )

    assert result.exit_code == 1
    assert "kicad-cli not found at:" in result.output
    assert (
        "CliPart" not in (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    )


def _zip_with(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    zip_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for member, content in files.items():
            zf.writestr(member, content)
    return zip_path


def test_vendor_footprint_prefix_is_replaced_for_imported_footprint(
    tmp_path: Path, category_tree: Path
) -> None:
    zip_path = _zip_with(
        tmp_path,
        "VendChip",
        {
            "VendChip/KiCad/VendChip.kicad_sym": (
                '(kicad_symbol_lib\n\t(symbol "VendChip"\n'
                '\t\t(property "Footprint" "SamacSys_Parts:VENDFP")\n\t)\n)\n'
            ),
            "VendChip/KiCad/VENDFP.kicad_mod": '(footprint "VENDFP")\n',
        },
    )

    result = _run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    text = (category_tree / "symbols" / "CAT_IC.kicad_sym").read_text()
    assert '"Footprint" "CAT_QFN:VENDFP"' in text


def test_fallback_models_use_library_env_var(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    (library_tree / "kilm.yaml").write_text(
        "name: mylib\nenv_var: KICAD_LIB_MYLIB\n", encoding="utf-8"
    )
    zip_path = _zip_with(
        tmp_path,
        "M1",
        {
            "M1/KiCad/M1.kicad_sym": '(kicad_symbol_lib\n\t(symbol "M1"\n\t)\n)\n',
            "M1/KiCad/M1.kicad_mod": '(footprint "M1"\n\t(model "C:/x/M1.stp"\n\t)\n)\n',
            "M1/3D/M1.stp": "STEP",
        },
    )

    result = _run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    fp = (library_tree / "footprints" / "SAMPLELIB.pretty" / "M1.kicad_mod").read_text()
    assert '(model "${KICAD_LIB_MYLIB}/SAMPLELIB.3dshapes/M1.stp"' in fp


def test_fallback_models_without_env_var_use_absolute_path(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    zip_path = _zip_with(
        tmp_path,
        "M2",
        {
            "M2/KiCad/M2.kicad_mod": '(footprint "M2"\n\t(model "M2.stp"\n\t)\n)\n',
            "M2/3D/M2.stp": "STEP",
        },
    )

    result = _run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    fp = (library_tree / "footprints" / "SAMPLELIB.pretty" / "M2.kicad_mod").read_text()
    assert "KICAD_3RD_PARTY" not in fp
    assert (library_tree / "SAMPLELIB.3dshapes").resolve().as_posix() in fp


def test_split_library_fallback_models_dir_named_after_library(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    (library_tree / "symbols" / "OTHER.kicad_sym").write_text(SAMPLE_SYM_LIB)
    zip_path = _zip_with(
        tmp_path,
        "M3",
        {
            "M3/KiCad/M3.kicad_mod": '(footprint "M3"\n\t(model "M3.stp"\n\t)\n)\n',
            "M3/3D/M3.stp": "STEP",
        },
    )

    result = _run_import("-s", "SAMPLELIB", str(zip_path))

    assert result.exit_code == 0, result.output
    assert (library_tree / f"{library_tree.name}.3dshapes" / "M3.stp").exists()
    assert "3D model paths will be absolute to this machine" in result.output


def test_models_dir_prefers_library_named_dir(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    (library_tree / "AAA.3dshapes").mkdir()
    (library_tree / "SAMPLELIB.3dshapes").mkdir()
    zip_path = _zip_with(tmp_path, "M4", {"M4/3D/M4.stp": "STEP"})

    result = _run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert (library_tree / "SAMPLELIB.3dshapes" / "M4.stp").exists()
    assert not (library_tree / "AAA.3dshapes" / "M4.stp").exists()


def test_model_in_other_models_dir_is_reused(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    (library_tree / "Aaa.3dshapes").mkdir()
    (library_tree / "Bbb.3dshapes").mkdir()
    (library_tree / "Bbb.3dshapes" / "Part.step").write_text("STEP")
    (library_tree / "kilm.yaml").write_text("name: mylib\nenv_var: KICAD_LIB_MYLIB\n")
    zip_path = _zip_with(
        tmp_path,
        "Reuse",
        {
            "R/KiCad/RFP.kicad_mod": '(footprint "RFP"\n\t(model "x/Part.step"\n\t)\n)\n',
            "R/3D/Part.step": "STEP",
        },
    )

    result = _run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert (
        "3D   reuse existing ${KICAD_LIB_MYLIB}/Bbb.3dshapes/Part.step for Part.step"
        in result.output
    )
    assert not (library_tree / "Aaa.3dshapes" / "Part.step").exists()
    fp = (
        library_tree / "footprints" / "SAMPLELIB.pretty" / "RFP.kicad_mod"
    ).read_text()
    assert '(model "${KICAD_LIB_MYLIB}/Bbb.3dshapes/Part.step"' in fp


def test_dry_run_counts_shared_model_once(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    a = _zip_with(tmp_path, "a", {"A/3D/Shared.step": "STEP"})
    b = _zip_with(tmp_path, "b", {"B/3D/Shared.step": "STEP"})

    result = _run_import("--dry-run", str(a), str(b))

    assert result.exit_code == 0, result.output
    assert result.output.count("3D   add: Shared.step") == 1


def test_fix_3d_path_handles_windows_separators() -> None:
    text = '(model "C:\\\\Vendor\\\\3D\\\\part.step"'

    assert _fix_3d_path(text, "${LIB}") == '(model "${LIB}/part.step"'


def test_absolute_paths_from_other_model_dirs_are_warned(
    tmp_path: Path, category_tree: Path
) -> None:
    (category_tree / "Old.3dshapes").mkdir()
    (category_tree / "Old.3dshapes" / "Legacy.step").write_text("STEP")
    zip_path = _zip_with(tmp_path, "W", {"W/3D/New.step": "STEP"})

    result = _run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    assert "3D model paths will be absolute to this machine" in result.output


def test_merge_symbols_adds_repeated_name_once(tmp_path: Path) -> None:
    sym_lib = tmp_path / "SAMPLELIB.kicad_sym"
    sym_lib.write_text(SAMPLE_SYM_LIB, encoding="utf-8")
    src = tmp_path / "src.kicad_sym"
    src.write_text(
        '(kicad_symbol_lib\n\t(symbol "Twice"\n\t)\n\t(symbol "Twice"\n\t)\n)\n'
    )

    added, skipped = _merge_symbols(src, sym_lib, "SAMPLELIB", dry_run=False)

    assert added == ["Twice"]
    assert skipped == ["Twice"]
    assert sym_lib.read_text().count('(symbol "Twice"') == 1


def test_dry_run_reports_model_added_earlier_as_skip(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    a = _zip_with(tmp_path, "a", {"A/3D/Shared.step": "STEP"})
    b = _zip_with(tmp_path, "b", {"B/3D/Shared.step": "STEP"})

    result = _run_import("--dry-run", str(a), str(b))

    assert "3D   skip (exists): Shared.step" in result.output
    assert "reuse existing" not in result.output


def test_hidden_files_in_model_dirs_are_ignored(
    tmp_path: Path, category_tree: Path
) -> None:
    # A .DS_Store in an extra dir without a library env var must not count as
    # a model (it would trigger the absolute-path warning on its own).
    (category_tree / "Old.3dshapes").mkdir()
    (category_tree / "Old.3dshapes" / ".DS_Store").write_text("x")
    zip_path = _zip_with(tmp_path, "H", {"H/3D/New.step": "STEP"})

    result = _run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    assert "absolute to this machine" not in result.output


# -- Regression tests: format versions, dry-run parity, archive hygiene -------

NEW_FORMAT = 20260206
LEGACY_FP = (
    '(module "OldFP" (layer F.Cu)\n  (model OldPart.stp\n    (at (xyz 0 0 0))\n  )\n)\n'
)
OLD_SYM = (
    "(kicad_symbol_lib (version 20211014) (generator SamacSys_ECAD_Model)\n"
    '  (symbol "OldPart" (in_bom yes) (on_board yes)\n'
    '    (property "Footprint" "OldFP" (id 2) (at 0 0 0))\n'
    "  )\n"
    ")\n"
)


def _old_format_zip(tmp_path: Path) -> Path:
    """SamacSys-style ZIP with a 20211014 symbol and a legacy (module ...) footprint."""
    return _zip_with(
        tmp_path,
        "LIB_OldPart",
        {
            "OldPart/KiCad/OldPart.kicad_sym": OLD_SYM,
            "OldPart/KiCad/OldFP.kicad_mod": LEGACY_FP,
            "OldPart/3D/OldPart.stp": "STEP",
        },
    )


def _fake_kicad_cli(
    cmd: list[str], **_kwargs: object
) -> subprocess.CompletedProcess[str]:
    """Stand-in for kicad-cli that upgrades files to NEW_FORMAT."""
    if cmd[1:3] == ["fp", "upgrade"]:
        out_dir = Path(cmd[cmd.index("--output") + 1])
        out_dir.mkdir()
        for src in Path(cmd[-1]).iterdir():
            (out_dir / src.name).write_text(
                f'(footprint "{src.stem}"\n\t(version {NEW_FORMAT})\n)\n',
                encoding="utf-8",
            )
    elif cmd[1:3] == ["sym", "upgrade"]:
        path = Path(cmd[-1])
        text = path.read_text(encoding="utf-8").replace("20211014", str(NEW_FORMAT))
        path.write_text(
            text.replace("(on_board yes)", "(on_board yes) (embedded_fonts no)"),
            encoding="utf-8",
        )
    return subprocess.CompletedProcess(cmd, 0, "", "")


def _import_with_fake_cli(tmp_path: Path, *args: str) -> Result:
    cli = tmp_path / "kicad-cli"
    cli.write_text("", encoding="utf-8")
    with patch(
        "kicad_lib_manager.commands.import_zip.command.subprocess.run",
        side_effect=_fake_kicad_cli,
    ):
        return runner.invoke(app, ["import", "--kicad-cli", str(cli), *args])


def test_upgrade_never_makes_library_format_newer(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    # A library saved by KiCad 8 must stay loadable by KiCad 8 even when the
    # importing machine has a newer kicad-cli.
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    sym_lib.write_text(
        SAMPLE_SYM_LIB.replace(
            "(kicad_symbol_lib", "(kicad_symbol_lib\n\t(version 20231120)"
        ),
        encoding="utf-8",
    )
    fp_dir = library_tree / "footprints" / "SAMPLELIB.pretty"
    (fp_dir / "Existing.kicad_mod").write_text(
        '(footprint "Existing"\n\t(version 20240108)\n)\n', encoding="utf-8"
    )

    result = _import_with_fake_cli(tmp_path, str(_old_format_zip(tmp_path)))

    assert result.exit_code == 0, result.output
    sym_text = sym_lib.read_text(encoding="utf-8")
    assert '(symbol "OldPart"' in sym_text
    assert str(NEW_FORMAT) not in sym_text
    assert "embedded_fonts" not in sym_text
    fp_text = (fp_dir / "OldFP.kicad_mod").read_text(encoding="utf-8")
    assert fp_text.startswith("(module")
    assert "SAMPLELIB.3dshapes/OldPart.stp" in fp_text


def test_upgrade_applies_when_library_format_allows(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    sym_lib.write_text(
        SAMPLE_SYM_LIB.replace(
            "(kicad_symbol_lib", f"(kicad_symbol_lib\n\t(version {NEW_FORMAT})"
        ),
        encoding="utf-8",
    )

    result = _import_with_fake_cli(tmp_path, str(_old_format_zip(tmp_path)))

    assert result.exit_code == 0, result.output
    assert "embedded_fonts" in sym_lib.read_text(encoding="utf-8")
    fp = library_tree / "footprints" / "SAMPLELIB.pretty" / "OldFP.kicad_mod"
    assert f"(version {NEW_FORMAT})" in fp.read_text(encoding="utf-8")


def _summary(output: str) -> list[str]:
    return output[output.index("Summary:") :].splitlines()[1:4]


def test_dry_run_matches_real_run_for_parts_repeated_across_zips(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _make_samacsys_zip(tmp_path / "a", "Twin")
    b = _make_samacsys_zip(tmp_path / "b", "Twin")

    dry = _run_import("--dry-run", str(a), str(b))
    real = _run_import(str(a), str(b))

    assert real.exit_code == 0, real.output
    assert "Symbols   added: 1" in real.output
    assert _summary(dry.output) == _summary(real.output)


def test_macos_metadata_entries_are_ignored(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    zip_path = _make_samacsys_zip(tmp_path, "MacPart")
    with zipfile.ZipFile(zip_path, "a") as zf:
        for name in ("._MacPart.kicad_mod", "._MacPart.kicad_sym", "._MacPart.stp"):
            zf.writestr(f"__MACOSX/MacPart/KiCad/{name}", b"\x00\x05\x16\x07\xff\xfe")

    result = _run_import(str(zip_path))

    assert result.exit_code == 0, result.output
    assert _summary(result.output) == [
        "  Symbols   added: 1",
        "  Footprints added: 1",
        "  3D models  added: 1",
    ]
    assert not list((library_tree / "footprints").rglob("._*"))


def test_missing_zip_fails_the_run_after_importing_the_rest(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    good = _make_samacsys_zip(tmp_path, "GoodPart")

    result = _run_import(str(tmp_path / "missing.zip"), str(good))

    assert result.exit_code == 1
    assert "missing.zip" in result.output
    sym_text = (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    assert '(symbol "GoodPart"' in sym_text


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_written_files_keep_library_line_endings(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock, newline: str
) -> None:
    # Rewriting every line ending of a git-tracked library (Windows text-mode
    # writes, or CRLF vendor files) would bury the import in a whole-file diff.
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    sym_lib.write_bytes(SAMPLE_SYM_LIB.replace("\n", newline).encode())

    result = _run_import(str(_make_ultralibrarian_zip(tmp_path, "EolPart")))

    assert result.exit_code == 0, result.output
    data = sym_lib.read_bytes()
    assert b'(symbol "EolPart"' in data
    rest = data.replace(newline.encode(), b"")
    assert b"\r" not in rest
    assert b"\n" not in rest
    fp = library_tree / "footprints" / "SAMPLELIB.pretty" / "EolPart.kicad_mod"
    assert b"\r" not in fp.read_bytes()


def test_default_library_is_the_current_library(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    # Like setup and template, import targets the library made current by
    # 'kilm init' / 'kilm config set-default', not merely the first one.
    other = tmp_path / "other"
    (other / "symbols").mkdir(parents=True)
    (other / "footprints" / "OTHER.pretty").mkdir(parents=True)
    (other / "symbols" / "OTHER.kicad_sym").write_text(SAMPLE_SYM_LIB, encoding="utf-8")
    mock_config.libs.append({"name": "other", "path": str(other), "type": "github"})
    mock_config.get_symbol_library_path.return_value = str(other)

    result = _run_import(str(_make_samacsys_zip(tmp_path, "CurPart")))

    assert result.exit_code == 0, result.output
    assert "CurPart" in (other / "symbols" / "OTHER.kicad_sym").read_text()
    assert (
        "CurPart" not in (library_tree / "symbols" / "SAMPLELIB.kicad_sym").read_text()
    )
