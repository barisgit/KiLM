import pytest
from typer.testing import CliRunner

from kicad_lib_manager.main import app

LEAF_COMMANDS = [
    "status",
    "list",
    "init",
    "pin",
    "unpin",
    "setup",
    "sync",
    "add-3d",
    "add-hook",
    "import",
]


@pytest.mark.parametrize("command", LEAF_COMMANDS)
def test_leaf_command_usage_has_no_subcommand_placeholder(command):
    result = CliRunner().invoke(app, [command, "--help"])
    usage = next(line for line in result.output.splitlines() if "Usage:" in line)
    assert "COMMAND" not in usage
    assert "[ARGS]" not in usage


def test_group_usage_keeps_subcommand_placeholder():
    result = CliRunner().invoke(app, ["template", "--help"])
    usage = next(line for line in result.output.splitlines() if "Usage:" in line)
    assert "COMMAND [ARGS]..." in usage
