"""
Library service protocol interface for KiCad Library Manager.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Protocol, Tuple, Union


class LibraryServiceProtocol(Protocol):
    """Protocol for library management services."""

    @abstractmethod
    def list_libraries(self, directory: Path) -> Tuple[List[str], List[str]]:
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
    ) -> Dict[str, Union[str, bool, Dict[str, bool]]]:
        """Initialize a library in the given directory."""
        ...

    @abstractmethod
    def get_library_metadata(
        self, directory: Path
    ) -> Optional[Dict[str, Union[str, bool, Dict[str, bool]]]]:
        """Get metadata for a library directory."""
        ...

    @abstractmethod
    def pin_libraries(
        self,
        symbol_libs: List[str],
        footprint_libs: List[str],
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
        symbol_libs: List[str],
        footprint_libs: List[str],
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
