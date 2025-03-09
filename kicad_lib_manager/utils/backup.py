"""
Utilities for backup management
"""

import os
import shutil
from pathlib import Path
from datetime import datetime


def create_backup(file_path: Path, max_backups: int = 5) -> Path:
    """
    Create a timestamped backup of a file and maintain a limited history
    
    Args:
        file_path: Path to the file to back up
        max_backups: Maximum number of backups to keep
        
    Returns:
        Path to the created backup
        
    Raises:
        FileNotFoundError: If the file to back up doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Create timestamp for the backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = file_path.with_suffix(f"{file_path.suffix}.backup.{timestamp}")
    
    # Create the backup
    shutil.copy2(file_path, backup_path)
    
    # Clean up old backups
    manage_backup_history(file_path, max_backups)
    
    return backup_path


def manage_backup_history(file_path: Path, max_backups: int = 5) -> None:
    """
    Maintain a limited history of backups, removing the oldest ones
    
    Args:
        file_path: Path to the original file
        max_backups: Maximum number of backups to keep
    """
    # Find all backups for this file
    pattern = f"{file_path.name}.backup.*"
    backups = sorted(file_path.parent.glob(pattern))
    
    # Remove oldest backups if we have too many
    if len(backups) > max_backups:
        for old_backup in backups[:-max_backups]:
            os.remove(old_backup) 