"""
Environment variable handling utilities
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List


def find_environment_variables(var_name: str) -> Optional[str]:
    """
    Find environment variables from various shell configurations
    
    Args:
        var_name: The name of the environment variable to find
        
    Returns:
        The value of the environment variable, or None if not found
    """
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
        if config_file.exists():
            with open(config_file, "r") as f:
                for line in f:
                    match = pattern.match(line.strip())
                    if match:
                        return match.group(1)
    
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
    kicad_config: Path, env_vars: dict, dry_run: bool = False
) -> bool:
    """
    Update environment variables in KiCad's common configuration file
    
    Args:
        kicad_config: Path to the KiCad configuration directory
        env_vars: Dictionary of environment variables to update
        dry_run: If True, don't make any changes
        
    Returns:
        True if changes were made, False otherwise
        
    Raises:
        FileNotFoundError: If the KiCad common configuration file is not found
    """
    import json
    
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
    
    for key, value in env_vars.items():
        if key not in current_vars or current_vars[key] != value:
            changes_needed = True
            if not dry_run:
                current_vars[key] = value
    
    # Write changes if needed
    if changes_needed and not dry_run:
        with open(kicad_common, "w") as f:
            json.dump(config, f, indent=2)
    
    return changes_needed


def update_pinned_libraries(
    kicad_config: Path, 
    symbol_libs: List[str] = None, 
    footprint_libs: List[str] = None, 
    dry_run: bool = False
) -> bool:
    """
    Update pinned libraries in KiCad's common configuration file
    
    Args:
        kicad_config: Path to the KiCad configuration directory
        symbol_libs: List of symbol libraries to pin
        footprint_libs: List of footprint libraries to pin
        dry_run: If True, don't make any changes
        
    Returns:
        True if changes were made, False otherwise
        
    Raises:
        FileNotFoundError: If the KiCad common configuration file is not found
    """
    import json
    
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
        with open(kicad_common, "w") as f:
            json.dump(config, f, indent=2)
    
    return changes_needed 