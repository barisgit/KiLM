"""Tests for the ``kilm add-3d`` command."""

import json
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from kicad_lib_manager.main import app
from kicad_lib_manager.utils.constants import CLOUD_METADATA_FILE


def _models_dir(tmp_path: Path, metadata: dict[str, object]) -> Path:
    """Return a directory with one model and the given cloud metadata."""
    directory = tmp_path / "models"
    directory.mkdir()
    (directory / "part.step").write_text("", encoding="utf-8")
    (directory / CLOUD_METADATA_FILE).write_text(json.dumps(metadata), encoding="utf-8")
    return directory


def _add_3d(directory: Path, *options: str) -> dict[str, object]:
    """Run add-3d on directory and return the metadata it leaves behind."""
    result = CliRunner().invoke(
        app, ["add-3d", "--directory", str(directory), *options]
    )
    assert result.exit_code == 0, result.output
    text = (directory / CLOUD_METADATA_FILE).read_text(encoding="utf-8")
    loaded: object = json.loads(text)
    assert isinstance(loaded, dict)
    return cast("dict[str, object]", loaded)


def test_add_3d_keeps_fields_the_typed_metadata_cannot_hold(tmp_path: Path) -> None:
    """Rewriting the metadata keeps mistyped known fields as they were."""
    directory = _models_dir(
        tmp_path,
        {"name": "models", "version": 2, "description": None, "maintainer": "Ada"},
    )

    metadata = _add_3d(directory)

    assert metadata["version"] == 2
    assert metadata["description"] is None
    assert metadata["maintainer"] == "Ada"
    assert metadata["model_count"] == 1


def test_add_3d_overrides_replace_mistyped_fields(tmp_path: Path) -> None:
    """Given options win over kept fields; --no-env-var clears the variable."""
    directory = _models_dir(
        tmp_path,
        {"name": "models", "version": 2, "description": None, "env_var": 5},
    )

    metadata = _add_3d(directory, "--description", "Parts", "--no-env-var")

    assert metadata["description"] == "Parts"
    assert metadata["env_var"] is None
    assert metadata["version"] == 2


def test_add_3d_force_starts_fresh(tmp_path: Path) -> None:
    """--force replaces the metadata, mistyped fields included."""
    directory = _models_dir(tmp_path, {"name": "old", "version": 2})

    metadata = _add_3d(directory, "--force")

    assert metadata["name"] == "models"
    assert metadata["version"] == "1.0.0"
