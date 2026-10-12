"""Tests for the KiLM configuration file model."""

import time
from pathlib import Path
from typing import cast

import pytest
import yaml

from kicad_lib_manager.services.config_service import (
    LAST_UPDATE_CHECK_FILE,
    Config,
    LibraryDict,
)

GITHUB = LibraryDict(name="symbols", path="/libs/symbols", type="github")
CLOUD = LibraryDict(name="models", path="/libs/models", type="cloud")


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Location of a configuration file that does not exist yet."""
    return tmp_path / "config" / "config.yaml"


def make_config(config_file: Path, settings: object | None = None) -> Config:
    """Write settings (if any) to config_file and load it."""
    if settings is not None:
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(yaml.dump(settings), encoding="utf-8")
    return Config(config_file=config_file, cache_dir=config_file.parent / "cache")


def saved(config_file: Path) -> dict[str, object]:
    """The settings currently stored in config_file."""
    loaded: object = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return cast("dict[str, object]", loaded)


def test_missing_file_yields_defaults_without_creating_anything(
    config_file: Path,
) -> None:
    """A missing file means the defaults, and loading creates no directory."""
    config = make_config(config_file)

    assert config.get_libraries() == []
    assert config.get("update_check") is True
    assert config.get("max_backups") == 5
    assert not config_file.parent.exists()


def test_loading_merges_settings_and_drops_invalid_libraries(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """File settings override defaults; incomplete library entries are dropped."""
    config = make_config(
        config_file,
        {"max_backups": 2, "libraries": [dict(GITHUB), {"name": "no-path"}]},
    )

    assert config.get("max_backups") == 2
    assert config.get("update_check_frequency") == "daily"
    assert config.get_libraries() == [GITHUB]
    assert "Skipping invalid library entry" in capsys.readouterr().err


def test_non_list_libraries_setting_becomes_empty(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A libraries setting that is not a list is replaced by an empty one."""
    config = make_config(config_file, {"libraries": "oops"})

    assert config.get_libraries() == []
    assert "resetting to empty list" in capsys.readouterr().err


def test_unreadable_file_is_reported_and_yields_defaults(
    config_file: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Invalid YAML is reported on stderr and the defaults apply."""
    config_file.parent.mkdir(parents=True)
    config_file.write_text("libraries: [unclosed", encoding="utf-8")

    config = make_config(config_file)

    assert config.get_libraries() == []
    assert "Error loading config file" in capsys.readouterr().err


def test_add_library_saves_and_updates_existing_entry(config_file: Path) -> None:
    """Adding a known name and type updates its path; every change is saved."""
    config = make_config(config_file)

    config.add_library("symbols", "/old", "github")
    config.add_library("symbols", GITHUB["path"], "github")
    config.add_library(CLOUD["name"], CLOUD["path"], "cloud")

    assert config.get_libraries() == [GITHUB, CLOUD]
    assert config.get_libraries("cloud") == [CLOUD]
    assert make_config(config_file).get_libraries() == [GITHUB, CLOUD]


def test_remove_library_by_type_or_every_type(config_file: Path) -> None:
    """Removal is limited to one type when given and reports whether it removed."""
    twin = LibraryDict(name="symbols", path="/libs/twin", type="cloud")
    config = make_config(config_file, {"libraries": [GITHUB, twin, CLOUD]})

    assert config.remove_library("symbols", "cloud")
    assert config.get_libraries() == [GITHUB, CLOUD]
    assert config.remove_library("symbols")
    assert not config.remove_library("symbols")
    assert saved(config_file)["libraries"] == [CLOUD]


def test_removing_the_default_library_clears_the_default(config_file: Path) -> None:
    """No default remains once no registered library has its path."""
    config = make_config(
        config_file, {"libraries": [GITHUB, CLOUD], "current_library": GITHUB["path"]}
    )

    config.remove_library(CLOUD["name"])
    assert config.get_current_library() == GITHUB["path"]

    config.remove_library(GITHUB["name"])

    assert config.get_current_library() is None
    assert "current_library" not in saved(config_file)


def test_default_survives_while_another_entry_has_its_path(config_file: Path) -> None:
    """Removing one of two entries sharing the default path keeps the default."""
    twin = LibraryDict(name="twin", path=GITHUB["path"], type="cloud")
    config = make_config(
        config_file, {"libraries": [GITHUB, twin], "current_library": GITHUB["path"]}
    )

    config.remove_library(GITHUB["name"])

    assert config.get_current_library() == GITHUB["path"]


def test_library_paths_prefer_the_default_of_matching_type(config_file: Path) -> None:
    """The default library wins for its own type; others fall back to the first."""
    other = LibraryDict(name="other", path="/libs/other", type="github")
    config = make_config(config_file, {"libraries": [GITHUB, other, CLOUD]})

    assert config.get_symbol_library_path() == GITHUB["path"]
    assert config.get_3d_library_path() == CLOUD["path"]

    config.set_current_library(other["path"])

    assert config.get_current_library() == other["path"]
    assert config.get_symbol_library_path() == other["path"]
    assert config.get_3d_library_path() == CLOUD["path"]
    assert saved(config_file)["current_library"] == other["path"]


def test_library_paths_are_none_without_libraries(config_file: Path) -> None:
    """Without libraries there is no default and no path to use."""
    config = make_config(config_file)

    assert config.get_symbol_library_path() is None
    assert config.get_3d_library_path() is None
    assert config.get_current_library() is None


DAY = 24 * 60 * 60


def config_with_last_check(
    config_file: Path, settings: dict[str, object], seconds_ago: float | None
) -> Config:
    """Load settings, with the last update check seconds_ago (None: never)."""
    config = make_config(config_file, settings)
    if seconds_ago is not None:
        cache_dir = config_file.parent / "cache"
        cache_dir.mkdir()
        (cache_dir / LAST_UPDATE_CHECK_FILE).write_text(str(time.time() - seconds_ago))
    return config


@pytest.mark.parametrize(
    ("settings", "seconds_ago"),
    [
        ({}, None),
        ({}, 2 * DAY),
        ({"update_check_frequency": "weekly"}, 8 * DAY),
        ({"update_check_frequency": "monthly"}, None),
    ],
)
def test_update_check_is_due(
    config_file: Path, settings: dict[str, object], seconds_ago: float | None
) -> None:
    """A check is due without a record or once the interval has passed."""
    config = config_with_last_check(config_file, settings, seconds_ago)

    assert config.should_check_updates()


@pytest.mark.parametrize(
    ("settings", "seconds_ago"),
    [
        ({}, 60),
        ({"update_check_frequency": "weekly"}, 2 * DAY),
        ({"update_check_frequency": "never"}, None),
        ({"update_check": False}, None),
        ({"update_check_frequency": "monthly"}, 8 * DAY),
    ],
)
def test_update_check_is_not_due(
    config_file: Path, settings: dict[str, object], seconds_ago: float | None
) -> None:
    """Checks wait for the interval, and disabled checks never run."""
    config = config_with_last_check(config_file, settings, seconds_ago)

    assert not config.should_check_updates()


def test_marking_a_check_postpones_the_next(config_file: Path) -> None:
    """Recording a check makes the next one wait for the interval."""
    config = make_config(config_file)

    config.mark_update_check_performed()

    assert not config.should_check_updates()
