"""The KiLM ASCII-art banner."""

from typing import Literal

from rich.console import Console

_BANNER_LINES = (
    "██╗  ██╗██╗██╗     ███╗   ███╗",
    "██║ ██╔╝██║██║     ████╗ ████║",
    "█████╔╝ ██║██║     ██╔████╔██║",
    "██╔═██╗ ██║██║     ██║╚██╔╝██║",
    "██║  ██╗██║███████╗██║ ╚═╝ ██║",
    "╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝",
)
# One color per line for the solid blocks that form the letters, a gradient.
_LETTER_COLORS = (
    "bright_blue",
    "bright_blue",
    "bright_cyan",
    "bright_cyan",
    "bright_green",
    "bright_white",
)
# Color of the box-drawing shadow around the letters.
_SHADOW_COLOR = "white"
_LETTER_CHAR = "█"


def show_banner(
    console: Console, justify: Literal["center", "left", "right"] = "center"
) -> None:
    """Print the KiLM banner, with the letters and their shadow in different colors.

    Args:
        console: Rich console to print the banner to.
        justify: Horizontal alignment of the banner.
    """
    for line, letter_color in zip(_BANNER_LINES, _LETTER_COLORS, strict=True):
        colored_line = "".join(
            f"[bold {letter_color}]{char}[/]"
            if char == _LETTER_CHAR
            else f"[{_SHADOW_COLOR}]{char}[/]"
            for char in line
        )
        console.print(colored_line, justify=justify)
