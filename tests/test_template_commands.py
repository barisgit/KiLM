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


def test_list_json_keeps_custom_metadata(home: Path) -> None:
    """Keys KiLM does not know, YAML dates included, appear in the JSON."""
    template_dir = add_template(add_library(home, "lib"), "board", {})
    with (template_dir / TEMPLATE_METADATA).open("a", encoding="utf-8") as f:
        f.write("released: 2026-01-02\nhook_options:\n  greeting: Hi\n")

    templates = json.loads(invoke("list", "--json"))

    assert templates["board"]["hook_options"] == {"greeting": "Hi"}
    assert templates["board"]["released"] == "2026-01-02"


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
    """--library lists its template even when an earlier library shares the name."""
    for library_name in ("first", "second"):
        add_template(
            add_library(home, library_name), "board", {}, description=library_name
        )

    templates = json.loads(invoke("list", "--library", "second", "--json"))

    assert templates["board"]["description"] == "second"


def test_create_renders_percent_syntax_defaults(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defaults written in the %{...} syntax are rendered before they are offered."""
    offered: dict[str, str] = {}

    class AcceptDefault:
        def __init__(self, message: str, default: str) -> None:
            self.answer = default
            offered[message.split(maxsplit=1)[0]] = default

        def ask(self) -> str:
            return self.answer

    monkeypatch.setattr(questionary, "text", AcceptDefault)
    add_template(
        add_library(home, "lib"),
        "board",
        {"%{project_filename}.txt.jinja2": "{{ directory_name }}"},
        variables={
            "project_name": {"description": "Name", "default": ""},
            "directory_name": {
                "description": "Directory",
                "default": "%{project_name.lower.replace(' ', '-')}",
            },
            "project_filename": {"description": "File", "default": "%{project_name}"},
        },
    )

    invoke("create", "My Board", str(tmp_path), "--template", "board")

    assert offered == {"directory_name": "my-board", "project_filename": "My Board"}
    assert (tmp_path / "my-board" / "My Board.txt").read_text() == "my-board"


def test_make_keeps_description_when_detected_variable_is_described(
    home: Path, tmp_path: Path
) -> None:
    """Describing a detected variable does not replace the template description."""
    add_library(home, "lib")
    source = tmp_path / "source"
    source.mkdir()
    (source / "notes.txt").write_text('author = "Jane"')
    output = tmp_path / "out"

    invoke(
        "make",
        "board",
        str(source),
        "--description",
        "Board template",
        "--use-case",
        "Boards",
        "--output-directory",
        str(output),
        user_input="y\nAuthor name\nn\n",
    )

    metadata = yaml.safe_load((output / TEMPLATE_METADATA).read_text())
    assert metadata["description"] == "Board template"
    assert metadata["variables"]["jane"]["description"] == "Author name"


def test_make_dry_run_lists_only_files_that_make_copies(
    home: Path, tmp_path: Path
) -> None:
    """The preview excludes what make itself excludes."""
    add_library(home, "lib")
    source = tmp_path / "source"
    (source / ".git").mkdir(parents=True)
    (source / ".git" / "HEAD").write_text("ref")
    (source / "board.kicad_prl").write_text("{}")
    (source / "notes.txt").write_text("notes")

    output = invoke(
        "make",
        "board",
        str(source),
        "--non-interactive",
        "--dry-run",
        "--output-directory",
        str(tmp_path / "out"),
    )

    included = [line.strip() for line in output.splitlines() if "+ " in line]
    assert included == ["+ notes.txt"]


@pytest.mark.parametrize("library_args", [[], ["--library", "lib"]])
def test_list_without_templates_suggests_existing_commands(
    home: Path, library_args: list[str]
) -> None:
    """The hints for an empty listing name commands that exist."""
    add_library(home, "lib")

    output = invoke("list", *library_args)

    assert "kilm list-libraries" not in output
    assert "kilm config list" in output
