"""Tests for creating KiLM libraries."""

from pathlib import Path

import pytest
import yaml

from kicad_lib_manager.services import library_service
from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.metadata import read_github_metadata, write_github_metadata

ALL_CAPABILITIES = {"symbols": True, "footprints": True, "templates": True}


def test_new_library_gets_folders_and_metadata(tmp_path: Path) -> None:
    """A new library is named as given, with a variable derived from the name."""
    metadata = LibraryService.initialize_library(
        tmp_path, name="My Parts", description="Shared parts"
    )

    assert all((tmp_path / folder).is_dir() for folder in ALL_CAPABILITIES)
    assert metadata["name"] == "My Parts"
    assert metadata["description"] == "Shared parts"
    assert metadata["env_var"] == "KICAD_LIB_MY_PARTS"
    assert metadata["capabilities"] == ALL_CAPABILITIES
    assert read_github_metadata(tmp_path) == metadata


def test_new_library_without_environment_variable(tmp_path: Path) -> None:
    """no_env_var leaves the variable out of new metadata."""
    metadata = LibraryService.initialize_library(tmp_path, no_env_var=True)

    assert "env_var" not in metadata
    assert metadata["name"] == tmp_path.name


def test_existing_metadata_is_kept_with_overrides(tmp_path: Path) -> None:
    """Existing fields survive; given ones replace them and mark the update."""
    write_github_metadata(
        tmp_path,
        {"name": "old", "version": "2.0.0", "env_var": "OLD", "created_with": "me"},
    )

    metadata = LibraryService.initialize_library(tmp_path, env_var="NEW_VAR")

    assert metadata["name"] == "old"
    assert metadata["version"] == "2.0.0"
    assert metadata["env_var"] == "NEW_VAR"
    assert metadata["updated_with"] == "kilm"
    assert read_github_metadata(tmp_path) == metadata


def test_init_keeps_entries_the_typed_metadata_cannot_hold(tmp_path: Path) -> None:
    """Non-string keys and mistyped fields survive; a refused variable goes."""
    (tmp_path / "kilm.yaml").write_text(
        "2026: retained\nname: old\nversion: 2\nenv_var: 5\n", encoding="utf-8"
    )

    LibraryService.initialize_library(tmp_path, no_env_var=True)

    written = yaml.safe_load((tmp_path / "kilm.yaml").read_text(encoding="utf-8"))
    assert written[2026] == "retained"
    assert written["name"] == "old"
    assert written["version"] == 2
    assert "env_var" not in written


def test_force_replaces_existing_metadata(tmp_path: Path) -> None:
    """With force, the metadata starts fresh."""
    write_github_metadata(tmp_path, {"name": "old", "version": "2.0.0"})

    metadata = LibraryService.initialize_library(tmp_path, force=True)

    assert metadata["name"] == tmp_path.name
    assert metadata["version"] == "1.0.0"


def test_unwritable_metadata_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A metadata file that cannot be written is an error, not a silent success."""
    monkeypatch.setattr(
        library_service,
        "write_github_metadata",
        lambda _directory, _metadata, _unsupported: False,
    )

    with pytest.raises(OSError, match=r"kilm\.yaml"):
        LibraryService.initialize_library(tmp_path)
