"""Tests for locating KiCad's configuration directory."""

from pathlib import Path

import pytest

from kicad_lib_manager.services.kicad_config import find_kicad_config


def make_versions(root: Path, *versions: str) -> None:
    """Create version directories under root, each with a symbol table."""
    for version in versions:
        (root / version).mkdir(parents=True)
        (root / version / "sym-lib-table").touch()


@pytest.mark.parametrize(
    ("system", "relative"),
    [("Darwin", "Library/Preferences/kicad"), ("Linux", ".config/kicad")],
)
def test_finds_latest_numeric_version(
    tmp_path: Path, system: str, relative: str
) -> None:
    """Versions order numerically, so 10.0 is newer than 9.0."""
    root = tmp_path / relative
    make_versions(root, "8.0", "9.0", "10.0")
    (root / "colors").mkdir()

    assert find_kicad_config(system=system, home=tmp_path) == root / "10.0"


def test_windows_uses_appdata(tmp_path: Path) -> None:
    """On Windows the configuration lives under APPDATA."""
    make_versions(tmp_path / "kicad", "9.0")

    found = find_kicad_config(
        system="Windows", home=tmp_path, environ={"APPDATA": str(tmp_path)}
    )

    assert found == tmp_path / "kicad" / "9.0"


@pytest.mark.parametrize(
    ("system", "environ", "message"),
    [
        ("Windows", {}, "APPDATA"),
        ("Plan9", {}, "Unsupported platform"),
        ("Linux", {}, "configuration directory not found"),
    ],
)
def test_reports_missing_configuration(
    tmp_path: Path, system: str, environ: dict[str, str], message: str
) -> None:
    """Unsupported platforms and missing directories raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError, match=message):
        find_kicad_config(system=system, home=tmp_path, environ=environ)


def test_requires_version_directory_with_tables(tmp_path: Path) -> None:
    """KiCad must have created a version directory with a library table."""
    root = tmp_path / ".config" / "kicad"
    root.mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="No KiCad version directories"):
        find_kicad_config(system="Linux", home=tmp_path)

    (root / "9.0").mkdir()
    with pytest.raises(FileNotFoundError, match="library tables not found"):
        find_kicad_config(system="Linux", home=tmp_path)
