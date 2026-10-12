"""Tests for the ``kilm template`` commands, run through the Typer app."""

import json
from pathlib import Path

import pytest
import questionary
import yaml
from typer.testing import CliRunner

from kicad_lib_manager.commands.template import template_app
from kicad_lib_manager.services.config_service import Config
from kicad_lib_manager.utils.constants import (
    TEMPLATE_CONTENT_DIR,
    TEMPLATE_METADATA,
    TEMPLATES_DIR,
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty home directory, so Config reads and writes only test data."""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home_dir)
    return home_dir


def add_library(home: Path, name: str) -> Path:
    """Configure a GitHub library called ``name`` and return its directory."""
    library = home / name
    (library / TEMPLATES_DIR).mkdir(parents=True)
    Config().add_library(name, str(library), "github")
    return library


def add_template(
    library: Path,
    name: str,
    files: dict[str, str],
    variables: dict[str, dict[str, str]] | None = None,
    description: str = "",
) -> Path:
    """Write a template with the given content files into ``library``."""
    template_dir = library / TEMPLATES_DIR / name
    content_dir = template_dir / TEMPLATE_CONTENT_DIR
    content_dir.mkdir(parents=True)
    metadata = {
        "name": name,
        "description": description,
        "variables": variables or {},
    }
    (template_dir / TEMPLATE_METADATA).write_text(yaml.safe_dump(metadata))
    for relative, content in files.items():
        (content_dir / relative).write_text(content)
    return template_dir


def invoke(*args: str, user_input: str | None = None) -> str:
    """Run ``kilm template`` with ``args``, require success, and return the output."""
    result = CliRunner().invoke(template_app, list(args), input=user_input)
    assert result.exit_code == 0, result.output
    return result.output


def test_list_json_is_valid_json_for_long_values(home: Path) -> None:
    """Long values are not wrapped into the JSON output."""
    library = add_library(home, "lib")
    add_template(library, "board", {}, description="x" * 150)

    templates = json.loads(invoke("list", "--json"))

    assert templates["board"]["description"] == "x" * 150


def test_create_uses_template_from_requested_library(
    home: Path, tmp_path: Path
) -> None:
    """--library selects that library's template when names clash."""
    for library_name in ("first", "second"):
        add_template(
            add_library(home, library_name),
            "board",
            {"origin.txt.jinja2": library_name},
            variables={"directory_name": {"description": "", "default": ""}},
        )

    invoke(
        "create",
        "Widget",
        str(tmp_path),
        "--template",
        "board",
        "--library",
        "second",
        "--set-var",
        "directory_name=widget",
    )

    assert (tmp_path / "widget" / "origin.txt").read_text() == "second"


def test_list_filters_library_before_resolving_name_clashes(home: Path) -> None:
    """--library lists that library's template even when an earlier one shares its name."""
    for library_name in ("first", "second"):
        add_template(add_library(home, library_name), "board", {}, description=library_name)

    templates = json.loads(invoke("list", "--library", "second", "--json"))

    assert templates["board"]["description"] == "second"
