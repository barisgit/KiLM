"""Tests for the `kilm config` commands."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner, Result

from kicad_lib_manager.commands.config import command, config_app
from kicad_lib_manager.services.config_service import Config, LibraryDict
from kicad_lib_manager.utils.constants import CLOUD_METADATA_FILE, GITHUB_METADATA_FILE


@pytest.fixture
def libraries(tmp_path: Path) -> list[LibraryDict]:
    """A GitHub and a cloud library whose directories exist."""
    github = tmp_path / "github-lib"
    cloud = tmp_path / "cloud-lib"
    github.mkdir()
    cloud.mkdir()
    return [
        LibraryDict(name="test-github-lib", path=str(github), type="github"),
        LibraryDict(name="test-cloud-lib", path=str(cloud), type="cloud"),
    ]


@pytest.fixture
def config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, libraries: list[LibraryDict]
) -> Path:
    """A configuration with both libraries, the GitHub one as default.

    The commands load it instead of the user's configuration.
    """
    path = tmp_path / "config.yaml"
    settings = {"libraries": libraries, "current_library": libraries[0]["path"]}
    path.write_text(yaml.dump(settings), encoding="utf-8")
    monkeypatch.setattr(
        command, "Config", lambda: Config(config_file=path, cache_dir=tmp_path)
    )
    return path


def stored(config_file: Path) -> Config:
    """The configuration as currently saved."""
    return Config(config_file=config_file, cache_dir=config_file.parent)


def invoke(*args: str, user_input: str | None = None) -> Result:
    """Run `kilm config` with args."""
    return CliRunner().invoke(config_app, list(args), input=user_input)


@pytest.mark.usefixtures("config_file")
def test_list_shows_both_types_and_the_default() -> None:
    """The table lists each type and marks the default library."""
    result = invoke("list")

    assert result.exit_code == 0
    assert "GitHub Libraries" in result.output
    assert "Cloud Libraries" in result.output
    assert "test-github-lib" in result.output
    assert "test-cloud-lib" in result.output
    assert "Current" in result.output
    assert "GitHub: 1  Cloud: 1" in result.output


@pytest.mark.usefixtures("config_file")
def test_list_verbose_shows_metadata(libraries: list[LibraryDict]) -> None:
    """Verbose panels show stored metadata, or count models without it."""
    github = Path(libraries[0]["path"])
    (github / GITHUB_METADATA_FILE).write_text(
        yaml.dump(
            {
                "description": "Company parts",
                "version": "1.2.0",
                "capabilities": {"symbols": True, "footprints": False},
            }
        ),
        encoding="utf-8",
    )
    cloud = Path(libraries[1]["path"])
    (cloud / "sub").mkdir()
    (cloud / "sub" / "part.step").touch()
    (cloud / "part.wrl").touch()
    (cloud / "notes.txt").touch()

    result = invoke("list", "--verbose")

    assert result.exit_code == 0
    assert "CURRENT" in result.output
    assert "Description: Company parts" in result.output
    assert "Version: 1.2.0" in result.output
    assert "Features: Symbols" in result.output
    assert f"No {CLOUD_METADATA_FILE} metadata file found" in result.output
    assert "3D Models: 2 (counted)" in result.output


@pytest.mark.usefixtures("config_file")
def test_list_filtered_by_type() -> None:
    """--type shows only libraries of that type."""
    result = invoke("list", "--type", "github")

    assert result.exit_code == 0
    assert "test-github-lib" in result.output
    assert "Cloud Libraries" not in result.output
    assert "test-cloud-lib" not in result.output


@pytest.mark.parametrize(
    ("library_type", "removed", "message", "hint"),
    [
        ("github", "test-github-lib", "No GitHub libraries configured", "kilm init"),
        ("cloud", "test-cloud-lib", "No cloud libraries configured", "kilm add-3d"),
    ],
)
def test_list_type_without_libraries(
    config_file: Path, library_type: str, removed: str, message: str, hint: str
) -> None:
    """A type filter without matches names that type and how to add one."""
    stored(config_file).remove_library(removed)

    result = invoke("list", "--type", library_type)

    assert result.exit_code == 0
    assert message in result.output
    assert hint in result.output


def test_list_without_libraries(config_file: Path) -> None:
    """Without any library the list explains how to add one."""
    config = stored(config_file)
    config.remove_library("test-github-lib")
    config.remove_library("test-cloud-lib")

    result = invoke("list")

    assert result.exit_code == 0
    assert "No libraries configured" in result.output


def test_set_default_by_name(config_file: Path, libraries: list[LibraryDict]) -> None:
    """A named library of the given type becomes the saved default."""
    result = invoke("set-default", "test-cloud-lib", "--type", "cloud")

    assert result.exit_code == 0
    assert "Set cloud library 'test-cloud-lib' as default" in result.output
    assert stored(config_file).get_current_library() == libraries[1]["path"]


@pytest.mark.parametrize(("arguments", "index"), [((), 0), (("--type", "cloud"), 1)])
def test_set_default_prompts_without_name(
    config_file: Path,
    libraries: list[LibraryDict],
    arguments: tuple[str, ...],
    index: int,
) -> None:
    """Without a name the libraries of the type are numbered and one is picked."""
    library = libraries[index]

    result = invoke("set-default", *arguments, user_input="5\n1\n")

    assert result.exit_code == 0
    assert f"Available {library['type']} libraries:" in result.output
    assert f"1. {library['name']}" in result.output
    assert "5 is not in the range 1<=x<=1" in result.output
    assert stored(config_file).get_current_library() == library["path"]


@pytest.mark.usefixtures("config_file")
def test_set_default_unknown_name() -> None:
    """An unknown name fails and points to config list."""
    result = invoke("set-default", "non-existent-lib")

    assert result.exit_code == 1
    assert "No github library named 'non-existent-lib' found" in result.output
    assert "kilm config list" in result.output


def test_set_default_without_libraries_of_type(config_file: Path) -> None:
    """Without libraries of the type the command fails and says how to add one."""
    stored(config_file).remove_library("test-cloud-lib")

    result = invoke("set-default", "--type", "cloud")

    assert result.exit_code == 1
    assert "No cloud libraries configured." in result.output
    assert "kilm add-3d" in result.output


def test_remove_with_force(config_file: Path, libraries: list[LibraryDict]) -> None:
    """--force removes without asking and saves the configuration."""
    result = invoke("remove", "test-cloud-lib", "--force")

    assert result.exit_code == 0
    assert "Removed library 'test-cloud-lib'" in result.output
    assert "Note:" not in result.output
    assert stored(config_file).get_libraries() == [libraries[0]]


def test_remove_default_library_reports_cleared_default(config_file: Path) -> None:
    """Removing the default library says that no default is set any more."""
    result = invoke("remove", "test-github-lib", "--force")

    assert result.exit_code == 0
    assert "no default is set now" in result.output
    assert stored(config_file).get_current_library() is None


def test_remove_asks_for_confirmation(config_file: Path) -> None:
    """Without --force the libraries are described and removal needs a yes."""
    result = invoke("remove", "test-github-lib", user_input="y\n")

    assert result.exit_code == 0
    assert "Will remove github library 'test-github-lib'" in result.output
    assert "This is the current default library" in result.output
    assert "Removed library 'test-github-lib'" in result.output
    assert len(stored(config_file).get_libraries()) == 1


def test_remove_cancelled_keeps_library(config_file: Path) -> None:
    """Declining the confirmation keeps the configuration unchanged."""
    result = invoke("remove", "test-github-lib", user_input="n\n")

    assert result.exit_code == 0
    assert "Operation cancelled." in result.output
    assert len(stored(config_file).get_libraries()) == 2


def test_remove_only_the_given_type(config_file: Path) -> None:
    """--type removes one entry of a name registered for both types."""
    config = stored(config_file)
    config.add_library("test-github-lib", "/elsewhere", "cloud")

    result = invoke("remove", "test-github-lib", "--type", "cloud", "--force")

    assert result.exit_code == 0
    assert [library["type"] for library in stored(config_file).get_libraries()] == [
        "github",
        "cloud",
    ]


def test_remove_every_type_reports_count(config_file: Path) -> None:
    """Without --type every entry with the name goes, and the count is given."""
    stored(config_file).add_library("test-github-lib", "/elsewhere", "cloud")

    result = invoke("remove", "test-github-lib", "--force")

    assert result.exit_code == 0
    assert "Removed 2 instances of library 'test-github-lib'" in result.output


@pytest.mark.usefixtures("config_file")
def test_remove_unknown_name() -> None:
    """An unknown name fails and points to config list."""
    result = invoke("remove", "non-existent-lib", "--force")

    assert result.exit_code == 1
    assert "No library named 'non-existent-lib' found" in result.output
