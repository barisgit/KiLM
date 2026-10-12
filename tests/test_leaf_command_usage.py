"""Usage-line contract for the registered top-level commands (issue #13).

A Typer sub-app registered with ``add_typer`` always becomes a click group, so a
leaf command registered that way renders ``COMMAND [ARGS]...`` in its usage line
although it has no subcommands. Leaf commands must use ``app.command``; only real
groups use ``add_typer``. The cases are derived from the app, so a new command
registered the wrong way fails here without editing this file.
"""

from collections.abc import Mapping

import click
import pytest
import typer
from typer.testing import CliRunner

from kicad_lib_manager.main import app

SUBCOMMAND_PLACEHOLDER = "COMMAND [ARGS]..."


def _registered_commands() -> Mapping[str, click.Command]:
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    return root.commands


COMMANDS = _registered_commands()
GROUPS = sorted(name for name, cmd in COMMANDS.items() if isinstance(cmd, click.Group))
LEAVES = sorted(name for name in COMMANDS if name not in GROUPS)


def _usage_line(command: str) -> str:
    result = CliRunner().invoke(app, [command, "--help"])
    assert result.exit_code == 0, result.output
    return next(line for line in result.output.splitlines() if "Usage:" in line)


@pytest.mark.parametrize("command", LEAVES)
def test_leaf_command_usage_has_no_subcommand_placeholder(command: str) -> None:
    usage = _usage_line(command)
    assert "COMMAND" not in usage
    assert "[ARGS]" not in usage


@pytest.mark.parametrize("command", GROUPS)
def test_group_has_subcommands_and_keeps_placeholder(command: str) -> None:
    group = COMMANDS[command]
    assert isinstance(group, click.Group)
    assert group.commands, f"{command} is a group without subcommands; use app.command"
    assert SUBCOMMAND_PLACEHOLDER in _usage_line(command)
