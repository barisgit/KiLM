#!/usr/bin/env python3
"""
Command-line interface for KiCad Library Manager
"""

import click

from . import __version__
from .commands.setup import setup
from .commands.list_libraries import list_cmd
from .commands.status import status
from .commands.pin import pin
from .commands.unpin import unpin
from .commands.init import init
from .commands.add_3d import add_3d
from .commands.config_list import config_list


@click.group()
@click.version_option(version=__version__)
def main():
    """KiCad Library Manager - Manage KiCad libraries

    This tool helps configure and manage KiCad libraries across your projects.
    """
    pass


# Register commands
main.add_command(setup)
main.add_command(list_cmd, name="list")  # Use list_cmd function but keep command name as "list"
main.add_command(status)
main.add_command(pin)
main.add_command(unpin)
main.add_command(init)
main.add_command(add_3d)
main.add_command(config_list, name="config")


if __name__ == "__main__":
    main()