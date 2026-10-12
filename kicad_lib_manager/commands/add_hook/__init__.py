"""The ``add-hook`` command: install a git post-merge hook that runs ``kilm sync``."""

from kicad_lib_manager.commands.add_hook.command import add_hook

__all__ = ["add_hook"]
