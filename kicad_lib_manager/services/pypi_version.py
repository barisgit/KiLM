"""Latest-release lookup on PyPI, cached on disk for a day."""

# PEP 810: on Python 3.15+ these imports load on first use.
__lazy_modules__ = {"requests"}

import json
import time
from dataclasses import asdict, dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Final

import requests

from kicad_lib_manager.services.user_paths import user_cache_dir

CACHE_TTL_SECONDS: Final = 24 * 60 * 60
"""How long a cached answer is returned without asking PyPI."""

REQUEST_TIMEOUT_SECONDS: Final = 10
"""How long a PyPI request may take before the check gives up."""


VERSION_CHECK_FILE: Final = "version_check.json"
"""Cache file, in the user cache directory, holding the last PyPI answer."""


@dataclass(frozen=True)
class CachedVersion:
    """The last answer from PyPI and the ETag that identifies it."""

    version: str
    etag: str | None
    timestamp: float

    @staticmethod
    def from_json(data: object) -> "CachedVersion | None":
        """Parse a cache file's content; None when it is not a cache entry."""
        if not isinstance(data, dict):
            return None
        version = data.get("version")
        etag = data.get("etag")
        timestamp = data.get("timestamp")
        if not isinstance(version, str) or not isinstance(timestamp, int | float):
            return None
        etag = etag if isinstance(etag, str) else None
        return CachedVersion(version, etag, float(timestamp))

    def is_fresh(self) -> bool:
        """Return whether the entry is young enough to answer without PyPI."""
        return time.time() - self.timestamp < CACHE_TTL_SECONDS


class PyPIVersionChecker:
    """PyPI client for the latest release of a package, cached for a day.

    A cached answer younger than `CACHE_TTL_SECONDS` is returned without a
    request. Otherwise PyPI is asked with the cached ETag, so an unchanged
    release costs a 304 answer.
    """

    def __init__(
        self,
        package_name: str,
        version: str = "unknown",
        *,
        cache_file: Path | None = None,
    ) -> None:
        """Prepare a checker; nothing is read or requested yet.

        Args:
            package_name: The PyPI project to look up.
            version: The running version, sent in the User-Agent.
            cache_file: Where answers are cached; defaults to the user cache.
        """
        self.base_url = f"https://pypi.org/pypi/{package_name}/json"
        self.cache_file = cache_file or user_cache_dir() / VERSION_CHECK_FILE
        self.user_agent = f"KiLM/{version} (+https://github.com/barisgit/KiLM)"

    def check_latest_version(self, *, use_cache: bool = True) -> str | None:
        """Return the latest released version, or None when it is unknown.

        With `use_cache` a fresh cached answer is returned without a request.
        Network and response errors return None, even when an older answer
        is cached, and never raise, so an offline machine only loses the
        update notice.
        """
        cached = self._load_cache()
        if use_cache and cached is not None and cached.is_fresh():
            return cached.version

        headers = {"User-Agent": self.user_agent}
        if cached is not None and cached.etag is not None:
            headers["If-None-Match"] = cached.etag
        try:
            response = requests.get(
                self.base_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            answer = self._read_response(response, cached)
        except (requests.RequestException, ValueError):
            return None
        if answer is None:
            return None
        self._save_cache(answer)
        return answer.version

    @staticmethod
    def _read_response(
        response: requests.Response, cached: CachedVersion | None
    ) -> CachedVersion | None:
        """Turn a PyPI answer into a cache entry; None when it holds no version.

        Raises:
            ValueError: The body is not JSON.
        """
        if response.status_code == HTTPStatus.NOT_MODIFIED:
            if cached is None:
                return None
            return CachedVersion(cached.version, cached.etag, time.time())
        if response.status_code != HTTPStatus.OK:
            return None
        body = response.json()
        info = body.get("info") if isinstance(body, dict) else None
        version = info.get("version") if isinstance(info, dict) else None
        if not isinstance(version, str):
            return None
        return CachedVersion(version, response.headers.get("ETag"), time.time())

    def _load_cache(self) -> CachedVersion | None:
        """Return the cache entry of any age; None when absent or unreadable."""
        try:
            with self.cache_file.open(encoding="utf-8") as f:
                return CachedVersion.from_json(json.load(f))
        except (OSError, ValueError):
            return None

    def _save_cache(self, entry: CachedVersion) -> None:
        """Write the cache entry; a cache that cannot be written is skipped."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.cache_file.write_text(json.dumps(asdict(entry)), encoding="utf-8")
        except OSError:
            return
