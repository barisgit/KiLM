"""
Banner utilities for KiCad Library Manager
"""

from typing import Literal

from rich.console import Console


def show_banner(
    console: Console, justify: Literal["center", "left", "right"] = "center"
) -> None:
    """
    Display the KiLM banner with colorful ASCII art.

    Front characters (KILM text) and back characters (box drawing) use different colors
    to create a layered visual effect.

    Args:
        console: Rich console instance to print the banner to
    """
    banner_lines = [
        "██╗  ██╗██╗██╗     ███╗   ███╗",
        "██║ ██╔╝██║██║     ████╗ ████║",
        "█████╔╝ ██║██║     ██╔████╔██║",
        "██╔═██╗ ██║██║     ██║╚██╔╝██║",
        "██║  ██╗██║███████╗██║ ╚═╝ ██║",
        "╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝",
    ]

    # Colors for front characters (KILM text) - gradient effect
    front_colors = [
        "bright_blue",
        "bright_blue",
        "bright_cyan",
        "bright_cyan",
        "bright_green",
        "bright_white",
    ]

    # Colors for back characters (box drawing) - darker, more subtle
    back_colors = [
        "white",
        "white",
        "white",
        "white",
        "white",
        "white",
    ]

    # Print each line with different colors for front and back characters
    for line, front_color, back_color in zip(banner_lines, front_colors, back_colors):
        # Split the line into front characters (KILM) and back characters (box drawing)
        # The KILM text is represented by the block characters ██╗, ██║, etc.
        # The back characters are the decorative box drawing elements

        # Only the solid block characters ██ are front characters
        # All other characters (╗╔╝║═╚ and spaces) are back characters
        colored_line = ""
        for char in line:
            if char == "█":
                # Only the solid block character is the front character
                colored_line += f"[bold {front_color}]{char}[/]"
            else:
                # All other characters are back characters
                colored_line += f"[{back_color}]{char}[/]"

        console.print(colored_line, justify=justify)
