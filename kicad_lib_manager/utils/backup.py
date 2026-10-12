"""Timestamped backups of files that KiLM is about to change.

A backup of ``<name>`` is the sibling ``<name>.backup.<stamp>``, where the
stamp is the local time with microseconds. Stamps have a fixed width, so the
name order of a file's backups is their creation order; pruning relies on it.
Backups from releases that stamped whole seconds sort correctly among them.
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from kicad_lib_manager.utils.constants import DEFAULT_MAX_BACKUPS

_STAMP_FORMAT = "%Y%m%d_%H%M%S_%f"
_BACKUP_INFIX = ".backup."


def create_backup(file_path: Path, max_backups: int = DEFAULT_MAX_BACKUPS) -> Path:
    """Copy file_path to a new backup and keep only its newest max_backups backups.

    The backup keeps the file's metadata (shutil.copy2). It never replaces an
    earlier backup, even one taken at the same clock reading.

    Args:
        file_path: File to back up.
        max_backups: Number of backups of the file to keep, this one included.

    Returns:
        Path of the new backup.

    Raises:
        FileNotFoundError: file_path does not exist.
    """
    if not file_path.exists():
        msg = f"File not found: {file_path}"
        raise FileNotFoundError(msg)

    backup_path = unique_backup_path(file_path)
    shutil.copy2(file_path, backup_path)
    manage_backup_history(file_path, max_backups)
    return backup_path


def unique_backup_path(file_path: Path) -> Path:
    """Return an unused backup path for file_path, named after the current time.

    When the name is taken (clocks can repeat a reading), the stamp moves
    forward a microsecond at a time, which keeps name order equal to creation
    order.
    """
    stamp = datetime.now().astimezone()
    while (path := _backup_path(file_path, stamp)).exists():
        stamp += timedelta(microseconds=1)
    return path


def manage_backup_history(
    file_path: Path, max_backups: int = DEFAULT_MAX_BACKUPS
) -> None:
    """Delete the oldest backups of file_path beyond the newest max_backups."""
    backups = sorted(file_path.parent.glob(f"{file_path.name}{_BACKUP_INFIX}*"))
    for old_backup in backups[:-max_backups]:
        old_backup.unlink()


def _backup_path(file_path: Path, stamp: datetime) -> Path:
    return file_path.with_name(
        f"{file_path.name}{_BACKUP_INFIX}{stamp.strftime(_STAMP_FORMAT)}"
    )
