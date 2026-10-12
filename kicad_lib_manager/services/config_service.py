"""The KiLM configuration file: registered libraries and update-check settings."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"yaml"}

import time
from pathlib import Path
from typing import Final, TypedDict, cast

import click
import yaml

from kicad_lib_manager.services.user_paths import user_cache_dir, user_config_file
from kicad_lib_manager.utils.constants import DEFAULT_MAX_BACKUPS


class LibraryDict(TypedDict):
    """A library registered in the configuration.

    `type` is "github" for symbol and footprint libraries and "cloud" for 3D
    model libraries.
    """

    name: str
    path: str
    type: str


ConfigValue = str | int | list[LibraryDict]
"""A configuration value; booleans are stored as the int subtype bool."""

UPDATE_CHECK_INTERVALS: Final[dict[str, float]] = {
    "daily": 24 * 60 * 60,
    "weekly": 7 * 24 * 60 * 60,
}
"""Seconds between update checks for each `update_check_frequency`.

"never" disables checks; any other value never triggers one.
"""

LAST_UPDATE_CHECK_FILE: Final = "last_update_check"
"""Cache file holding the time of the last update check."""


def default_config() -> dict[str, ConfigValue]:
    """Return a fresh configuration with every setting at its default."""
    return {
        "max_backups": DEFAULT_MAX_BACKUPS,
        "libraries": [],
        "update_check": True,
        "update_check_frequency": "daily",
        "auto_update": False,
    }


class Config:
    """The user's KiLM configuration, loaded at construction.

    Mutating methods save the file immediately. A missing file means the
    defaults; an unreadable one is reported on stderr and also yields the
    defaults. Library entries without a name, path, and type are dropped
    with a warning when the file is loaded.
    """

    def __init__(
        self, *, config_file: Path | None = None, cache_dir: Path | None = None
    ) -> None:
        """Load the configuration.

        Args:
            config_file: The YAML file; defaults to the user's KiLM config.
            cache_dir: Where update-check times are kept; defaults to the
                user's KiLM cache.
        """
        self.config_file = config_file or user_config_file()
        self._cache_dir = cache_dir or user_cache_dir()
        self._config = default_config()
        self._load_config()

    def _load_config(self) -> None:
        """Merge the file's settings over the defaults, if the file exists."""
        try:
            with self.config_file.open(encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
        except FileNotFoundError:
            return
        except (OSError, yaml.YAMLError) as e:
            click.echo(f"Error loading config file: {e}", err=True)
            return
        if isinstance(loaded, dict):
            self._config.update(loaded)
            self._config["libraries"] = _normalize_libraries(
                self._config.get("libraries")
            )

    def _get_config_file(self) -> Path:
        """Return `config_file`; kept for callers that predate the attribute."""
        return self.config_file

    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue | None:
        """Return the setting `key`, or `default` when it is not set."""
        return self._config.get(key, default)

    def save(self) -> None:
        """Write the configuration file, creating its directory if needed."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with self.config_file.open("w", encoding="utf-8") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def _libraries(self) -> list[LibraryDict]:
        """Return the stored library list itself; callers may mutate it."""
        libraries = self._config.get("libraries")
        if isinstance(libraries, list):
            return libraries
        libraries = []
        self._config["libraries"] = libraries
        return libraries

    def add_library(self, name: str, path: str, library_type: str = "github") -> None:
        """Register a library, or update the path of the one with this name and type.

        Args:
            name: Library name.
            path: Path to the library.
            library_type: "github" for symbols and footprints, "cloud" for
                3D models.
        """
        libraries = self._libraries()
        for library in libraries:
            if library["name"] == name and library["type"] == library_type:
                library["path"] = str(path)
                break
        else:
            libraries.append(LibraryDict(name=name, path=str(path), type=library_type))
        self.save()

    def remove_library(self, name: str, library_type: str | None = None) -> bool:
        """Unregister the libraries called `name`, of one type or of every type.

        The default library is cleared once no remaining library has its path.

        Returns:
            Whether any library was removed.
        """
        libraries = self._libraries()
        remaining = [
            library
            for library in libraries
            if library["name"] != name
            or (library_type is not None and library["type"] != library_type)
        ]
        if len(remaining) == len(libraries):
            return False
        self._config["libraries"] = remaining
        if self.get_current_library() not in {library["path"] for library in remaining}:
            self._config.pop("current_library", None)
        self.save()
        return True

    def get_libraries(self, library_type: str | None = None) -> list[LibraryDict]:
        """Return the registered libraries, optionally only those of one type."""
        return [
            library
            for library in self._libraries()
            if library_type is None or library["type"] == library_type
        ]

    def set_current_library(self, path: str) -> None:
        """Make the library at `path` the default and save."""
        self._config["current_library"] = str(path)
        self.save()

    def get_current_library(self) -> str | None:
        """Return the path of the default library, if one is set."""
        value = self._config.get("current_library")
        return value if isinstance(value, str) else None

    def get_symbol_library_path(self) -> str | None:
        """Return the symbol library to use: the default or else the first one."""
        return self._current_or_first("github")

    def get_3d_library_path(self) -> str | None:
        """Return the 3D model library to use: the default or else the first one."""
        return self._current_or_first("cloud")

    def _current_or_first(self, library_type: str) -> str | None:
        """Return the default library if it has this type, else the first such."""
        paths = [library["path"] for library in self.get_libraries(library_type)]
        current = self.get_current_library()
        if current in paths:
            return current
        return paths[0] if paths else None

    def should_check_updates(self) -> bool:
        """Return whether the update check frequency calls for a check now.

        Without a readable record of the last check, a check is due unless
        checks are disabled or the frequency is "never".
        """
        if not bool(self._config.get("update_check", True)):
            return False
        frequency = self._config.get("update_check_frequency", "daily")
        if frequency == "never":
            return False
        try:
            last_check = float(self._last_check_file().read_text().strip())
        except (ValueError, OSError):
            return True
        interval = (
            UPDATE_CHECK_INTERVALS.get(frequency)
            if isinstance(frequency, str)
            else None
        )
        return interval is not None and time.time() - last_check > interval

    def mark_update_check_performed(self) -> None:
        """Record that an update check ran now."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_check_file().write_text(str(time.time()))

    def _last_check_file(self) -> Path:
        return self._cache_dir / LAST_UPDATE_CHECK_FILE


def _normalize_libraries(value: object) -> list[LibraryDict]:
    """Return the valid library entries of a loaded `libraries` setting.

    Anything other than a list becomes an empty list, and entries without a
    name, path, and type are dropped; both are reported on stderr.
    """
    if not isinstance(value, list):
        click.echo(
            f"Warning: libraries field in config was {type(value).__name__},"
            " resetting to empty list",
            err=True,
        )
        return []
    libraries: list[LibraryDict] = []
    for entry in cast("list[object]", value):
        library = _library_entry(entry)
        if library is None:
            click.echo(f"Warning: Skipping invalid library entry: {entry}", err=True)
        else:
            libraries.append(library)
    return libraries


def _library_entry(entry: object) -> LibraryDict | None:
    """Return a loaded library entry as a `LibraryDict`; None if it lacks a field."""
    if not isinstance(entry, dict):
        return None
    fields = cast("dict[object, object]", entry)
    if not all(key in fields for key in ("name", "path", "type")):
        return None
    return LibraryDict(
        name=str(fields["name"]), path=str(fields["path"]), type=str(fields["type"])
    )


class ConfigService:
    """Holder of a `Config`, kept only because main.py still constructs it.

    New code uses `Config` directly; remove this once main.py does.
    """

    def __init__(self) -> None:
        """Load the user's configuration into `_config`."""
        self._config = Config()
