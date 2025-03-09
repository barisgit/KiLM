"""
Configuration management
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_CONFIG = {
    "max_backups": 5,
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
            # For now, we just use environment variables
            # In the future, we could add support for a config file
            pass
    
    def _get_config_file(self) -> Path:
        """Get the configuration file path"""
        config_dir = Path.home() / ".config" / "kicad-lib-manager"
        os.makedirs(config_dir, exist_ok=True)
        return config_dir / "config.yaml"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        self._config[key] = value
    
    def save(self) -> None:
        """Save configuration to file"""
        # For now, we don't save anything
        # In the future, we could add support for saving to a config file
        pass 