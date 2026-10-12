"""KiCad configuration lookups used by the pin and status commands."""

from pathlib import Path

from kicad_lib_manager.services.library_service import LibraryService
from kicad_lib_manager.utils.file_ops import (
    LibraryTableEntry,
    list_configured_libraries,
)


class KiCadService:
    """Finds KiCad's configuration and the libraries its tables list."""

    @staticmethod
    def find_kicad_config_dir() -> Path:
        """Return the newest KiCad version's configuration directory.

        Goes through `LibraryService.find_kicad_config` so that one patch
        point covers every command.

        Raises:
            FileNotFoundError: KiCad's configuration cannot be found.
        """
        return LibraryService.find_kicad_config()

    @staticmethod
    def get_configured_libraries(
        config_dir: Path,
    ) -> tuple[list[LibraryTableEntry], list[LibraryTableEntry]]:
        """Return the entries of KiCad's symbol and footprint library tables."""
        return list_configured_libraries(config_dir)
