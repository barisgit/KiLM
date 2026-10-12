"""Tests for the Release workflow's GitHub publication (.github/scripts)."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from github_release import (
    Publication,
    Release,
    ReleaseError,
    file_digest,
    has_tag_ref,
    parse_release,
    publish_release,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

TAG = "v1.2.3"
COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40


class JobInterruptedError(Exception):
    """The job died after GitHub applied a write (lost response, cancelled runner)."""


class FakeGitHub:
    """In-memory GitHub whose writes can fail after taking effect.

    ``writes`` records each applied write; setting ``fail_after`` to a write's
    name raises JobInterruptedError right after that write is applied.
    """

    def __init__(self) -> None:
        """Start with no releases, no tags, and no injected failure."""
        self.releases: dict[str, Release] = {}
        self.tags: dict[str, str] = {}
        self.writes: list[str] = []
        self.fail_after: str | None = None

    def release(self, tag: str) -> Release | None:
        """Return the stored release, draft or published."""
        return self.releases.get(tag)

    def tag_commit(self, tag: str) -> str | None:
        """Return the stored tag target."""
        return self.tags.get(tag)

    def create_draft(self, tag: str, target: str, title: str, notes: str) -> None:
        """Store an empty draft; like gh, refuse a tag that already has a release."""
        assert tag not in self.releases, f"release {tag} already exists"
        assert title
        assert notes
        self.releases[tag] = Release(draft=True, target=target)
        self._wrote("create_draft")

    def upload(self, tag: str, files: Sequence[Path]) -> None:
        """Store the files one by one, so a failure leaves a partial upload."""
        release = self.releases[tag]
        for path in files:
            assets = {**release.assets, path.name: file_digest(path)}
            release = self.releases[tag] = replace(release, assets=assets)
            self._wrote("upload")

    def publish(self, tag: str) -> None:
        """Publish the draft and create the tag at its target if it is missing."""
        release = self.releases[tag]
        self.tags.setdefault(tag, release.target)
        self.releases[tag] = replace(release, draft=False)
        self._wrote("publish")

    def _wrote(self, operation: str) -> None:
        self.writes.append(operation)
        if operation == self.fail_after:
            raise JobInterruptedError(operation)


@pytest.fixture
def dist(tmp_path: Path) -> tuple[Path, ...]:
    """Two built files with distinct contents."""
    files = (tmp_path / "kilm-1.2.3.tar.gz", tmp_path / "kilm-1.2.3-py3-none-any.whl")
    for path in files:
        path.write_bytes(path.name.encode())
    return files


def publish(github: FakeGitHub, files: tuple[Path, ...]) -> None:
    """Publish ``files`` as release TAG of COMMIT."""
    publication = Publication(
        tag=TAG, commit=COMMIT, files=files, title="Release", notes="Notes"
    )
    publish_release(github, publication)


def assert_published(github: FakeGitHub, files: tuple[Path, ...]) -> None:
    """Assert TAG is a published release of COMMIT holding exactly ``files``."""
    release = github.releases[TAG]
    assert not release.draft
    assert github.tags[TAG] == COMMIT
    assert release.assets == {f.name: file_digest(f) for f in files}


def test_first_run_creates_uploads_then_publishes(dist: tuple[Path, ...]) -> None:
    """The draft gets every file before it is published."""
    github = FakeGitHub()
    publish(github, dist)
    assert github.writes == ["create_draft", "upload", "upload", "publish"]
    assert_published(github, dist)


@pytest.mark.parametrize(
    ("fail_after", "rerun_writes"),
    [
        ("create_draft", ["upload", "upload", "publish"]),
        ("upload", ["upload", "publish"]),
        ("publish", []),
    ],
)
def test_rerun_finishes_an_interrupted_publication(
    dist: tuple[Path, ...], fail_after: str, rerun_writes: list[str]
) -> None:
    """A rerun after any interrupted write does only the remaining writes."""
    github = FakeGitHub()
    github.fail_after = fail_after
    with pytest.raises(JobInterruptedError):
        publish(github, dist)

    github.fail_after = None
    github.writes.clear()
    publish(github, dist)
    assert github.writes == rerun_writes
    assert_published(github, dist)


def test_published_release_with_a_stale_asset_gets_it_replaced(
    dist: tuple[Path, ...],
) -> None:
    """Only the asset whose digest differs from the built file is uploaded."""
    github = FakeGitHub()
    publish(github, dist)
    release = github.releases[TAG]
    github.releases[TAG] = replace(
        release, assets={**release.assets, dist[0].name: "0" * 64}
    )

    github.writes.clear()
    publish(github, dist)
    assert github.writes == ["upload"]
    assert_published(github, dist)


@pytest.mark.parametrize("draft", [False, True], ids=["published", "draft"])
def test_release_of_another_commit_is_rejected_without_writes(
    dist: tuple[Path, ...], *, draft: bool
) -> None:
    """A release or tag of another commit stops the run before any write."""
    github = FakeGitHub()
    github.releases[TAG] = Release(draft=draft, target=OTHER_COMMIT)
    if not draft:
        github.tags[TAG] = OTHER_COMMIT

    with pytest.raises(ReleaseError, match=OTHER_COMMIT):
        publish(github, dist)
    assert github.writes == []


def test_parse_release_keeps_only_uploaded_assets_with_a_digest() -> None:
    """Assets still uploading or without a digest count as missing."""
    asset = {"name": "done.whl", "state": "uploaded", "digest": "sha256:abc"}
    view = {
        "isDraft": True,
        "targetCommitish": COMMIT,
        "assets": [
            asset,
            {**asset, "name": "partial.whl", "state": "open"},
            {**asset, "name": "old.whl", "digest": None},
        ],
    }
    assert parse_release(json.dumps(view)) == Release(
        draft=True, target=COMMIT, assets={"done.whl": "abc"}
    )


def test_parse_release_rejects_unexpected_output() -> None:
    """Output without the requested fields fails with a ReleaseError."""
    with pytest.raises(ReleaseError, match="isDraft"):
        parse_release(json.dumps({"targetCommitish": COMMIT, "assets": []}))


def test_has_tag_ref_ignores_longer_tags_with_the_same_prefix() -> None:
    """matching-refs lists every tag starting with the name; only exact counts."""
    refs = json.dumps([{"ref": f"refs/tags/{TAG}0"}])
    assert not has_tag_ref(refs, TAG)
    assert has_tag_ref(json.dumps([{"ref": f"refs/tags/{TAG}"}]), TAG)
