"""
Git utility functions for KiCad Library Manager.
Handles Git hooks directory detection and safe hook management.
"""

import subprocess
from datetime import datetime
from pathlib import Path


def get_git_hooks_directory(repo_path: Path) -> Path:
    """
    Get the active Git hooks directory for a repository.

    This function detects the correct hooks directory by:
    1. Checking git config core.hooksPath (custom hooks directory)
    2. Falling back to .git/hooks (standard location)
    3. Handling Git worktrees where hooks live in the linked location

    Args:
        repo_path: Path to the Git repository

    Returns:
        Path to the active hooks directory

    Raises:
        RuntimeError: If the repository is not a valid Git repository
    """
    if not (repo_path / ".git").exists():
        raise RuntimeError(f"Not a Git repository: {repo_path}")

    # Check for custom hooks path via git config
    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0 and result.stdout.strip():
            custom_hooks_path = Path(result.stdout.strip())

            # If it's a relative path, make it relative to the repo
            if not custom_hooks_path.is_absolute():
                custom_hooks_path = repo_path / custom_hooks_path

            if custom_hooks_path.exists():
                return custom_hooks_path.resolve()
    except (subprocess.SubprocessError, OSError):
        pass

    # Check if this is a worktree (has .git file instead of directory)
    git_path = repo_path / ".git"
    if git_path.is_file():
        try:
            with git_path.open() as f:
                content = f.read().strip()
                if content.startswith("gitdir: "):
                    # This is a worktree, hooks are in the main repo
                    worktree_git_dir = Path(content[8:])
                    if worktree_git_dir.is_absolute():
                        hooks_dir = worktree_git_dir / "hooks"
                        if hooks_dir.exists():
                            return hooks_dir.resolve()
        except (OSError, UnicodeDecodeError):
            pass

    # Standard fallback to .git/hooks
    standard_hooks = repo_path / ".git" / "hooks"
    if not standard_hooks.exists():
        standard_hooks.mkdir(parents=True, exist_ok=True)

    return standard_hooks.resolve()


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
    backup_path.write_text(hook_path.read_text())

    # Preserve executable permissions
    if hook_path.stat().st_mode & 0o111:  # Check if executable
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
        lines = existing_content.split('\n')
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
            new_lines = lines[:start_idx] + [kilm_content] + lines[end_idx + 1:]
            return '\n'.join(new_lines)

    # Add KiLM content at the end with clear markers
    return f"{existing_content.rstrip()}\n\n{kilm_content}"


def create_kilm_hook_content() -> str:
    """
    Create the standard KiLM hook content with clear markers.

    Returns:
        Formatted hook content string
    """
    return """# BEGIN KiLM-managed section
# KiCad Library Manager auto-update hook
# Added by kilm add-hook command

echo "Running KiCad Library Manager update..."
kilm update

# Uncomment to set up libraries automatically (use with caution)
# kilm setup

echo "KiCad libraries update complete."
# END KiLM-managed section"""
