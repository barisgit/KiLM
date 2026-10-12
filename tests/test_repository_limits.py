"""Repository limits that no lint rule enforces.

- Every Python module stays within ``MAX_MODULE_LINES`` lines; split a module
  that grows past it instead of raising the limit.
- Every lint or type suppression names its rule and states a reason after
  ``--``, for example ``# noqa: S603 -- arguments are a fixed git command``.
- No module contains emoji or check-mark glyphs; CLI output uses words.
"""

import io
import re
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON_ROOTS = ("kicad_lib_manager", "tests", ".github/scripts")
MAX_MODULE_LINES = 600

SUPPRESSION = re.compile(r"\b(noqa|ty:\s*ignore|type:\s*ignore)\b")
REASONED_SUPPRESSION = re.compile(
    r"#\s*(noqa: [A-Z]+[0-9]+(, [A-Z]+[0-9]+)*|ty: ignore\[[a-z-]+(, [a-z-]+)*\])"
    r" -- \S"
)
# Miscellaneous symbols, dingbats (check and cross marks), pictographs, and
# the emoji variation selector. Arrows, bullets, and box drawing stay allowed.
PICTOGRAPH = re.compile("[\u2600-\u27bf\u2b00-\u2bff\ufe0f\U0001f000-\U0001faff]")


def python_modules() -> list[Path]:
    """All Python modules under the checked roots, sorted for stable output."""
    return sorted(
        path for root in PYTHON_ROOTS for path in (REPO_ROOT / root).rglob("*.py")
    )


def relative(path: Path) -> str:
    """The repository-relative POSIX path, identical on every OS."""
    return path.relative_to(REPO_ROOT).as_posix()


def test_modules_stay_within_line_limit() -> None:
    """No module exceeds MAX_MODULE_LINES lines."""
    oversized = {
        relative(path): count
        for path in python_modules()
        if (count := len(path.read_text(encoding="utf-8").splitlines()))
        > MAX_MODULE_LINES
    }
    assert not oversized, f"Modules over {MAX_MODULE_LINES} lines: {oversized}"


def test_suppressions_name_rule_and_reason() -> None:
    """Every noqa or ty: ignore comment names its rule and gives a reason."""
    unreasoned = []
    for path in python_modules():
        source = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type != tokenize.COMMENT or not SUPPRESSION.search(token.string):
                continue
            if not REASONED_SUPPRESSION.search(token.string):
                unreasoned.append(f"{relative(path)}:{token.start[0]}")
    assert not unreasoned, f"Suppressions without rule and reason: {unreasoned}"


def test_modules_contain_no_pictographs() -> None:
    """No module contains an emoji, check mark, or other pictograph."""
    found = [
        f"{relative(path)}:{number}"
        for path in python_modules()
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if PICTOGRAPH.search(line)
    ]
    assert not found, f"Pictographs in: {found}"
