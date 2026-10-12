"""Tests for ``kilm setup`` against a temporary KiCad configuration."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.commands.setup import changes as setup_changes
from kicad_lib_manager.commands.setup import sources as setup_sources
from kicad_lib_manager.main import app
from kicad_lib_manager.services.library_service import LibraryService
from tests.fault_injection import fail_writes

EMPTY_SYM_TABLE = "(sym_lib_table\n  (version 7)\n)\n"
EMPTY_FP_TABLE = "(fp_lib_table\n  (version 7)\n)\n"
INVALID_URI_TABLE = (
    "(sym_lib_table\n"
    '  (lib (name "Bad")(type "KiCad")(uri "${/libs}/symbols/Bad.kicad_sym")'
    '(options "")(descr ""))\n'
    ")\n"
)


@pytest.fixture
def kicad_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return an isolated KiCad configuration directory that setup finds."""
    monkeypatch.setattr(setup_sources, "find_library_variable", lambda _name: None)
    config = tmp_path / "kicad"
    config.mkdir()
    (config / "sym-lib-table").write_text(EMPTY_SYM_TABLE, encoding="utf-8")
    (config / "fp-lib-table").write_text(EMPTY_FP_TABLE, encoding="utf-8")
    (config / "kicad_common.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        LibraryService, "find_kicad_config", staticmethod(lambda: config)
    )
    return config


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """Return a library directory with one symbol and one footprint library."""
    library = tmp_path / "library"
    (library / "symbols").mkdir(parents=True)
    (library / "symbols" / "Demo.kicad_sym").write_text("", encoding="utf-8")
    (library / "footprints" / "Demo.pretty").mkdir(parents=True)
    return library


def test_setup_backs_up_library_tables_before_changing_them(
    kicad_config: Path, library: Path
) -> None:
    """The backup holds the table as it was before setup added libraries."""
    result = CliRunner().invoke(
        app, ["setup", "--kicad-lib-dir", str(library), "--no-pin-libraries"]
    )

    assert result.exit_code == 0, result.output
    assert '(name "Demo")' in (kicad_config / "sym-lib-table").read_text(
        encoding="utf-8"
    )
    backups = sorted(kicad_config.glob("sym-lib-table.backup.*"))
    assert [b.read_text(encoding="utf-8") for b in backups] == [EMPTY_SYM_TABLE]


def test_fix_invalid_uris_rewrites_wrapped_paths(kicad_config: Path) -> None:
    """A path wrapped in ``${}`` becomes a plain path."""
    table = kicad_config / "sym-lib-table"
    table.write_text(INVALID_URI_TABLE, encoding="utf-8")

    assert setup_changes.fix_invalid_uris(kicad_config)

    assert '(uri "/libs/symbols/Bad.kicad_sym")' in table.read_text(encoding="utf-8")


def test_fix_invalid_uris_keeps_the_table_when_writing_fails(
    kicad_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed write leaves the original table in place."""
    table = kicad_config / "sym-lib-table"
    table.write_text(INVALID_URI_TABLE, encoding="utf-8")
    fail_writes(monkeypatch)

    with pytest.raises(OSError, match="No space left"):
        setup_changes.fix_invalid_uris(kicad_config)

    assert table.read_text(encoding="utf-8") == INVALID_URI_TABLE


def test_setup_keeps_max_backups_when_pinning(
    kicad_config: Path, library: Path
) -> None:
    """Pinning prunes ``kicad_common.json`` backups to ``--max-backups``."""
    kicad_common = kicad_config / "kicad_common.json"
    current_vars = {"KICAD_USER_LIB": library.as_posix()}
    kicad_common.write_text(
        json.dumps({"environment": {"vars": current_vars}}), encoding="utf-8"
    )
    for second in range(3):
        old_backup = kicad_config / f"kicad_common.json.backup.20000101_00000{second}"
        old_backup.write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["setup", "--kicad-lib-dir", str(library), "--max-backups", "1"]
    )

    assert result.exit_code == 0, result.output
    assert "Pinned 1 symbol and 1 footprint libraries" in result.output
    assert len(list(kicad_config.glob("kicad_common.json.backup.*"))) == 1
