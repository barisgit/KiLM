"""Rich consoles for CLI output, created at the moment output is written.

A Rich ``Console`` decides its color system and terminal mode when it is
constructed. A console stored at import time therefore keeps the decision made
for whatever stdout looked like then: imported from a terminal, it keeps
writing ANSI codes after output is redirected, for example into Click's test
runner. Code that prints calls ``get_console`` instead of holding a console.
"""

from rich.console import Console


def get_console(*, stderr: bool = False) -> Console:
    """Return a console for the current stdout, or stderr when ``stderr`` is set.

    Every call builds a new console, so redirection and environment changes such
    as ``NO_COLOR`` made after import take effect. Keep the result in a local
    variable when one operation needs a single console instance, such as a live
    status display.
    """
    return Console(stderr=stderr)
