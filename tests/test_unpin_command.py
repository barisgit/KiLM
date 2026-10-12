"""Tests for ``kilm unpin`` against a temporary KiCad configuration."""

import io
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.main import app
from kicad_lib_manager.services.library_service import LibraryService

CONFLICT = "'--all' cannot be used with '--symbols' or '--footprints'"


@pytest.fixture
def kicad_common(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a kicad_common.json with two pinned symbol and footprint libraries."""
    monkeypatch.setattr(
        LibraryService, "find_kicad_config", staticmethod(lambda: tmp_path)
    )
    path = tmp_path / "kicad_common.json"
    session = {
        "pinned_symbol_libs": ["sym_a", "sym_b"],
        "pinned_fp_libs": ["fp_a", "fp_b"],
        "remember_open_files": False,
    }
    path.write_text(json.dumps({"session": session}, indent=2), encoding="utf-8")
    return path


def _session(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    session = data["session"]
    assert isinstance(session, dict)
    return session


@pytest.mark.parametrize(
    "selection",
    [
        ["--symbols", "lib1"],
        ["--footprints", "lib1"],
        ["--symbols", "lib1", "--footprints", "lib2"],
    ],
)
def test_all_cannot_be_combined_with_a_selection(selection: list[str]) -> None:
    """``--all`` with explicit libraries fails before touching KiCad."""
    result = CliRunner().invoke(app, ["unpin", "--all", *selection])

    assert result.exit_code == 1
    assert CONFLICT in result.output


def test_unpin_without_selection_fails(kicad_common: Path) -> None:
    """Nothing to unpin is an error that names the options."""
    result = CliRunner().invoke(app, ["unpin"])

    assert result.exit_code == 1
    assert "No libraries specified to unpin" in result.output
    assert _session(kicad_common)["pinned_symbol_libs"] == ["sym_a", "sym_b"]


def test_unpin_selected_libraries(kicad_common: Path) -> None:
    """Only the named libraries are unpinned, and a backup is kept."""
    result = CliRunner().invoke(
        app, ["unpin", "--symbols", "sym_a", "--footprints", "fp_b"]
    )

    assert result.exit_code == 0, result.output
    session = _session(kicad_common)
    assert session["pinned_symbol_libs"] == ["sym_b"]
    assert session["pinned_fp_libs"] == ["fp_a"]
    assert session["remember_open_files"] is False
    assert len(list(kicad_common.parent.glob("kicad_common.json.backup.*"))) == 1


def test_unpin_all_libraries(kicad_common: Path) -> None:
    """``--all`` empties both pinned lists."""
    result = CliRunner().invoke(app, ["unpin", "--all"])

    assert result.exit_code == 0, result.output
    assert "Unpinned 2 symbol and 2 footprint libraries" in result.output
    session = _session(kicad_common)
    assert session["pinned_symbol_libs"] == []
    assert session["pinned_fp_libs"] == []


def test_unpin_dry_run_changes_nothing(kicad_common: Path) -> None:
    """A dry run reports the change and leaves the file alone."""
    before = kicad_common.read_text(encoding="utf-8")

    result = CliRunner().invoke(app, ["unpin", "--symbols", "sym_a", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "Would unpin 1 symbol and 0 footprint libraries" in result.output
    assert kicad_common.read_text(encoding="utf-8") == before


def test_unpin_keeps_the_file_when_writing_fails(
    kicad_common: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed write leaves kicad_common.json as it was."""
    before = kicad_common.read_text(encoding="utf-8")
    real_open = io.open

    def failing_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        handle = real_open(file, mode, *args, **kwargs)
        if "w" in mode:
            handle.close()
            raise OSError(28, "No space left on device")
        return handle

    monkeypatch.setattr(io, "open", failing_open)

    result = CliRunner().invoke(app, ["unpin", "--symbols", "sym_a"])

    assert result.exit_code == 1
    assert "No space left on device" in result.output
    assert kicad_common.read_text(encoding="utf-8") == before
