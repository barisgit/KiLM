"""
Configuration management
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

DEFAULT_CONFIG = {
    "max_backups": 5,
    "libraries": [],
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
                with open(config_file, "r") as f:
                    loaded_config = yaml.safe_load(f)
                if loaded_config and isinstance(loaded_config, dict):
                    self._config.update(loaded_config)
            except Exception as e:
                print(f"Error loading config file: {e}")
    
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
        config_file = self._get_config_file()
        with open(config_file, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False)
    
    def add_library(self, name: str, path: str, library_type: str = "github") -> None:
        """
        Add a library to the configuration
        
        Args:
            name: Library name
            path: Path to the library
            library_type: Type of library ("github" for symbols/footprints, "cloud" for 3D models)
        """
        libraries = self._config.get("libraries", [])
        
        # Check if library already exists
        for lib in libraries:
            if lib.get("name") == name and lib.get("type") == library_type:
                lib["path"] = str(path)
                self.save()
                return
        
        # Add new library
        libraries.append({
            "name": name,
            "path": str(path),
            "type": library_type
        })
        
        self._config["libraries"] = libraries
        self.save()
    
    def remove_library(self, name: str, library_type: str = None) -> bool:
        """
        Remove a library from the configuration
        
        Args:
            name: Library name
            library_type: Type of library ("github" or "cloud"). If None, remove all types.
            
        Returns:
            True if library was removed, False otherwise
        """
        libraries = self._config.get("libraries", [])
        original_count = len(libraries)
        
        if library_type:
            self._config["libraries"] = [
                lib for lib in libraries 
                if not (lib.get("name") == name and lib.get("type") == library_type)
            ]
        else:
            self._config["libraries"] = [
                lib for lib in libraries 
                if lib.get("name") != name
            ]
        
        removed = len(self._config["libraries"]) < original_count
        if removed:
            self.save()
        
        return removed
    
    def get_libraries(self, library_type: str = None) -> List[Dict[str, str]]:
        """
        Get libraries from configuration
        
        Args:
            library_type: Type of library ("github" or "cloud"). If None, get all types.
            
        Returns:
            List of libraries
        """
        libraries = self._config.get("libraries", [])
        
        if library_type:
            return [lib for lib in libraries if lib.get("type") == library_type]
        else:
            return libraries
    
    def get_library_path(self, name: str, library_type: str = "github") -> Optional[str]:
        """
        Get the path for a specific library
        
        Args:
            name: Library name
            library_type: Type of library ("github" or "cloud")
            
        Returns:
            Path to the library or None if not found
        """
        libraries = self._config.get("libraries", [])
        
        for lib in libraries:
            if lib.get("name") == name and lib.get("type") == library_type:
                return lib.get("path")
        
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
        current_lib_path = self._config.get("current_library")
        
        # For GitHub libraries: first check if current library is a GitHub library,
        # otherwise use the first available GitHub library
        github_lib_path = None
        if current_lib_path:
            # Check if current library is a GitHub library
            for lib in github_libraries:
                if lib.get("path") == current_lib_path:
                    github_lib_path = current_lib_path
                    break
        
        # If no GitHub library was found or it's not the current lib,
        # use the first available GitHub library
        if not github_lib_path and github_libraries:
            github_lib_path = github_libraries[0].get("path")
        
        # For cloud libraries: first check if current library is a cloud library,
        # otherwise use the first available cloud library
        cloud_lib_path = None
        if current_lib_path:
            # Check if current library is a cloud library
            for lib in cloud_libraries:
                if lib.get("path") == current_lib_path:
                    cloud_lib_path = current_lib_path
                    break
        
        # If no cloud library was found or it's not the current lib,
        # use the first available cloud library
        if not cloud_lib_path and cloud_libraries:
            cloud_lib_path = cloud_libraries[0].get("path")
        
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
        return self._config.get("current_library")
    
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