"""Tests for the cached PyPI latest-release lookup."""

import json
import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from kicad_lib_manager.services.pypi_version import (
    CACHE_TTL_SECONDS,
    PyPIVersionChecker,
)


@pytest.fixture
def cache_file(tmp_path: Path) -> Path:
    """A cache location inside the test's temporary directory."""
    return tmp_path / "cache" / "version_check.json"


@pytest.fixture
def checker(cache_file: Path) -> PyPIVersionChecker:
    """A checker whose cache lives in the test's temporary directory."""
    return PyPIVersionChecker("kilm", "1.0.0", cache_file=cache_file)


def pypi_response(version: str = "1.1.0", status_code: int = 200) -> Mock:
    """A PyPI JSON API response announcing `version`."""
    response = Mock()
    response.status_code = status_code
    response.json.return_value = {"info": {"version": version}}
    response.headers.get.return_value = "etag123"
    return response


@pytest.fixture
def pypi_get() -> Iterator[Mock]:
    """Patch the PyPI request so no test reaches the network."""
    with patch("requests.get") as mock_get:
        mock_get.return_value = pypi_response()
        yield mock_get


def test_latest_version_from_pypi(checker: PyPIVersionChecker, pypi_get: Mock) -> None:
    """The version comes from PyPI's JSON API with an identifying User-Agent."""
    assert checker.check_latest_version() == "1.1.0"
    assert pypi_get.call_args.args == ("https://pypi.org/pypi/kilm/json",)
    assert pypi_get.call_args.kwargs["headers"]["User-Agent"].startswith("KiLM/1.0.0 ")


def test_network_error_is_unknown(checker: PyPIVersionChecker, pypi_get: Mock) -> None:
    """A failed request means the latest version is unknown; nothing raises."""
    pypi_get.side_effect = requests.RequestException("Network error")
    assert checker.check_latest_version() is None


def test_unexpected_response_is_unknown(
    checker: PyPIVersionChecker, pypi_get: Mock
) -> None:
    """Error statuses and bodies without a version are not versions."""
    pypi_get.return_value = pypi_response(status_code=503)
    assert checker.check_latest_version() is None
    pypi_get.return_value.status_code = 200
    pypi_get.return_value.json.return_value = {"info": None}
    assert checker.check_latest_version() is None
    for body in ([], None):
        pypi_get.return_value.json.return_value = body
        assert checker.check_latest_version() is None


def test_fresh_cache_answers_without_network(
    checker: PyPIVersionChecker, pypi_get: Mock
) -> None:
    """Within a day of the last check the cached version is the answer."""
    checker.check_latest_version()
    pypi_get.reset_mock()

    assert checker.check_latest_version() == "1.1.0"
    pypi_get.assert_not_called()


def test_bypassing_the_cache_queries_pypi(
    checker: PyPIVersionChecker, pypi_get: Mock
) -> None:
    """use_cache=False asks PyPI even when the cache is fresh."""
    checker.check_latest_version()
    pypi_get.return_value = pypi_response("1.2.0")

    assert checker.check_latest_version(use_cache=False) == "1.2.0"
    assert checker.check_latest_version() == "1.2.0"


def test_stale_cache_is_revalidated_with_its_etag(
    checker: PyPIVersionChecker, cache_file: Path, pypi_get: Mock
) -> None:
    """After a day PyPI is asked again; a 304 keeps and renews the answer."""
    stale = time.time() - CACHE_TTL_SECONDS - 1
    cache_file.parent.mkdir()
    cache_file.write_text(
        json.dumps({"version": "1.0.5", "etag": "etag123", "timestamp": stale}),
        encoding="utf-8",
    )
    pypi_get.return_value = pypi_response(status_code=304)

    assert checker.check_latest_version() == "1.0.5"
    assert pypi_get.call_args.kwargs["headers"]["If-None-Match"] == "etag123"
    pypi_get.reset_mock()
    assert checker.check_latest_version() == "1.0.5"
    pypi_get.assert_not_called()


@pytest.mark.usefixtures("pypi_get")
def test_unreadable_cache_is_ignored(
    checker: PyPIVersionChecker, cache_file: Path
) -> None:
    """A corrupt cache file is replaced by the next answer from PyPI."""
    cache_file.parent.mkdir()
    cache_file.write_text("{not json", encoding="utf-8")

    assert checker.check_latest_version() == "1.1.0"
    assert json.loads(cache_file.read_text(encoding="utf-8"))["version"] == "1.1.0"
