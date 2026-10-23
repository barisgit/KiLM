"""Vendor ZIP builders and CLI helpers shared by the import command tests."""

import zipfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner, Result

from kicad_lib_manager.main import app

runner = CliRunner()

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


def zip_with(tmp_path: Path, name: str, files: dict[str, str | bytes]) -> Path:
    """Write tmp_path/<name>.zip holding files (member name -> content)."""
    zip_path = tmp_path / f"{name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for member, content in files.items():
            zf.writestr(member, content)
    return zip_path


def samacsys_zip(tmp_path: Path, part: str) -> Path:
    """SamacSys/Mouser layout: <part>/KiCad/ for KiCad files, <part>/3D/ for models."""
    return zip_with(
        tmp_path,
        f"LIB_{part}",
        {
            f"{part}/KiCad/{part}.kicad_sym": (
                f'(kicad_symbol_lib\n\t(symbol "{part}"\n'
                f'\t\t(property "Footprint" "{part}")\n\t)\n)\n'
            ),
            f"{part}/KiCad/{part}.kicad_mod": f'(footprint "{part}"\n)\n',
            f"{part}/3D/{part}.stp": "STEP data",
        },
    )


def ultralibrarian_zip(tmp_path: Path, part: str) -> Path:
    """UltraLibrarian layout: a "KiCADv6" dir with a nested "*.pretty" dir.

    Symbol files use 2-space indents and CRLF line endings.
    """
    sym = (
        "(kicad_symbol_lib (version 20211014) (generator kicad_symbol_editor)\r\n"
        f'  (symbol "{part}" (in_bom yes) (on_board yes)\r\n'
        f'    (property "Footprint" "{part}")\r\n'
        f'    (symbol "{part}_0_1"\r\n'
        "    )\r\n"
        "  )\r\n"
        ")\r\n"
    )
    return zip_with(
        tmp_path,
        f"ul_{part}",
        {
            f"{part}/KiCADv6/2026-01-01_00-00-00.kicad_sym": sym,
            f"{part}/KiCADv6/footprints.pretty/{part}.kicad_mod": (
                f'(footprint "{part}"\n)\n'
            ),
        },
    )


def snapmagic_zip(tmp_path: Path, part: str) -> Path:
    """SnapMagic layout: every file at the ZIP root, plus an HTML how-to."""
    return zip_with(
        tmp_path,
        part,
        {
            f"{part}.kicad_sym": (
                f'(kicad_symbol_lib\n\t(symbol "{part}"\n'
                f'\t\t(property "Footprint" "FP_{part}")\n\t)\n)\n'
            ),
            f"FP_{part}.kicad_mod": f'(footprint "FP_{part}"\n)\n',
            f"{part}.step": "STEP data",
            "how-to-import.htm": "<html></html>",
        },
    )


def run_import(*args: str) -> Result:
    """Run 'kilm import' with args, without kicad-cli."""
    with patch(
        "kicad_lib_manager.commands.import_zip.command.detect_kicad_cli",
        return_value=None,
    ):
        return runner.invoke(app, ["import", *args])


def summary(output: str) -> list[str]:
    """The three count lines of the run summary."""
    return output[output.index("Summary:") :].splitlines()[1:4]
