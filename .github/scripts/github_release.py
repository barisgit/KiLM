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
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

DIGEST_PREFIX = "sha256:"
UPLOADED_STATE = "uploaded"

_FieldType = TypeVar("_FieldType")


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


@dataclass(frozen=True)
class Publication:
    """What one run publishes: release ``tag`` of ``commit`` holding ``files``.

    ``title`` and ``notes`` are used only when the run creates the release;
    an existing release keeps its own.
    """

    tag: str
    commit: str
    files: tuple[Path, ...]
    title: str
    notes: str


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


def publish_release(github: GitHub, publication: Publication) -> None:
    """Make ``publication.tag`` a published release of its commit and files.

    Safe to repeat: each step checks GitHub first and only does what is
    missing, so a run that stopped after any step is completed by the next
    one. Raises ReleaseError when the tag or a draft belongs to another
    commit, or when GitHub does not hold the expected state at the end.
    """
    tag, commit = publication.tag, publication.commit
    _check_tag(github, tag, commit)
    release = github.release(tag)
    if release is None:
        github.create_draft(tag, commit, publication.title, publication.notes)
        release = Release(draft=True, target=commit)
    elif release.draft and release.target != commit:
        msg = f"Draft release {tag} targets {release.target}, not {commit}"
        raise ReleaseError(msg)

    missing = _differing_files(release, publication.files)
    if missing:
        github.upload(tag, missing)
    if release.draft:
        github.publish(tag)

    _verify(github, publication)


def _differing_files(release: Release, files: Sequence[Path]) -> list[Path]:
    """Return the ``files`` that ``release`` lacks or holds with other bytes."""
    return [f for f in files if release.assets.get(f.name) != file_digest(f)]


def _check_tag(github: GitHub, tag: str, commit: str) -> None:
    tag_commit = github.tag_commit(tag)
    if tag_commit not in {None, commit}:
        msg = f"Tag {tag} points at {tag_commit}, not {commit}"
        raise ReleaseError(msg)


def _verify(github: GitHub, publication: Publication) -> None:
    tag, commit = publication.tag, publication.commit
    release = github.release(tag)
    if release is None or release.draft:
        msg = f"Release {tag} is not published"
        raise ReleaseError(msg)
    if github.tag_commit(tag) != commit:
        msg = f"Tag {tag} does not point at {commit}"
        raise ReleaseError(msg)
    wrong = [f.name for f in _differing_files(release, publication.files)]
    if wrong:
        msg = f"Release {tag} assets differ from the built files: {', '.join(wrong)}"
        raise ReleaseError(msg)


def parse_release(text: str) -> Release:
    """Read ``gh release view --json isDraft,targetCommitish,assets`` output.

    Only assets in the ``uploaded`` state with a ``sha256:`` digest are kept.
    Raises ReleaseError when the JSON does not have the expected shape.
    """
    data = _json_object(json.loads(text))
    assets: dict[str, str] = {}
    for item in _field(data, "assets", list):
        asset = _json_object(item)
        digest = asset.get("digest")
        if (
            _field(asset, "state", str) == UPLOADED_STATE
            and isinstance(digest, str)
            and digest.startswith(DIGEST_PREFIX)
        ):
            assets[_field(asset, "name", str)] = digest.removeprefix(DIGEST_PREFIX)
    return Release(
        draft=_field(data, "isDraft", bool),
        target=_field(data, "targetCommitish", str),
        assets=assets,
    )


def has_tag_ref(text: str, tag: str) -> bool:
    """Tell whether ``git/matching-refs/tags/<tag>`` output holds exactly ``tag``.

    The endpoint matches by prefix, so ``v1.2`` also lists ``v1.2.3``; only an
    exact ``refs/tags/<tag>`` counts.
    """
    ref = f"refs/tags/{tag}"
    refs = _json_list(json.loads(text))
    return any(_field(_json_object(item), "ref", str) == ref for item in refs)


