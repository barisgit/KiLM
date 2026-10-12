"""The import command end to end: vendor layouts, targets, and dry-run parity."""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from tests.import_zip.helpers import (
    SAMPLE_SYM_LIB,
    run_import,
    samacsys_zip,
    snapmagic_zip,
    summary,
    ultralibrarian_zip,
    zip_with,
)


def _sym_text(library_tree: Path, name: str = "SAMPLELIB") -> str:
    return (library_tree / "symbols" / f"{name}.kicad_sym").read_text(encoding="utf-8")


def test_samacsys_zip_adds_symbol_footprint_and_model(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    result = run_import(str(samacsys_zip(tmp_path, "TestPart")))

    assert result.exit_code == 0, result.output
    assert '"Footprint" "SAMPLELIB:TestPart"' in _sym_text(library_tree)
    assert (
        library_tree / "footprints" / "SAMPLELIB.pretty" / "TestPart.kicad_mod"
    ).exists()
    assert (library_tree / "SAMPLELIB.3dshapes" / "TestPart.stp").exists()


def test_ultralibrarian_zip_adds_part(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    result = run_import(str(ultralibrarian_zip(tmp_path, "UlPart")))

    assert result.exit_code == 0, result.output
    assert "SYM  add: UlPart" in result.output
    assert "FP   add: UlPart.kicad_mod" in result.output
    assert '(symbol "UlPart"' in _sym_text(library_tree)
    assert (
        library_tree / "footprints" / "SAMPLELIB.pretty" / "UlPart.kicad_mod"
    ).exists()


def test_snapmagic_zip_adds_part(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    result = run_import(str(snapmagic_zip(tmp_path, "SnapPart")))

    assert result.exit_code == 0, result.output
    assert "3D   add: SnapPart.step" in result.output
    assert '"Footprint" "SAMPLELIB:FP_SnapPart"' in _sym_text(library_tree)
    fp_dir = library_tree / "footprints" / "SAMPLELIB.pretty"
    assert (fp_dir / "FP_SnapPart.kicad_mod").exists()
    assert (library_tree / "SAMPLELIB.3dshapes" / "SnapPart.step").exists()


def test_dry_run_changes_nothing(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    before = sorted(p.relative_to(library_tree) for p in library_tree.rglob("*"))

    result = run_import("--dry-run", str(samacsys_zip(tmp_path, "DryPart")))

    assert result.exit_code == 0, result.output
    assert "SYM  add: DryPart" in result.output
    assert (
        sorted(p.relative_to(library_tree) for p in library_tree.rglob("*")) == before
    )
    assert _sym_text(library_tree) == SAMPLE_SYM_LIB


def test_existing_parts_are_skipped(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    result = run_import(str(samacsys_zip(tmp_path, "ExistingPart")))

    assert result.exit_code == 0, result.output
    assert "SYM  skip (exists): ExistingPart" in result.output
    assert _sym_text(library_tree).count('(symbol "ExistingPart"') == 1


def test_several_libraries_require_a_choice(
    tmp_path: Path, category_tree: Path
) -> None:
    result = run_import(str(samacsys_zip(tmp_path, "AmbPart")))

    assert result.exit_code == 1
    assert "--symbol-lib" in result.output
    assert "CAT_IC" in result.output


def test_unknown_library_lists_available(tmp_path: Path, category_tree: Path) -> None:
    zip_path = samacsys_zip(tmp_path, "XPart")

    result = run_import(
        "--symbol-lib", "NOPE", "--footprint-lib", "CAT_QFN", str(zip_path)
    )

    assert result.exit_code == 1
    assert "No symbol library 'NOPE'" in result.output


def test_import_into_chosen_category_libraries(
    tmp_path: Path, category_tree: Path
) -> None:
    zip_path = zip_with(
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

    result = run_import("-s", "CAT_IC", "-f", "CAT_QFN", str(zip_path))

    assert result.exit_code == 0, result.output
    assert '"Footprint" "CAT_QFN:VENDFP"' in _sym_text(category_tree, "CAT_IC")
    assert "VendChip" not in _sym_text(category_tree)


def test_missing_kicad_cli_path_stops_before_changes(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    zip_path = samacsys_zip(tmp_path, "CliPart")

    result = run_import(
        "--kicad-cli", str(tmp_path / "nope" / "kicad-cli"), str(zip_path)
    )

    assert result.exit_code == 1
    assert "kicad-cli not found at:" in result.output
    assert "CliPart" not in _sym_text(library_tree)


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

    result = run_import(str(samacsys_zip(tmp_path, "CurPart")))

    assert result.exit_code == 0, result.output
    assert "CurPart" in _sym_text(other, "OTHER")
    assert "CurPart" not in _sym_text(library_tree)


def test_dry_run_matches_real_run_for_parts_repeated_across_zips(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = samacsys_zip(tmp_path / "a", "Twin")
    b = samacsys_zip(tmp_path / "b", "Twin")

    dry = run_import("--dry-run", str(a), str(b))
    real = run_import(str(a), str(b))

    assert real.exit_code == 0, real.output
    assert "Symbols   added: 1" in real.output
    assert summary(dry.output) == summary(real.output)


def test_undecodable_footprint_fails_dry_run_and_writes_nothing(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    zip_path = samacsys_zip(tmp_path, "BadPart")
    with zipfile.ZipFile(zip_path, "a") as zf:
        zf.writestr("BadPart/KiCad/BadFP.kicad_mod", b'(footprint "BadFP" "\xff")\n')
    before = sorted(p.relative_to(library_tree) for p in library_tree.rglob("*"))

    dry = run_import("--dry-run", str(zip_path))
    real = run_import(str(zip_path))

    for result in (dry, real):
        assert result.exit_code == 1, result.output
        assert "BadFP.kicad_mod is not valid UTF-8" in result.output
        assert "add:" not in result.output
    assert (
        sorted(p.relative_to(library_tree) for p in library_tree.rglob("*")) == before
    )
