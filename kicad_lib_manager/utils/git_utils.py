"""
Git utility functions for KiCad Library Manager.
Handles Git hooks directory detection and safe hook management.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path


def get_git_hooks_directory(repo_path: Path) -> Path:
    """
    Get the active Git hooks directory for a repository.

    This function detects the correct hooks directory by:
    1. Using git rev-parse --git-path hooks (handles core.hooksPath, worktrees, and common dir)
    2. Falling back to git rev-parse --git-common-dir + hooks

    Args:
        repo_path: Path to the Git repository

    Returns:
        Path to the active hooks directory

    Raises:
        RuntimeError: If the repository is not a valid Git repository
    """
    if not repo_path.exists():
        raise RuntimeError(f"Repository path does not exist: {repo_path}")

    # Ask Git for the effective hooks directory. Handles core.hooksPath, worktrees, and common dir.
    try:
        rp = subprocess.run(
            ["git", "-C", str(repo_path), "rev-parse", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            check=True,
        )
        hooks_dir = Path(rp.stdout.strip())
        if not hooks_dir.is_absolute():
            hooks_dir = (repo_path / hooks_dir).resolve()
        hooks_dir.mkdir(parents=True, exist_ok=True)
        return hooks_dir
    except subprocess.CalledProcessError as e:
        # Fallback: resolve common dir then append hooks
        try:
            cd = subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", "--git-common-dir"],
                capture_output=True,
                text=True,
                check=True,
            )
            common_dir = Path(cd.stdout.strip())
            if not common_dir.is_absolute():
                common_dir = (repo_path / common_dir).resolve()
            hooks_dir = common_dir / "hooks"
            hooks_dir.mkdir(parents=True, exist_ok=True)
            return hooks_dir.resolve()
        except subprocess.CalledProcessError:
            raise RuntimeError(f"Not a Git repository: {repo_path}") from e


def backup_existing_hook(hook_path: Path) -> Path:
    """
    Create a timestamped backup of an existing hook file.

    Args:
        hook_path: Path to the existing hook file

    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = hook_path.with_suffix(f".backup.{timestamp}")

    # Copy the file content
    backup_path.write_text(hook_path.read_text(encoding="utf-8"))

    # Preserve executable permissions (Unix-like systems only)
    if (
        os.name != "nt" and hook_path.stat().st_mode & 0o111
    ):  # Not Windows and executable
        backup_path.chmod(0o755)

    return backup_path


def merge_hook_content(existing_content: str, kilm_content: str) -> str:
    """
    Safely merge existing hook content with KiLM content.

    Args:
        existing_content: Content of existing hook
        kilm_content: KiLM hook content to add

    Returns:
        Merged hook content
    """
    # Check if KiLM content is already present
    if "KiLM-managed section" in existing_content:
        # Already has KiLM content, replace the section
        lines = existing_content.split("\n")
        start_marker = "# BEGIN KiLM-managed section"
        end_marker = "# END KiLM-managed section"

        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if line.strip() == start_marker:
                start_idx = i
            elif line.strip() == end_marker:
                end_idx = i
                break

        if start_idx is not None and end_idx is not None:
            # Replace existing KiLM section
            new_lines = lines[:start_idx] + [kilm_content] + lines[end_idx + 1 :]
            return "\n".join(new_lines)

    # Add KiLM content at the end with clear markers
    return f"{existing_content.rstrip()}\n\n{kilm_content}"


def create_kilm_hook_content() -> str:
    """
    Create the standard KiLM hook content with clear markers.

    Returns:
        Formatted hook content string
    """
    return """# BEGIN KiLM-managed section
# KiCad Library Manager auto-sync hook
# Added by kilm add-hook command

echo "Running KiCad Library Manager sync..."
kilm sync

# Uncomment to set up libraries automatically (use with caution)
# kilm setup

echo "KiCad libraries sync complete."
# END KiLM-managed section"""
