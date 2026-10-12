"""Create or finish the GitHub release for a version that PyPI already holds.

The Release workflow's ``github`` job runs this after PyPI serves the built
files. It reads GitHub's current state on every run instead of trusting the
plan job's snapshot, so "Re-run failed jobs" finishes a publication that
stopped part way and accepts one that already finished.

The release starts as a draft without assets. The built files are uploaded
to it, and only then is it published, which creates the tag at the verified
commit. A published release therefore always has every file, and a draft
marks an unfinished attempt.

Usage: python3 github_release.py DIST_DIR, with NAME, VERSION,
GITHUB_REPOSITORY, RELEASE_SHA, and GH_TOKEN in the environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, TypedDict

DIGEST_PREFIX = "sha256:"


class ReleaseError(Exception):
    """GitHub holds a release or tag that this commit's files cannot complete."""


@dataclass(frozen=True)
class Release:
    """The parts of a GitHub release that decide what is left to publish.

    ``assets`` maps each fully uploaded asset name to its SHA-256 hex digest;
    assets that are still uploading or have no digest are left out, so they
    count as missing.
    """

    draft: bool
    target: str
    assets: dict[str, str] = field(default_factory=dict)


class GitHub(Protocol):
    """The GitHub operations a release needs, addressed by tag name."""

    def release(self, tag: str) -> Release | None:
        """Return the published or draft release for ``tag``, if any."""
        ...

    def tag_commit(self, tag: str) -> str | None:
        """Return the commit SHA that ``tag`` points at, if the tag exists."""
        ...

    def create_draft(self, tag: str, target: str, title: str, notes: str) -> None:
        """Create a draft release for ``tag`` that will tag ``target``."""
        ...

    def upload(self, tag: str, files: Sequence[Path]) -> None:
        """Upload ``files``, replacing assets of the same name."""
        ...

    def publish(self, tag: str) -> None:
        """Publish the draft release for ``tag``, creating the tag."""
        ...


def file_digest(path: Path) -> str:
    """Return the SHA-256 hex digest of ``path``."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publish_release(
    github: GitHub,
    *,
    tag: str,
    commit: str,
    files: Sequence[Path],
    title: str,
    notes: str,
) -> None:
    """Make ``tag`` a published release of ``commit`` that holds ``files``.

    Safe to repeat: each step checks GitHub first and only does what is
    missing, so a run that stopped after any step is completed by the next
    one. Raises ReleaseError when the tag or a draft belongs to another
    commit, or when GitHub does not hold the expected state at the end.
    """
    _check_tag(github, tag, commit)
    release = github.release(tag)
    if release is None:
        github.create_draft(tag, commit, title, notes)
        release = Release(draft=True, target=commit)
    elif release.draft and release.target != commit:
        msg = f"Draft release {tag} targets {release.target}, not {commit}"
        raise ReleaseError(msg)

    missing = [f for f in files if release.assets.get(f.name) != file_digest(f)]
    if missing:
        github.upload(tag, missing)
    if release.draft:
        github.publish(tag)

    _verify(github, tag, commit, files)


def _check_tag(github: GitHub, tag: str, commit: str) -> None:
    tag_commit = github.tag_commit(tag)
    if tag_commit not in (None, commit):
        msg = f"Tag {tag} points at {tag_commit}, not {commit}"
        raise ReleaseError(msg)


def _verify(github: GitHub, tag: str, commit: str, files: Sequence[Path]) -> None:
    release = github.release(tag)
    if release is None or release.draft:
        msg = f"Release {tag} is not published"
        raise ReleaseError(msg)
    if github.tag_commit(tag) != commit:
        msg = f"Tag {tag} does not point at {commit}"
        raise ReleaseError(msg)
    wrong = [f.name for f in files if release.assets.get(f.name) != file_digest(f)]
    if wrong:
        msg = f"Release {tag} assets differ from the built files: {', '.join(wrong)}"
        raise ReleaseError(msg)


class _AssetJson(TypedDict):
    name: str
    state: str
    digest: str | None


class _ReleaseJson(TypedDict):
    isDraft: bool
    targetCommitish: str
    assets: list[_AssetJson]


class _RefJson(TypedDict):
    ref: str


class GhCli:
    """GitHub operations through the ``gh`` CLI, authenticated by GH_TOKEN."""

    def __init__(self, repo: str) -> None:
        """Address the repository ``repo`` (``owner/name``)."""
        self.repo = repo

    def release(self, tag: str) -> Release | None:
        """Return the release for ``tag``; ``gh release view`` also finds drafts."""
        result = _gh(
            "release", "view", tag, "--repo", self.repo,
            "--json", "isDraft,targetCommitish,assets",
            check=False,
        )  # fmt: skip
        if result.returncode != 0:
            if "release not found" in result.stderr:
                return None
            raise ReleaseError(result.stderr.strip())
        data: _ReleaseJson = json.loads(result.stdout)
        assets = {
            asset["name"]: digest.removeprefix(DIGEST_PREFIX)
            for asset in data["assets"]
            if asset["state"] == "uploaded"
            and (digest := asset["digest"] or "").startswith(DIGEST_PREFIX)
        }
        return Release(
            draft=data["isDraft"], target=data["targetCommitish"], assets=assets
        )

    def tag_commit(self, tag: str) -> str | None:
        """Return the commit of ``refs/tags/<tag>``, peeling annotated tags."""
        ref = f"refs/tags/{tag}"
        # matching-refs answers an absent tag with an empty list instead of an error.
        refs: list[_RefJson] = json.loads(
            _gh("api", f"repos/{self.repo}/git/matching-refs/tags/{tag}").stdout
        )
        if all(r["ref"] != ref for r in refs):
            return None
        return _gh(
            "api", f"repos/{self.repo}/commits/{ref}", "--jq", ".sha"
        ).stdout.strip()

    def create_draft(self, tag: str, target: str, title: str, notes: str) -> None:
        """Create the draft; ``--notes`` is prepended to the generated notes."""
        _gh(
            "release", "create", tag, "--repo", self.repo, "--draft",
            "--target", target, "--title", title, "--generate-notes",
            "--notes", notes,
        )  # fmt: skip

    def upload(self, tag: str, files: Sequence[Path]) -> None:
        """Upload ``files``; ``--clobber`` replaces partial or stale assets."""
        _gh(
            "release", "upload", tag, *map(str, files), "--repo", self.repo, "--clobber"
        )

    def publish(self, tag: str) -> None:
        """Publish the draft, which creates the tag at its target commit."""
        _gh("release", "edit", tag, "--repo", self.repo, "--draft=false")


def _gh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603 -- fixed gh subcommands; values come from the workflow
        ["gh", *args], capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        msg = f"gh {args[0]} {args[1]} failed: {result.stderr.strip()}"
        raise ReleaseError(msg)
    return result


def main(argv: Sequence[str]) -> int:
    """Publish the files in ``argv[1]`` as the release of the environment's version."""
    name, version = os.environ["NAME"], os.environ["VERSION"]
    tag = f"v{version}"
    files = sorted(p for p in Path(argv[1]).iterdir() if p.is_file())
    notes = (
        f"Install with `pipx install {name}=={version}` or "
        f"`uv tool install {name}=={version}`; "
        "upgrade an existing install with `kilm update`."
    )
    try:
        publish_release(
            GhCli(os.environ["GITHUB_REPOSITORY"]),
            tag=tag,
            commit=os.environ["RELEASE_SHA"],
            files=files,
            title=f"Release {tag}",
            notes=notes,
        )
    except ReleaseError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1
    print(f"Release {tag} is published with {len(files)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
