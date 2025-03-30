"""
Environment variable handling utilities
"""

import os
import re
import subprocess
import shutil
import json
from pathlib import Path
from typing import Optional, List

# Import Config here, but only use it when needed to avoid circular imports
try:
    from ..config import Config
except ImportError:
    Config = None

# Try to import metadata utilities without causing circular imports
try:
    from ..utils.metadata import (
        read_github_metadata,
        read_cloud_metadata,
        GITHUB_METADATA_FILE,
        CLOUD_METADATA_FILE
    )
except ImportError:
    read_github_metadata = None
    read_cloud_metadata = None
    GITHUB_METADATA_FILE = "kilm.yaml"
    CLOUD_METADATA_FILE = ".kilm_metadata"


def find_environment_variables(var_name: str) -> Optional[str]:
    """
    Find environment variables from various sources in the following order:
    1. Config file
    2. Metadata files in current directory
    3. Environment variables
    4. Shell config files
    
    Args:
        var_name: The name of the environment variable to find
        
    Returns:
        The value of the environment variable, or None if not found
    """
    # First check configuration file if it's a known variable
    if Config is not None:
        try:
            config = Config()
            
            # Check for KiCad library variables in config
            if var_name == "KICAD_USER_LIB":
                lib_path = config.get_symbol_library_path()
                if lib_path:
                    return lib_path
                    
            # Check for 3D model variables in config
            elif var_name == "KICAD_3D_LIB":
                lib_path = config.get_3d_library_path()
                if lib_path:
                    return lib_path
        except Exception:
            # If there's any error with config, fall back to other methods
            pass
    
    # Check for metadata file in current directory
    try:
        current_dir = Path.cwd().resolve()
        
        # For KiCad library directory, check for GitHub metadata
        if var_name == "KICAD_USER_LIB" and read_github_metadata:
            metadata_file = current_dir / GITHUB_METADATA_FILE
            if metadata_file.exists():
                # Found metadata file in current directory, probably a KiCad library
                return str(current_dir)
                
        # For 3D library directory, check for cloud metadata
        elif var_name == "KICAD_3D_LIB" and read_cloud_metadata:
            metadata_file = current_dir / CLOUD_METADATA_FILE
            if metadata_file.exists():
                # Found metadata file in current directory, probably a 3D model library
                return str(current_dir)
    except Exception:
        # If any error occurs, continue to other methods
        pass
    
    # Check environment directly
    if var_name in os.environ:
        return os.environ[var_name]
    
    # Check for fish universal variables
    if shutil.which("fish"):
        try:
            result = subprocess.run(
                ["fish", "-c", f"echo ${var_name}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    
    # Check common shell config files
    home = Path.home()
    config_files = [
        home / ".bashrc",
        home / ".bash_profile",
        home / ".profile",
        home / ".zshrc",
    ]
    
    pattern = re.compile(rf'^(?:export\s+)?{var_name}=[\'\"]?(.*?)[\'\"]?$')
    
    for config_file in config_files:
        if not config_file.exists():
            continue
            
        try:
            with open(config_file, "r") as f:
                for line in f:
                    match = pattern.search(line.strip())
                    if match:
                        return match.group(1)
        except Exception:
            pass
            
    return None


def expand_user_path(path: str) -> str:
    """
    Expand a path that might start with ~ to an absolute path
    
    Args:
        path: The path to expand
        
    Returns:
        The expanded path
    """
    if path.startswith("~"):
        return os.path.expanduser(path)
    return path


def update_kicad_env_vars(
    kicad_config: Path, env_vars: dict, dry_run: bool = False, max_backups: int = 5
) -> bool:
    """
    Update environment variables in KiCad's common configuration file
    
    Args:
        kicad_config: Path to the KiCad configuration directory
        env_vars: Dictionary of environment variables to set
        dry_run: If True, don't make any changes
        max_backups: Maximum number of backups to keep
        
    Returns:
        True if changes were made, False otherwise
        
    Raises:
        FileNotFoundError: If the KiCad common configuration file is not found
    """
    import json
    from .backup import create_backup
    
    # Validate input
    if not env_vars or not isinstance(env_vars, dict):
        return False
    
    kicad_common = kicad_config / "kicad_common.json"
    
    if not kicad_common.exists():
        raise FileNotFoundError(f"KiCad common configuration file not found at {kicad_common}")
    
    try:
        with open(kicad_common, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in {kicad_common}")
    
    # Check if environment section exists
    if "environment" not in config:
        config["environment"] = {"vars": {}}
    elif "vars" not in config["environment"]:
        config["environment"]["vars"] = {}
    
    # Check if changes are needed
    changes_needed = False
    current_vars = config["environment"]["vars"]
    
    # Filter out any None values from env_vars
    valid_env_vars = {key: value for key, value in env_vars.items() if value is not None}
    
    for key, value in valid_env_vars.items():
        # Ensure path uses forward slashes
        normalized_value = value.replace('\\', '/')
        
        if key not in current_vars or current_vars[key] != normalized_value:
            changes_needed = True
            if not dry_run:
                current_vars[key] = normalized_value
    
    # Write changes if needed
    if changes_needed and not dry_run:
        # Create backup before making changes
        create_backup(kicad_common, max_backups)
        
        with open(kicad_common, "w") as f:
            json.dump(config, f, indent=2)
    
    return changes_needed


def update_pinned_libraries(
    kicad_config: Path, 
    symbol_libs: List[str] = None, 
    footprint_libs: List[str] = None, 
    dry_run: bool = False,
    max_backups: int = 5
) -> bool:
    """
    Update pinned libraries in KiCad's common configuration file
    
    Args:
        kicad_config: Path to the KiCad configuration directory
        symbol_libs: List of symbol libraries to pin
        footprint_libs: List of footprint libraries to pin
        dry_run: If True, don't make any changes
        max_backups: Maximum number of backups to keep
        
    Returns:
        True if changes were made, False otherwise
        
    Raises:
        FileNotFoundError: If the KiCad common configuration file is not found
    """
    import json
    from .backup import create_backup
    
    # Default empty lists if None
    symbol_libs = symbol_libs or []
    footprint_libs = footprint_libs or []
    
    # Skip if both are empty
    if not symbol_libs and not footprint_libs:
        return False
    
    kicad_common = kicad_config / "kicad_common.json"
    
    if not kicad_common.exists():
        raise FileNotFoundError(f"KiCad common configuration file not found at {kicad_common}")
    
    try:
        with open(kicad_common, "r") as f:
            config = json.load(f)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON format in {kicad_common}")
    
    # Ensure session section exists
    if "session" not in config:
        config["session"] = {
            "pinned_symbol_libs": [],
            "pinned_fp_libs": [],
            "remember_open_files": False
        }
    
    # Ensure the pinned libraries sections exist
    if "pinned_symbol_libs" not in config["session"]:
        config["session"]["pinned_symbol_libs"] = []
    if "pinned_fp_libs" not in config["session"]:
        config["session"]["pinned_fp_libs"] = []
    
    # Convert lists to keep track of original state
    current_pinned_symbols = list(config["session"]["pinned_symbol_libs"])
    current_pinned_footprints = list(config["session"]["pinned_fp_libs"])
    
    # Check for changes to symbol libraries
    changes_needed = False
    
    # Add new symbol libraries that aren't already pinned
    for lib in symbol_libs:
        if lib not in current_pinned_symbols:
            changes_needed = True
            if not dry_run:
                config["session"]["pinned_symbol_libs"].append(lib)
    
    # Add new footprint libraries that aren't already pinned
    for lib in footprint_libs:
        if lib not in current_pinned_footprints:
            changes_needed = True
            if not dry_run:
                config["session"]["pinned_fp_libs"].append(lib)
    
    # Write changes if needed
    if changes_needed and not dry_run:
        # Create backup before making changes
        create_backup(kicad_common, max_backups)
        
        with open(kicad_common, "w") as f:
            json.dump(config, f, indent=2)
    
    return changes_needed 