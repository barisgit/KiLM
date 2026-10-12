"""Tests for the Release workflow's GitHub publication (.github/scripts)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest
from github_release import Release, ReleaseError, file_digest, publish_release

TAG = "v1.2.3"
COMMIT = "a" * 40


class JobInterruptedError(Exception):
    """The job died after GitHub applied a write (lost response, cancelled runner)."""


class FakeGitHub:
    """In-memory GitHub whose writes can fail after taking effect."""

    def __init__(self) -> None:
        self.releases: dict[str, Release] = {}
        self.tags: dict[str, str] = {}
        self.writes: list[str] = []
        self.fail_after: str | None = None

    def release(self, tag: str) -> Release | None:
        return self.releases.get(tag)

    def tag_commit(self, tag: str) -> str | None:
        return self.tags.get(tag)

    def create_draft(self, tag: str, target: str, title: str, notes: str) -> None:
        # gh release create rejects a tag that already has a release.
        assert tag not in self.releases, f"release {tag} already exists"
        assert title
        assert notes
        self.releases[tag] = Release(draft=True, target=target)
        self._wrote("create_draft")

    def upload(self, tag: str, files: Sequence[Path]) -> None:
        release = self.releases[tag]
        for path in files:
            assets = {**release.assets, path.name: file_digest(path)}
            release = self.releases[tag] = replace(release, assets=assets)
            # Failing here leaves a partial upload: only the first file arrived.
            self._wrote("upload")

    def publish(self, tag: str) -> None:
        release = self.releases[tag]
        self.tags.setdefault(tag, release.target)
        self.releases[tag] = replace(release, draft=False)
        self._wrote("publish")

    def _wrote(self, operation: str) -> None:
        self.writes.append(operation)
        if operation == self.fail_after:
            raise JobInterruptedError(operation)


@pytest.fixture
def dist(tmp_path: Path) -> list[Path]:
    files = [tmp_path / "kilm-1.2.3.tar.gz", tmp_path / "kilm-1.2.3-py3-none-any.whl"]
    for path in files:
        path.write_bytes(path.name.encode())
    return files


def publish(github: FakeGitHub, files: list[Path]) -> None:
    publish_release(
        github, tag=TAG, commit=COMMIT, files=files, title="Release", notes="Notes"
    )


def assert_published(github: FakeGitHub, files: list[Path]) -> None:
    release = github.releases[TAG]
    assert not release.draft
    assert github.tags[TAG] == COMMIT
    assert release.assets == {f.name: file_digest(f) for f in files}


def test_first_run_creates_uploads_then_publishes(dist: list[Path]) -> None:
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
    dist: list[Path], fail_after: str, rerun_writes: list[str]
) -> None:
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
    dist: list[Path],
) -> None:
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


@pytest.mark.parametrize("draft", [False, True])
def test_release_of_another_commit_is_rejected_without_writes(
    dist: list[Path], draft: bool
) -> None:
    other = "b" * 40
    github = FakeGitHub()
    github.releases[TAG] = Release(draft=draft, target=other)
    if not draft:
        github.tags[TAG] = other

    with pytest.raises(ReleaseError, match=other):
        publish(github, dist)
    assert github.writes == []
