"""The suite runs CLI commands, which check for updates; keep them contained."""

import tempfile
from pathlib import Path

import pytest
import requests


def test_home_is_a_temporary_directory() -> None:
    """Config, cache, and KiCad files land in a per-test home, not the user's."""
    temp_root = Path(tempfile.gettempdir()).resolve()

    assert Path.home().resolve().is_relative_to(temp_root)


def test_network_requests_fail() -> None:
    """The update check cannot reach PyPI, so results never depend on it."""
    with pytest.raises(requests.ConnectionError):
        requests.get("https://pypi.org/pypi/kilm/json", timeout=5)
