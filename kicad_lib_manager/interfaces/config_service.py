"""
Configuration service protocol interface for KiCad Library Manager.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Optional, Protocol


class ConfigServiceProtocol(Protocol):
    """Protocol for configuration management services."""

    @abstractmethod
    def get_config_file_path(self) -> Path:
        """Get the path to the KiLM configuration file."""

    @abstractmethod
    def load_config(self) -> dict:
        """Load the KiLM configuration."""

    @abstractmethod
    def save_config(self, config: dict) -> None:
        """Save the KiLM configuration."""

    @abstractmethod
    def add_library(self, name: str, path: str, library_type: str) -> None:
        """Add a library to the configuration."""

    @abstractmethod
    def remove_library(self, name: str) -> None:
        """Remove a library from the configuration."""

    @abstractmethod
    def get_libraries(self) -> list[dict]:
        """Get all configured libraries."""

    @abstractmethod
    def get_library_by_name(self, name: str) -> Optional[dict]:
        """Get a specific library by name."""

    @abstractmethod
    def get_current_library(self) -> Optional[str]:
        """Get the current active library path."""

    @abstractmethod
    def set_current_library(self, path: str) -> None:
        """Set the current active library."""

    @abstractmethod
    def get_max_backups(self) -> int:
        """Get the maximum number of backups to keep."""

    @abstractmethod
    def set_max_backups(self, count: int) -> None:
        """Set the maximum number of backups to keep."""
