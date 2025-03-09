"""
Environment variable handling utilities
"""

import os
import re
import subprocess
import shutil
from pathlib import Path
from typing import Optional


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