def _json_object(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        msg = f"Expected a JSON object from gh, got {type(value).__name__}"
        raise ReleaseError(msg)
    # JSON object keys are always strings; the check narrows the key type.
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _json_list(value: object) -> list[object]:
    if not isinstance(value, list):
        msg = f"Expected a JSON array from gh, got {type(value).__name__}"
        raise ReleaseError(msg)
    return list(value)


def _field(data: Mapping[str, object], key: str, kind: type[_FieldType]) -> _FieldType:
    value = data.get(key)
    if not isinstance(value, kind):
        msg = f"Expected {kind.__name__} {key!r} in gh output, got {value!r}"
        raise ReleaseError(msg)
    return value


class GhCli:
    """GitHub operations through the ``gh`` CLI, authenticated by GH_TOKEN."""

    def __init__(self, repo: str) -> None:
        """Address the repository ``repo`` (``owner/name``) through ``gh`` on PATH.

        Raises ReleaseError when ``gh`` is not installed.
        """
        executable = shutil.which("gh")
        if executable is None:
            msg = "The gh CLI is not on PATH"
            raise ReleaseError(msg)
        self.repo = repo
        self._executable = executable

    def release(self, tag: str) -> Release | None:
        """Return the release for ``tag``; ``gh release view`` also finds drafts."""
        result = self._run(
            "release", "view", tag, "--repo", self.repo,
            "--json", "isDraft,targetCommitish,assets",
            check=False,
        )  # fmt: skip
        if result.returncode != 0:
            if "release not found" in result.stderr:
                return None
            raise ReleaseError(result.stderr.strip())
        return parse_release(result.stdout)

    def tag_commit(self, tag: str) -> str | None:
        """Return the commit of ``refs/tags/<tag>``, peeling annotated tags."""
        # matching-refs answers an absent tag with an empty list instead of an error.
        refs = self._run("api", f"repos/{self.repo}/git/matching-refs/tags/{tag}")
        if not has_tag_ref(refs.stdout, tag):
            return None
        commit = self._run(
            "api", f"repos/{self.repo}/commits/refs/tags/{tag}", "--jq", ".sha"
        )
        return commit.stdout.strip()

    def create_draft(self, tag: str, target: str, title: str, notes: str) -> None:
        """Create the draft; ``--notes`` is prepended to the generated notes."""
        self._run(
            "release", "create", tag, "--repo", self.repo, "--draft",
            "--target", target, "--title", title, "--generate-notes",
            "--notes", notes,
        )  # fmt: skip

    def upload(self, tag: str, files: Sequence[Path]) -> None:
        """Upload ``files``; ``--clobber`` replaces partial or stale assets."""
        paths = [str(path) for path in files]
        self._run("release", "upload", tag, *paths, "--repo", self.repo, "--clobber")

    def publish(self, tag: str) -> None:
        """Publish the draft, which creates the tag at its target commit."""
        self._run("release", "edit", tag, "--repo", self.repo, "--draft=false")

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run ``gh`` with ``args``; raise ReleaseError on failure when ``check``."""
        result = subprocess.run(  # noqa: S603 -- fixed gh subcommands; values come from the workflow
            [self._executable, *args], capture_output=True, text=True, check=False
        )
        if check and result.returncode != 0:
            msg = f"gh {args[0]} {args[1]} failed: {result.stderr.strip()}"
            raise ReleaseError(msg)
        return result


def publication_from_environment(dist_dir: Path) -> Publication:
    """Describe the release of every file in ``dist_dir`` from NAME and VERSION.

    Reads RELEASE_SHA for the commit; raises KeyError when a variable is unset.
    """
    name, version = os.environ["NAME"], os.environ["VERSION"]
    tag = f"v{version}"
    notes = (
        f"Install with `pipx install {name}=={version}` or "
        f"`uv tool install {name}=={version}`; "
        "upgrade an existing install with `kilm update perform`."
    )
    return Publication(
        tag=tag,
        commit=os.environ["RELEASE_SHA"],
        files=tuple(sorted(p for p in dist_dir.iterdir() if p.is_file())),
        title=f"Release {tag}",
        notes=notes,
    )


def main(argv: Sequence[str]) -> int:
    """Publish the files in ``argv[1]`` as the release of the environment's version.

    Returns the exit status; a ReleaseError becomes a workflow error annotation.
    """
    publication = publication_from_environment(Path(argv[1]))
    try:
        publish_release(GhCli(os.environ["GITHUB_REPOSITORY"]), publication)
    except ReleaseError as error:
        sys.stderr.write(f"::error::{error}\n")
        return 1
    count = len(publication.files)
    sys.stdout.write(f"Release {publication.tag} is published with {count} files.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
