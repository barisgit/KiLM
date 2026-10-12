"""Tests for ``kilm setup`` against a temporary KiCad configuration."""

import io
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.commands.setup import command as setup_command
from kicad_lib_manager.main import app
from kicad_lib_manager.services.library_service import LibraryService

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
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(
        setup_command, "find_environment_variables", lambda _name: None
    )
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


def _fail_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every file opened for writing fail after it has been opened.

    Opening with ``w`` truncates the file first, so a writer that rewrites the
    target in place loses its content, while an atomic writer loses only its
    temporary file.
    """
    real_open: Callable[..., io.IOBase] = io.open

    def failing_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        handle = real_open(file, mode, *args, **kwargs)
        if "w" in mode:
            handle.close()
            raise OSError(28, "No space left on device")
        return handle

    monkeypatch.setattr(io, "open", failing_open)


def test_fix_invalid_uris_rewrites_wrapped_paths(kicad_config: Path) -> None:
    """A path wrapped in ``${}`` becomes a plain path."""
    table = kicad_config / "sym-lib-table"
    table.write_text(INVALID_URI_TABLE, encoding="utf-8")

    assert setup_command.fix_invalid_uris(kicad_config, backup_first=False)

    assert '(uri "/libs/symbols/Bad.kicad_sym")' in table.read_text(encoding="utf-8")


def test_fix_invalid_uris_keeps_the_table_when_writing_fails(
    kicad_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed write leaves the original table in place."""
    table = kicad_config / "sym-lib-table"
    table.write_text(INVALID_URI_TABLE, encoding="utf-8")
    _fail_writes(monkeypatch)

    with pytest.raises(OSError, match="No space left"):
        setup_command.fix_invalid_uris(kicad_config, backup_first=False)

    assert table.read_text(encoding="utf-8") == INVALID_URI_TABLE
