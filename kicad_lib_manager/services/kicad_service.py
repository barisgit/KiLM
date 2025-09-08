"""
KiCad service implementation for KiCad Library Manager.
"""

import json
from pathlib import Path
from typing import Optional

from ..utils.file_ops import list_configured_libraries
from .library_service import LibraryService


class KiCadService:
    """Service for managing KiCad configuration and libraries."""

    @staticmethod
    def find_kicad_config_dir() -> Path:
        return LibraryService.find_kicad_config()

    def get_environment_variables(self, config_dir: Path) -> dict[str, str]:
        """Get KiCad environment variables from configuration."""
        kicad_common = config_dir / "kicad_common.json"

        if not kicad_common.exists():
            return {}

        try:
            with kicad_common.open() as f:
                config = json.load(f)

            if "environment" in config and "vars" in config["environment"]:
                return config["environment"]["vars"]

        except Exception:
            pass

        return {}

    def set_environment_variables(
        self,
        config_dir: Path,
        env_vars: dict[str, str],
        backup: bool = True,
        max_backups: int = 5,
    ) -> bool:
        """Set KiCad environment variables."""
        # This would use the existing update_kicad_env_vars function
        from ..utils.env_vars import update_kicad_env_vars

        return update_kicad_env_vars(config_dir, env_vars, backup, max_backups)

    def get_configured_libraries(
        self, config_dir: Path
    ) -> tuple[list[dict], list[dict]]:
        """Get configured symbol and footprint libraries."""
        return list_configured_libraries(config_dir)

    def add_libraries_to_kicad(
        self,
        config_dir: Path,
        symbol_libs: Optional[list[dict]] = None,
        footprint_libs: Optional[list[dict]] = None,
        backup: bool = True,
        max_backups: int = 5,
    ) -> bool:
        """Add libraries to KiCad library tables."""
        # This would use the existing add_libraries function
        from .library_service import LibraryService

        # TODO: Properly implement library addition with symbol_libs and footprint_libs
        _ = symbol_libs, footprint_libs, max_backups  # Suppress unused warnings
        added_libs, changes_needed = LibraryService.add_libraries(
            str(config_dir),
            config_dir,
            dry_run=not backup,
        )
        _ = added_libs  # Suppress unused warning
        return changes_needed

    def get_pinned_libraries(self, config_dir: Path) -> tuple[list[str], list[str]]:
        """Get pinned libraries from KiCad configuration."""
        kicad_common = config_dir / "kicad_common.json"

        if not kicad_common.exists():
            return [], []

        try:
            with kicad_common.open() as f:
                config = json.load(f)

            symbol_libs = []
            footprint_libs = []

            if "session" in config:
                if "pinned_symbol_libs" in config["session"]:
                    symbol_libs = config["session"]["pinned_symbol_libs"]
                if "pinned_fp_libs" in config["session"]:
                    footprint_libs = config["session"]["pinned_fp_libs"]

            return symbol_libs, footprint_libs

        except Exception:
            return [], []
