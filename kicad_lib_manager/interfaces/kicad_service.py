"""
KiCad service protocol interface for KiCad Library Manager.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Optional, Protocol


class KiCadServiceProtocol(Protocol):
    """Protocol for KiCad configuration and management services."""

    @abstractmethod
    def find_kicad_config_dir(self) -> Path:
        """Find the KiCad configuration directory."""

    @abstractmethod
    def get_environment_variables(self, config_dir: Path) -> dict[str, str]:
        """Get KiCad environment variables from configuration."""

    @abstractmethod
    def set_environment_variables(
        self,
        config_dir: Path,
        env_vars: dict[str, str],
        backup: bool = True,
        max_backups: int = 5,
    ) -> bool:
        """Set KiCad environment variables."""

    @abstractmethod
    def get_configured_libraries(
        self, config_dir: Path
    ) -> tuple[list[dict], list[dict]]:
        """
        Get configured symbol and footprint libraries.

        Returns:
            Tuple of (symbol_libraries, footprint_libraries)
        """

    @abstractmethod
    def add_libraries_to_kicad(
        self,
        config_dir: Path,
        symbol_libs: Optional[list[dict]] = None,
        footprint_libs: Optional[list[dict]] = None,
        backup: bool = True,
        max_backups: int = 5,
    ) -> bool:
        """Add libraries to KiCad library tables."""

    @abstractmethod
    def get_pinned_libraries(self, config_dir: Path) -> tuple[list[str], list[str]]:
        """
        Get pinned libraries from KiCad configuration.

        Returns:
            Tuple of (symbol_libraries, footprint_libraries)
        """
