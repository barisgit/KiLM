"""Tests for timestamped file backups."""

from datetime import datetime, timezone, tzinfo
from pathlib import Path

import pytest

from kicad_lib_manager.utils import backup
from kicad_lib_manager.utils.backup import create_backup

FROZEN_NOW = datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=timezone.utc)


class _FrozenClock:
    """Stands in for the datetime class: now() always reads FROZEN_NOW."""

    @staticmethod
    def now(tz: tzinfo | None = None) -> datetime:
        """FROZEN_NOW in the requested zone, local time when tz is None."""
        return FROZEN_NOW.astimezone(tz)


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every backup see the same instant."""
    monkeypatch.setattr(backup, "datetime", _FrozenClock)


def test_backup_copies_the_file(tmp_path: Path) -> None:
    """The backup sits next to the file and holds its content."""
    original = tmp_path / "sym-lib-table"
    original.write_text("v1", encoding="utf-8")

    backup_path = create_backup(original)

    assert backup_path.parent == tmp_path
    assert backup_path.name.startswith("sym-lib-table.backup.")
    assert backup_path.read_text(encoding="utf-8") == "v1"


@pytest.mark.usefixtures("frozen_clock")
def test_backups_in_the_same_instant_keep_every_version(tmp_path: Path) -> None:
    """Backups taken at the same clock reading get distinct names (issue #12)."""
    original = tmp_path / "kicad_common.json"
    paths = []
    for version in ("v1", "v2", "v3"):
        original.write_text(version, encoding="utf-8")
        paths.append(create_backup(original))

    assert len(set(paths)) == 3
    assert [p.read_text(encoding="utf-8") for p in paths] == ["v1", "v2", "v3"]
    # Name order is creation order, which the history pruning relies on.
    assert sorted(paths) == paths


@pytest.mark.usefixtures("frozen_clock")
def test_history_keeps_the_newest_backups(tmp_path: Path) -> None:
    """Pruning removes the oldest backups, even within one clock reading."""
    original = tmp_path / "fp-lib-table"
    for version in ("v1", "v2", "v3"):
        original.write_text(version, encoding="utf-8")
        create_backup(original, max_backups=2)

    kept = sorted(tmp_path.glob("fp-lib-table.backup.*"))
    assert [p.read_text(encoding="utf-8") for p in kept] == ["v2", "v3"]


def test_missing_file_raises(tmp_path: Path) -> None:
    """Backing up a file that does not exist fails without creating anything."""
    with pytest.raises(FileNotFoundError, match="File not found"):
        create_backup(tmp_path / "absent")
    assert not list(tmp_path.iterdir())
