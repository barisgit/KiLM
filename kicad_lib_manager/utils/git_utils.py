"""Git hook management for KiCad Library Manager.

Finds a repository's active hooks directory and merges the KiLM sync hook
into existing hooks without losing their content.
"""

import shutil
import subprocess
from pathlib import Path

from kicad_lib_manager.utils.backup import unique_backup_path

_BEGIN_MARKER = "# BEGIN KiLM-managed section"
_END_MARKER = "# END KiLM-managed section"


def get_git_hooks_directory(repo_path: Path) -> Path:
    """Return the active Git hooks directory of repo_path, creating it if needed.

    Git is asked for the hooks path, which honours core.hooksPath and
    worktrees; when that fails, the hooks directory of the common Git
    directory is used.

    Raises:
        RuntimeError: repo_path does not exist, Git is not installed, or
            repo_path is not a Git repository.
    """
    if not repo_path.exists():
        msg = f"Repository path does not exist: {repo_path}"
        raise RuntimeError(msg)

    hooks_dir = _rev_parse_path(repo_path, "--git-path", "hooks")
    if hooks_dir is None:
        common_dir = _rev_parse_path(repo_path, "--git-common-dir")
        if common_dir is None:
            msg = f"Not a Git repository: {repo_path}"
            raise RuntimeError(msg)
        hooks_dir = (common_dir / "hooks").resolve()
    hooks_dir.mkdir(parents=True, exist_ok=True)
    return hooks_dir


def _rev_parse_path(repo_path: Path, *args: str) -> Path | None:
    """Return the path `git rev-parse` prints for args, or None if it fails.

    A relative path is resolved against repo_path.
    """
    git = shutil.which("git")
    if git is None:
        msg = "Git is not installed or not on PATH"
        raise RuntimeError(msg)
    try:
        result = subprocess.run(  # noqa: S603 -- fixed git rev-parse command; repo_path is passed as one argument
            [git, "-C", str(repo_path), "rev-parse", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (repo_path / path).resolve()


def backup_existing_hook(hook_path: Path) -> Path:
    """Copy hook_path to a timestamped sibling and return the copy's path.

    The copy keeps the hook's permission bits, so an executable hook stays
    executable, and never overwrites an earlier backup.
    """
    backup_path = unique_backup_path(hook_path)
    shutil.copy2(hook_path, backup_path)
    return backup_path


def merge_hook_content(existing_content: str, kilm_content: str) -> str:
    """Return existing_content with kilm_content as its KiLM-managed section.

    A complete KiLM-managed section in existing_content is replaced in place;
    otherwise kilm_content is appended after a blank line.
    """
    lines = existing_content.split("\n")
    stripped = [line.strip() for line in lines]
    if _BEGIN_MARKER in stripped:
        start = stripped.index(_BEGIN_MARKER)
        if _END_MARKER in stripped[start:]:
            end = stripped.index(_END_MARKER, start)
            return "\n".join([*lines[:start], kilm_content, *lines[end + 1 :]])

    return f"{existing_content.rstrip()}\n\n{kilm_content}"


def create_kilm_hook_content() -> str:
    """Return the KiLM hook section, which runs `kilm sync`, between its markers."""
    return f"""{_BEGIN_MARKER}
# KiCad Library Manager auto-sync hook
# Added by kilm add-hook command

echo "Running KiCad Library Manager sync..."
kilm sync

# Uncomment to set up libraries automatically (use with caution)
# kilm setup

echo "KiCad libraries sync complete."
{_END_MARKER}"""
