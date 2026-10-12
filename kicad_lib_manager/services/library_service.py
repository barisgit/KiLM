"""Create KiLM libraries and register their contents with KiCad."""

from pathlib import Path
from typing import Final

from kicad_lib_manager.services.kicad_config import find_kicad_config
from kicad_lib_manager.services.library_table import add_libraries
from kicad_lib_manager.utils.constants import GITHUB_METADATA_FILE
from kicad_lib_manager.utils.file_ops import list_libraries
from kicad_lib_manager.utils.metadata import (
    GitHubMetadata,
    generate_env_var_name,
    get_default_github_metadata,
    read_github_metadata,
    write_github_metadata,
)

LIBRARY_FOLDERS: Final = ("symbols", "footprints", "templates")
"""The top-level folders of a KiLM library, created by `initialize_library`."""


class LibraryService:
    """Library operations behind the init, list, pin, setup, status, and unpin commands.

    `add_libraries` and `find_kicad_config` are the module functions of
    library_table and kicad_config. They stay class attributes because
    commands call them through this class and tests patch them here.
    """

    add_libraries = staticmethod(add_libraries)
    find_kicad_config = staticmethod(find_kicad_config)

    @staticmethod
    def list_libraries(directory: Path) -> tuple[list[str], list[str]]:
        """Return the symbol and footprint library names in a KiLM library.

        Raises:
            FileNotFoundError: directory does not exist.
        """
        return list_libraries(str(directory))

    @staticmethod
    def initialize_library(  # noqa: PLR0913 -- one parameter per init command option
        directory: Path,
        *,
        name: str | None = None,
        description: str | None = None,
        env_var: str | None = None,
        force: bool = False,
        no_env_var: bool = False,
    ) -> GitHubMetadata:
        """Make directory a KiLM library and return its metadata.

        Existing metadata is kept unless force is set, with name,
        description, and env_var (when given) replacing its fields. New
        metadata derives the environment variable from name unless env_var
        or no_env_var is given. The library folders are created, and the
        capabilities and metadata file reflect them.

        Raises:
            OSError: A folder or the metadata file cannot be written.
        """
        overrides = (name, description, env_var)
        existing = read_github_metadata(directory)
        if force or existing is None or not existing:
            metadata = get_default_github_metadata(directory)
            if name is not None and env_var is None and not no_env_var:
                metadata["env_var"] = generate_env_var_name(name, "KICAD_LIB")
        else:
            metadata = existing
            if no_env_var or any(value is not None for value in overrides):
                metadata["updated_with"] = "kilm"

        if name is not None:
            metadata["name"] = name
        if description is not None:
            metadata["description"] = description
        if env_var is not None:
            metadata["env_var"] = env_var
        elif no_env_var:
            metadata.pop("env_var", None)

        for folder in LIBRARY_FOLDERS:
            (directory / folder).mkdir(parents=True, exist_ok=True)
        # Every folder exists now, so the library can hold each kind.
        metadata["capabilities"] = {
            "symbols": True,
            "footprints": True,
            "templates": True,
        }
        if not write_github_metadata(directory, metadata):
            msg = f"Could not write {GITHUB_METADATA_FILE} in {directory}"
            raise OSError(msg)
        return metadata
