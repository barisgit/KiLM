"""Suite-wide fixtures that keep tests away from the user's machine."""

from pathlib import Path

import pytest
import requests


def _no_network(*_args: object, **_kwargs: object) -> requests.Response:
    """Stand in for requests.get; tests that need a response patch it."""
    message = "tests must not use the network"
    raise requests.ConnectionError(message)


@pytest.fixture(autouse=True)
def _isolated_user(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Give each test an empty home and no network.

    Every CLI invocation runs the update check, which reads the KiLM config,
    writes the version cache, and asks PyPI. Without this the suite would
    depend on and change the real home directory and the network.
    """
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(requests, "get", _no_network)
    return home
