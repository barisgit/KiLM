"""
Tests for Git utility functions.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kicad_lib_manager.utils.git_utils import (
    backup_existing_hook,
    create_kilm_hook_content,
    get_git_hooks_directory,
    merge_hook_content,
)


class TestGitUtils:
    """Test cases for Git utility functions."""

    def test_create_kilm_hook_content(self):
        """Test that KiLM hook content is created with proper markers."""
        content = create_kilm_hook_content()

        assert "BEGIN KiLM-managed section" in content
        assert "END KiLM-managed section" in content
        assert "kilm update" in content
        assert "kilm setup" in content
        assert content.startswith("# BEGIN KiLM-managed section")
        assert content.endswith("# END KiLM-managed section")

    def test_backup_existing_hook(self, tmp_path):
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
        assert backup_path.stat().st_mode & 0o111  # Check executable bit

    def test_merge_hook_content_new_content(self):
        """Test merging when no KiLM content exists."""
        existing = "#!/bin/sh\necho 'existing hook'"
        kilm_content = create_kilm_hook_content()

        result = merge_hook_content(existing, kilm_content)

        assert "existing hook" in result
        assert "BEGIN KiLM-managed section" in result
        assert "END KiLM-managed section" in result
        assert result.count("BEGIN KiLM-managed section") == 1

    def test_merge_hook_content_replace_existing(self):
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
        assert "kilm update" in result

    @patch('subprocess.run')
    def test_get_git_hooks_directory_standard(self, mock_run, tmp_path):
        """Test standard hooks directory detection."""
        mock_run.return_value = Mock(returncode=1, stdout="")

        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git" / "hooks").mkdir(parents=True, exist_ok=True)

        hooks_dir = get_git_hooks_directory(repo_path)

        assert hooks_dir == (repo_path / ".git" / "hooks").resolve()
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_git_hooks_directory_custom_path(self, mock_run, tmp_path):
        """Test custom hooks directory detection."""
        custom_hooks = tmp_path / "custom" / "hooks"
        custom_hooks.mkdir(parents=True, exist_ok=True)

        mock_run.return_value = Mock(returncode=0, stdout=str(custom_hooks))

        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        hooks_dir = get_git_hooks_directory(repo_path)

        assert hooks_dir == custom_hooks.resolve()
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_get_git_hooks_directory_relative_path(self, mock_run):
        """Test relative custom hooks path handling."""
        mock_run.return_value = Mock(returncode=0, stdout="custom/hooks")

        repo_path = Path("/tmp/test-repo")
        repo_path.mkdir(exist_ok=True)
        (repo_path / "custom" / "hooks").mkdir(parents=True, exist_ok=True)

        hooks_dir = get_git_hooks_directory(repo_path)

        assert hooks_dir == (repo_path / "custom" / "hooks").resolve()
        mock_run.assert_called_once()

    def test_get_git_hooks_directory_worktree(self, tmp_path):
        """Test Git worktree hooks directory detection."""
        # Create a mock worktree structure
        repo_path = tmp_path / "worktree"
        repo_path.mkdir()

        # Create .git file pointing to main repo
        git_file = repo_path / ".git"
        main_git_dir = tmp_path / "main-repo" / ".git"
        main_git_dir.mkdir(parents=True)
        (main_git_dir / "hooks").mkdir()

        git_file.write_text(f"gitdir: {main_git_dir}")

        hooks_dir = get_git_hooks_directory(repo_path)

        assert hooks_dir == (main_git_dir / "hooks").resolve()

    def test_get_git_hooks_directory_not_repo(self, tmp_path):
        """Test error when directory is not a Git repository."""
        with pytest.raises(RuntimeError, match="Not a Git repository"):
            get_git_hooks_directory(tmp_path)

    def test_get_git_hooks_directory_creates_standard(self, tmp_path):
        """Test that standard hooks directory is created if it doesn't exist."""
        repo_path = tmp_path / "test-repo"
        repo_path.mkdir()
        (repo_path / ".git").mkdir()

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")

            hooks_dir = get_git_hooks_directory(repo_path)

            assert hooks_dir.exists()
            assert hooks_dir == (repo_path / ".git" / "hooks").resolve()
