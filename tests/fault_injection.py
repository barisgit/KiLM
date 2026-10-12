"""Fault injection for tests of writers that must not lose data."""

import errno
import io
from collections.abc import Callable
from typing import ParamSpec, TypeVar

import pytest

_P = ParamSpec("_P")
_T = TypeVar("_T")


def fail_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every file opened for writing fail right after it is opened.

    Opening with ``w`` truncates the file first, so a writer that rewrites its
    target in place loses the content, while an atomic writer loses only its
    temporary file. The failure reads "No space left on device".
    """
    monkeypatch.setattr(io, "open", _failing_after_open(io.open))


def _failing_after_open(real_open: Callable[_P, _T]) -> Callable[_P, _T]:
    """Wrap ``real_open`` so that files opened for writing raise ENOSPC."""

    def failing_open(*args: _P.args, **kwargs: _P.kwargs) -> _T:
        handle = real_open(*args, **kwargs)
        if isinstance(handle, (io.TextIOWrapper, io.BufferedWriter)) and (
            "w" in handle.mode
        ):
            handle.close()
            raise OSError(errno.ENOSPC, "No space left on device")
        return handle

    return failing_open
