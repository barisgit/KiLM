"""Format limits: imports never make a library newer than its KiCad reads."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import Result

from kicad_lib_manager.main import app

from .helpers import SAMPLE_SYM_LIB, run_import, runner, samacsys_zip, zip_with

KICAD8_SYM = 20231120
KICAD8_FP = 20240108
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
NEW_SYM = (
    f"(kicad_symbol_lib\n\t(version {NEW_FORMAT})\n"
    '\t(symbol "NewPart"\n\t\t(embedded_fonts no)\n\t)\n)\n'
)


def _old_format_zip(tmp_path: Path) -> Path:
    """SamacSys-style ZIP with a 20211014 symbol and a legacy (module ...) footprint."""
    return zip_with(
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
        "kicad_lib_manager.commands.import_zip.kicad_cli.subprocess.run",
        side_effect=_fake_kicad_cli,
    ):
        return runner.invoke(app, ["import", "--kicad-cli", str(cli), *args])


def _kicad8_library(library_tree: Path) -> tuple[Path, Path]:
    """Stamp library_tree with KiCad 8 formats; return (symbol lib, footprint dir)."""
    sym_lib = library_tree / "symbols" / "SAMPLELIB.kicad_sym"
    sym_lib.write_text(
        SAMPLE_SYM_LIB.replace(
            "(kicad_symbol_lib", f"(kicad_symbol_lib\n\t(version {KICAD8_SYM})"
        ),
        encoding="utf-8",
    )
    fp_dir = library_tree / "footprints" / "SAMPLELIB.pretty"
    (fp_dir / "Existing.kicad_mod").write_text(
        f'(footprint "Existing"\n\t(version {KICAD8_FP})\n)\n', encoding="utf-8"
    )
    return sym_lib, fp_dir


def test_upgrade_never_makes_library_format_newer(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    # A library saved by KiCad 8 must stay loadable by KiCad 8 even when the
    # importing machine has a newer kicad-cli.
    sym_lib, fp_dir = _kicad8_library(library_tree)

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


def test_newer_vendor_symbols_are_rejected(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    # Merged under the library's 20231120 header, KiCad 8 would reject the
    # newer embedded_fonts token and with it the whole library.
    sym_lib, _ = _kicad8_library(library_tree)
    before = sym_lib.read_bytes()
    newer = zip_with(
        tmp_path,
        "newer",
        {"N/KiCad/NewPart.kicad_sym": NEW_SYM, "N/3D/NewPart.stp": "STEP"},
    )
    good = samacsys_zip(tmp_path, "GoodPart")

    dry = run_import("--dry-run", str(newer))
    result = run_import(str(newer), str(good))

    assert dry.exit_code == 1, dry.output
    assert result.exit_code == 1, result.output
    assert f"uses format {NEW_FORMAT}, newer than SAMPLELIB.kicad_sym" in result.output
    assert "kicad-cli sym upgrade" in result.output
    assert '(symbol "GoodPart"' in sym_lib.read_text()
    assert "embedded_fonts" not in sym_lib.read_text()
    # Everything before the closing parenthesis is kept byte for byte.
    assert sym_lib.read_bytes().startswith(before.rstrip()[:-1])
    assert not (library_tree / "SAMPLELIB.3dshapes" / "NewPart.stp").exists()


def test_newer_vendor_footprints_are_rejected(
    tmp_path: Path, library_tree: Path, mock_config: MagicMock
) -> None:
    _, fp_dir = _kicad8_library(library_tree)
    zip_path = zip_with(
        tmp_path,
        "newer",
        {
            "N/KiCad/NewFP.kicad_mod": f'(footprint "NewFP"\n\t(version {NEW_FORMAT})\n)\n'
        },
    )

    result = run_import(str(zip_path))

    assert result.exit_code == 1, result.output
    assert "kicad-cli fp upgrade" in result.output
    assert not (fp_dir / "NewFP.kicad_mod").exists()
