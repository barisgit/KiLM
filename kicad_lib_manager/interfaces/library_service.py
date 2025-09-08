"""
Library service protocol interface for KiCad Library Manager.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Optional, Protocol, Union


class LibraryServiceProtocol(Protocol):
    """Protocol for library management services."""

    @abstractmethod
    def list_libraries(self, directory: Path) -> tuple[list[str], list[str]]:
        """
        List symbol and footprint libraries in a directory.

        Returns:
            Tuple of (symbol_libraries, footprint_libraries)
        """
        ...

    @abstractmethod
    def initialize_library(
        self,
        directory: Path,
        name: Optional[str] = None,
        description: Optional[str] = None,
        env_var: Optional[str] = None,
        force: bool = False,
        no_env_var: bool = False,
    ) -> dict[str, Union[str, bool, dict[str, bool]]]:
        """Initialize a library in the given directory."""
        ...

    @abstractmethod
    def get_library_metadata(
        self, directory: Path
    ) -> Optional[dict[str, Union[str, bool, dict[str, bool]]]]:
        """Get metadata for a library directory."""
        ...

    @abstractmethod
    def pin_libraries(
        self,
        symbol_libs: list[str],
        footprint_libs: list[str],
        kicad_config_dir: Path,
        dry_run: bool = False,
        max_backups: int = 5,
    ) -> bool:
        """
        Pin libraries in KiCad for quick access.

        Returns:
            True if changes were made, False otherwise
        """
        ...

    @abstractmethod
    def unpin_libraries(
        self,
        symbol_libs: list[str],
        footprint_libs: list[str],
        kicad_config_dir: Path,
        dry_run: bool = False,
        max_backups: int = 5,
    ) -> bool:
        """
        Unpin libraries in KiCad.

        Returns:
            True if changes were made, False otherwise
        """
        ...
