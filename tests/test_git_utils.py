"""Tests for Git utility functions."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kicad_lib_manager.utils import git_utils
from kicad_lib_manager.utils.git_utils import (
    backup_existing_hook,
    create_kilm_hook_content,
    get_git_hooks_directory,
    merge_hook_content,
)


class TestGitUtils:
    """Test cases for Git utility functions."""

    def test_create_kilm_hook_content(self) -> None:
        """Test that KiLM hook content is created with proper markers."""
        content = create_kilm_hook_content()

        assert "BEGIN KiLM-managed section" in content
        assert "END KiLM-managed section" in content
        assert "kilm sync" in content
        assert "kilm setup" in content
        assert content.startswith("# BEGIN KiLM-managed section")
        assert content.endswith("# END KiLM-managed section")

    def test_backup_existing_hook(self, tmp_path: Path) -> None:
        """Test backup creation with timestamp."""
        hook_file = tmp_path / "post-merge"
        hook_content = "#!/bin/sh\necho 'test hook'"
        hook_file.write_text(hook_content)
        hook_file.chmod(0o755)

        backup_path = backup_existing_hook(hook_file)

        assert backup_path.exists()
        assert backup_path != hook_file
        assert backup_path.read_text() == hook_content
        assert backup_path.name.startswith("post-merge.backup.")

        # Check executable bit only on Unix-like systems
        if os.name != "nt":  # Not Windows
            assert backup_path.stat().st_mode & 0o111  # Check executable bit

    def test_merge_hook_content_new_content(self) -> None:
        """Test merging when no KiLM content exists."""
        existing = "#!/bin/sh\necho 'existing hook'"
        kilm_content = create_kilm_hook_content()

        result = merge_hook_content(existing, kilm_content)

        assert "existing hook" in result
        assert "BEGIN KiLM-managed section" in result
        assert "END KiLM-managed section" in result
        assert result.count("BEGIN KiLM-managed section") == 1

    def test_merge_hook_content_replace_existing(self) -> None:
        """Test merging when KiLM content already exists."""
        existing = """#!/bin/sh
echo 'existing hook'
# BEGIN KiLM-managed section
# old kilm content
# END KiLM-managed section
echo 'after kilm'"""

        kilm_content = create_kilm_hook_content()

        result = merge_hook_content(existing, kilm_content)

        assert "existing hook" in result
        assert "after kilm" in result
        assert result.count("BEGIN KiLM-managed section") == 1
        assert result.count("END KiLM-managed section") == 1
        assert "old kilm content" not in result
        assert "kilm sync" in result

    @pytest.mark.parametrize("relative", [True, False])
    @patch("subprocess.run")
    def test_get_git_hooks_directory_asks_git(
        self, mock_run: Mock, tmp_path: Path, *, relative: bool
    ) -> None:
        """Git's hooks path is used, relative to the repository or as given.

        core.hooksPath and worktrees reach this as such a path.
        """
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        if relative:
            hooks = repo_path / "custom" / "hooks"
            mock_run.return_value = Mock(returncode=0, stdout="custom/hooks")
        else:
            hooks = tmp_path / "main-repo" / ".git" / "hooks"
            mock_run.return_value = Mock(returncode=0, stdout=str(hooks))

        assert get_git_hooks_directory(repo_path) == hooks
        assert hooks.is_dir()
        mock_run.assert_called_once()

    def test_get_git_hooks_directory_without_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing git executable is reported, not raised as FileNotFoundError."""
        monkeypatch.setattr(git_utils.shutil, "which", lambda _name: None)
        with pytest.raises(RuntimeError, match="Git is not installed"):
            get_git_hooks_directory(tmp_path)

    def test_get_git_hooks_directory_not_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test error when directory is not a Git repository."""
        # Clear git environment (e.g. GIT_DIR is exported to hooks during
        # `git commit`, which would make rev-parse succeed against this repo)
        for var in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(RuntimeError, match="Not a Git repository"):
            get_git_hooks_directory(tmp_path)
