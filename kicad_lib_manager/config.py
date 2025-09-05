"""
Configuration management
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, TypedDict, Union, cast

import click
import yaml

from .constants import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    DEFAULT_LIBRARIES,
    DEFAULT_MAX_BACKUPS,
)


class LibraryDict(TypedDict):
    """Type definition for library configuration."""

    name: str
    path: str
    type: str


ConfigValue = Union[str, int, List[LibraryDict]]

DEFAULT_CONFIG: Dict[str, ConfigValue] = {
    "max_backups": DEFAULT_MAX_BACKUPS,
    "libraries": DEFAULT_LIBRARIES,
}


class Config:
    """
    Configuration manager for KiCad Library Manager
    """

    def __init__(self):
        """Initialize configuration with default values"""
        self._config = DEFAULT_CONFIG.copy()
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from file if it exists"""
        config_file = self._get_config_file()
        if config_file.exists():
            try:
                with config_file.open() as f:
                    loaded_config = yaml.safe_load(f)
                if loaded_config and isinstance(loaded_config, dict):
                    self._config.update(loaded_config)
                    # Ensure libraries field is always a list of dicts
                    self._normalize_libraries_field()
            except Exception as e:
                # Use click.echo for warnings/errors
                click.echo(f"Error loading config file: {e}", err=True)

    def _get_config_file(self) -> Path:
        """Get the configuration file path"""
        config_dir = Path.home() / ".config" / CONFIG_DIR_NAME
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / CONFIG_FILE_NAME

    def get(
        self, key: str, default: Optional[ConfigValue] = None
    ) -> Optional[ConfigValue]:
        """Get a configuration value"""
        return self._config.get(key, default)

    def set(self, key: str, value: ConfigValue) -> None:
        """Set a configuration value"""
        self._config[key] = value

    def save(self) -> None:
        """Save configuration to file"""
        config_file = self._get_config_file()
        with config_file.open("w") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    def add_library(self, name: str, path: str, library_type: str = "github") -> None:
        """
        Add a library to the configuration

        Args:
            name: Library name
            path: Path to the library
            library_type: Type of library ("github" for symbols/footprints, "cloud" for 3D models)
        """
        libraries = self._get_normalized_libraries()

        # Check if library already exists
        for lib in libraries:
            if lib["name"] == name and lib["type"] == library_type:
                lib["path"] = str(path)
                self.save()
                return

        # Add new library
        new_library = LibraryDict(name=name, path=str(path), type=library_type)
        libraries.append(new_library)

        self._config["libraries"] = libraries
        self.save()

    def remove_library(self, name: str, library_type: Optional[str] = None) -> bool:
        """
        Remove a library from the configuration

        Args:
            name: Library name
            library_type: Type of library ("github" or "cloud"). If None, remove all types.

        Returns:
            True if library was removed, False otherwise
        """
        libraries = self._get_normalized_libraries()
        original_count = len(libraries)

        if library_type:
            filtered_libraries = [
                lib
                for lib in libraries
                if not (lib["name"] == name and lib["type"] == library_type)
            ]
        else:
            filtered_libraries = [lib for lib in libraries if lib["name"] != name]

        self._config["libraries"] = filtered_libraries
        removed = len(filtered_libraries) < original_count
        if removed:
            self.save()

        return removed

    def get_libraries(self, library_type: Optional[str] = None) -> List[LibraryDict]:
        """
        Get libraries from configuration

        Args:
            library_type: Type of library ("github" or "cloud"). If None, get all types.

        Returns:
            List of libraries
        """
        libraries = self._get_normalized_libraries()

        if library_type:
            return [lib for lib in libraries if lib["type"] == library_type]
        else:
            return libraries

    def get_library_path(
        self, name: str, library_type: str = "github"
    ) -> Optional[str]:
        """
        Get the path for a specific library

        Args:
            name: Library name
            library_type: Type of library ("github" or "cloud")

        Returns:
            Path to the library or None if not found
        """
        libraries = self._get_normalized_libraries()

        for lib in libraries:
            if lib["name"] == name and lib["type"] == library_type:
                return lib["path"]

        return None

    def get_current_library_paths(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get paths for the current active libraries

        Returns:
            Tuple of (github_library_path, cloud_library_path), either may be None
        """
        # Get all libraries by type
        github_libraries = self.get_libraries("github")
        cloud_libraries = self.get_libraries("cloud")

        # Get the current explicitly set library path
        current_lib_path = cast("Optional[str]", self._config.get("current_library"))

        # For GitHub libraries: first check if current library is a GitHub library,
        # otherwise use the first available GitHub library
        github_lib_path = None
        if current_lib_path:
            # Check if current library is a GitHub library
            for lib in github_libraries:
                if lib["path"] == current_lib_path:
                    github_lib_path = current_lib_path
                    break

        # If no GitHub library was found or it's not the current lib,
        # use the first available GitHub library
        if not github_lib_path and github_libraries:
            github_lib_path = github_libraries[0]["path"]

        # For cloud libraries: first check if current library is a cloud library,
        # otherwise use the first available cloud library
        cloud_lib_path = None
        if current_lib_path:
            # Check if current library is a cloud library
            for lib in cloud_libraries:
                if lib["path"] == current_lib_path:
                    cloud_lib_path = current_lib_path
                    break

        # If no cloud library was found or it's not the current lib,
        # use the first available cloud library
        if not cloud_lib_path and cloud_libraries:
            cloud_lib_path = cloud_libraries[0]["path"]

        return github_lib_path, cloud_lib_path

    def set_current_library(self, path: str) -> None:
        """
        Set the current active library path

        Args:
            path: Path to the library
        """
        self._config["current_library"] = str(path)
        self.save()

    def get_current_library(self) -> Optional[str]:
        """
        Get the current active library path

        Returns:
            Path to the current library or None if not set
        """
        value = self._config.get("current_library")
        return value if isinstance(value, str) else None

    def get_symbol_library_path(self) -> Optional[str]:
        """
        Get the path for the current symbol library

        Returns:
            Path to the symbol library or None if not found
        """
        github_path, _ = self.get_current_library_paths()
        return github_path

    def get_3d_library_path(self) -> Optional[str]:
        """
        Get the path for the current 3D models library

        Returns:
            Path to the 3D models library or None if not found
        """
        _, cloud_path = self.get_current_library_paths()
        return cloud_path

    def _normalize_libraries_field(self) -> None:
        """Ensure libraries field is always a properly typed list of dictionaries."""
        libraries = self._config.get("libraries", [])

        # If libraries is not a list, reset to empty list
        if not isinstance(libraries, list):
            click.echo(
                f"Warning: libraries field in config was {type(libraries).__name__}, resetting to empty list",
                err=True,
            )
            self._config["libraries"] = []
            return

        # Validate and clean up each library entry
        normalized_libraries: List[LibraryDict] = []
        for lib in libraries:
            validated_lib = _validate_library_entry(lib)
            if validated_lib is not None:
                normalized_libraries.append(validated_lib)
            else:
                click.echo(f"Warning: Skipping invalid library entry: {lib}", err=True)

        self._config["libraries"] = normalized_libraries

    def _get_normalized_libraries(self) -> List[LibraryDict]:
        """
        Get libraries ensuring they are properly normalized.

        Returns:
            List of properly typed library dictionaries
        """
        libraries_raw = self._config.get("libraries", [])

        # If libraries is not a list, reset to empty list
        if not isinstance(libraries_raw, list):
            click.echo(
                f"Warning: libraries field was {type(libraries_raw).__name__}, resetting to empty list",
                err=True,
            )
            self._config["libraries"] = []
            return []

        # Validate and normalize each library entry
        normalized_libraries: List[LibraryDict] = []
        needs_save = False

        for lib in libraries_raw:
            validated_lib = _validate_library_entry(lib)
            if validated_lib is not None:
                normalized_libraries.append(validated_lib)
            else:
                click.echo(f"Warning: Skipping invalid library entry: {lib}", err=True)
                needs_save = True

        # Update config if we had to clean up invalid entries
        if needs_save:
            self._config["libraries"] = normalized_libraries
            self.save()

        return normalized_libraries


def _make_library_dict(name: str, path: str, type_: str) -> LibraryDict:
    """Typed constructor for `LibraryDict` to satisfy type checker."""
    return LibraryDict(name=name, path=path, type=type_)


def _validate_library_entry(
    lib: Union[Dict[str, str], LibraryDict],
) -> Optional[LibraryDict]:
    """Validate and normalize a library entry."""
    if isinstance(lib, dict) and all(key in lib for key in ["name", "path", "type"]):
        return _make_library_dict(
            name=str(lib["name"]),
            path=str(lib["path"]),
            type_=str(lib["type"]),
        )
    return None
