"""Tests for the ``kilm init`` command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from kicad_lib_manager.main import app


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return an empty library directory, made current, with a private home."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    directory = tmp_path / "library"
    directory.mkdir()
    monkeypatch.chdir(directory)
    return directory


def test_init_reports_which_folders_it_created(library: Path) -> None:
    """Init separates folders that already existed from the ones it created."""
    (library / "symbols").mkdir()

    result = CliRunner().invoke(app, ["init", "--name", "parts"], env={"COLUMNS": "200"})

    assert result.exit_code == 0, result.output
    assert "Found existing folders: symbols\n" in result.output
    assert "Created new folders: footprints, templates\n" in result.output
    assert (library / "footprints").is_dir()
    assert (library / "templates").is_dir()
