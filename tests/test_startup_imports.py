"""Startup cost: heavy dependencies load on first use, not at import."""

import subprocess
import sys

import pytest

# Each is listed in __lazy_modules__ by the modules that import it.
LAZY_MODULES = (
    "jinja2",
    "packaging.version",
    "pathspec",
    "questionary",
    "requests",
    "yaml",
)


@pytest.mark.skipif(
    sys.version_info < (3, 15), reason="__lazy_modules__ (PEP 810) needs Python 3.15"
)
def test_importing_the_cli_loads_no_heavy_dependency() -> None:
    """A module-level use of a lazy import would load it for every command."""
    code = (
        "import sys, kicad_lib_manager.main\n"
        f"print(*[m for m in {LAZY_MODULES!r} if m in sys.modules])"
    )
    result = subprocess.run(  # noqa: S603 -- runs this interpreter on a fixed snippet
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert result.stdout.split() == []
