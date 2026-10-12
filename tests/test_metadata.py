"""Tests for reading and writing library metadata files."""

from pathlib import Path

import pytest

from kicad_lib_manager.utils.metadata import (
    generate_env_var_name,
    read_cloud_metadata,
    read_github_metadata,
    write_github_metadata,
)


def test_known_fields_are_checked_and_unknown_fields_kept(tmp_path: Path) -> None:
    """A known field of the wrong type reads as absent; other fields survive."""
    (tmp_path / "kilm.yaml").write_text(
        "name: mylib\nversion: 2\nenv_var: null\nmaintainer: Ada\n",
        encoding="utf-8",
    )

    metadata = read_github_metadata(tmp_path)

    assert metadata == {"name": "mylib", "env_var": None, "maintainer": "Ada"}


def test_round_trip_keeps_fields_kilm_does_not_know(tmp_path: Path) -> None:
    """Changing a field and writing back keeps what other tools added."""
    (tmp_path / "kilm.yaml").write_text(
        "name: old\nmaintainer: Ada\n", encoding="utf-8"
    )
    metadata = read_github_metadata(tmp_path)
    assert metadata is not None

    metadata["name"] = "new"
    assert write_github_metadata(tmp_path, metadata)

    assert read_github_metadata(tmp_path) == {"name": "new", "maintainer": "Ada"}


def test_missing_empty_and_unreadable_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing reads as None, a non-mapping as empty, invalid JSON as None."""
    assert read_cloud_metadata(tmp_path) is None

    (tmp_path / ".kilm_metadata").write_text("[1, 2]", encoding="utf-8")
    assert read_cloud_metadata(tmp_path) == {}

    (tmp_path / ".kilm_metadata").write_text("{not json", encoding="utf-8")
    assert read_cloud_metadata(tmp_path) is None
    assert "Error reading cloud metadata file" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("name", "prefix", "expected"),
    [
        ("my-lib 2", "KICAD_LIB", "KICAD_LIB_MY_LIB_2"),
        ("3d models", "", "LIB_3D_MODELS"),
        ("", "", "LIB_"),
        ("x" * 60, "KICAD_3D", "KICAD_3D_" + "X" * 41),
    ],
)
def test_generate_env_var_name(name: str, prefix: str, expected: str) -> None:
    """Names are upper case, start with a letter, and stay within 50 chars."""
    assert generate_env_var_name(name, prefix) == expected
