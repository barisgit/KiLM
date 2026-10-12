"""Tests for the template utilities."""

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from kicad_lib_manager.utils.constants import (
    HOOKS_DIR,
    TEMPLATE_CONTENT_DIR,
    TEMPLATE_METADATA,
    TEMPLATES_DIR,
)
from kicad_lib_manager.utils.template.authoring import (
    create_template_metadata,
    create_template_structure,
)
from kicad_lib_manager.utils.template.constants import POST_CREATE_HOOK
from kicad_lib_manager.utils.template.discovery import (
    ConfiguredLibrary,
    find_all_templates,
    list_templates_in_directory,
)
from kicad_lib_manager.utils.template.hooks import (
    create_hook_script,
    run_post_create_hook,
)
from kicad_lib_manager.utils.template.models import (
    DiscoveredTemplate,
    TemplateMetadata,
    discovered_template,
    read_template_metadata,
    write_template_metadata,
)
from kicad_lib_manager.utils.template.project import create_project_from_template
from kicad_lib_manager.utils.template.rendering import (
    render_filename,
    render_filename_custom,
    render_template_file,
    render_template_string,
)
from kicad_lib_manager.utils.template.selection import find_potential_variables

PROJECT = {"project_name": "MyProject"}
SPACED_PROJECT = {"project_name": "My Project"}


def test_render_template_string() -> None:
    """Jinja2 placeholders are filled from the variables."""
    assert render_template_string("Hello, {{ name }}!", {"name": "World"}) == (
        "Hello, World!"
    )


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("{{ project_name }}.kicad_pro", "MyProject.kicad_pro"),
        ("%{project_name}.kicad_pro", "MyProject.kicad_pro"),
        ("project.kicad_pro", "project.kicad_pro"),
    ],
)
def test_render_filename(filename: str, expected: str) -> None:
    """Both placeholder syntaxes render; plain names stay unchanged."""
    assert render_filename(filename, PROJECT) == expected


@pytest.mark.parametrize(
    ("filename", "variables", "expected"),
    [
        ("%{project_name}.kicad_pro", PROJECT, "MyProject.kicad_pro"),
        ("%{project_name.lower}.kicad_pro", PROJECT, "myproject.kicad_pro"),
        ("%{project_name.upper}.kicad_pro", PROJECT, "MYPROJECT.kicad_pro"),
        (
            "%{project_name.replace(' ', '-')}.kicad_pro",
            SPACED_PROJECT,
            "My-Project.kicad_pro",
        ),
        (
            "%{project_name.replace(' ', '_')}.kicad_pro",
            SPACED_PROJECT,
            "My_Project.kicad_pro",
        ),
        (
            "%{project_name.replace(' ', '-').lower}.kicad_pro",
            SPACED_PROJECT,
            "my-project.kicad_pro",
        ),
        ("%{missing_var}.kicad_pro", PROJECT, "%{missing_var}.kicad_pro"),
    ],
)
def test_render_filename_custom(
    filename: str, variables: dict[str, str], expected: str
) -> None:
    """Transformations apply in order; unknown variables stay as written."""
    assert render_filename_custom(filename, variables) == expected


def test_template_metadata_round_trip(tmp_path: Path) -> None:
    """Written metadata reads back with the predefined variables added."""
    metadata = create_template_metadata(
        name="test-template",
        description="Test template",
        use_case="For testing",
        variables={"author": {"description": "Author", "default": "Jane"}},
    )
    write_template_metadata(tmp_path, metadata)

    read_back = read_template_metadata(tmp_path)

    assert read_back == metadata
    assert list(metadata.get("variables", {})) == [
        "author",
        "project_name",
        "directory_name",
        "project_filename",
    ]


def test_render_template_file(tmp_path: Path) -> None:
    """A template file renders into its target."""
    source = tmp_path / "test.txt.jinja2"
    source.write_text("Hello, {{ name }}!", encoding="utf-8")
    target = tmp_path / "target" / "test.txt"

    assert render_template_file(source, target, {"name": "World"})
    assert target.read_text(encoding="utf-8") == "Hello, World!"


def test_rendered_files_keep_markup_characters(tmp_path: Path) -> None:
    """Variables are inserted verbatim, not HTML-escaped."""
    source = tmp_path / "title.txt.jinja2"
    source.write_text("{{ project_name }}", encoding="utf-8")
    target = tmp_path / "title.txt"

    render_template_file(source, target, {"project_name": "R&D <1>"})

    assert target.read_text(encoding="utf-8") == "R&D <1>"


def _discovered(template_dir: Path, metadata: TemplateMetadata) -> DiscoveredTemplate:
    return discovered_template(metadata, template_dir, template_dir.parent)


@pytest.fixture
def template(tmp_path: Path) -> DiscoveredTemplate:
    """A template with a rendered README, a renamed file, and a recording hook."""
    template_dir = tmp_path / "template"
    content_dir = template_dir / TEMPLATE_CONTENT_DIR
    content_dir.mkdir(parents=True)
    (content_dir / "README.md.jinja2").write_text(
        "# {{ project_name }}\n\nThis is a test project.", encoding="utf-8"
    )
    (content_dir / "{{ project_name }}.txt.jinja2").write_text(
        "Hello from {{ project_name }}!", encoding="utf-8"
    )
    (template_dir / HOOKS_DIR).mkdir()
    (template_dir / HOOKS_DIR / POST_CREATE_HOOK).write_text(
        "from pathlib import Path\n\n\ndef post_create(context):\n"
        "    name = context['variables']['project_name']\n"
        "    Path(context['project_dir'], 'hook.txt').write_text(name)\n",
        encoding="utf-8",
    )
    return _discovered(template_dir, create_template_metadata("test-template"))


def test_create_project_from_template(
    template: DiscoveredTemplate, tmp_path: Path
) -> None:
    """Files render with the variables and the hook runs in the new project."""
    project_dir = tmp_path / "project"

    assert create_project_from_template(template, project_dir, PROJECT)

    assert sorted(path.name for path in project_dir.iterdir()) == [
        "MyProject.txt",
        "README.md",
        "hook.txt",
    ]
    readme = (project_dir / "README.md").read_text(encoding="utf-8")
    assert readme == "# MyProject\n\nThis is a test project."
    text = (project_dir / "MyProject.txt").read_text(encoding="utf-8")
    assert text == "Hello from MyProject!"
    assert (project_dir / "hook.txt").read_text(encoding="utf-8") == "MyProject"


def test_hook_reads_custom_metadata(tmp_path: Path) -> None:
    """Keys KiLM does not know reach the hook as metadata.yaml has them."""
    template_dir = tmp_path / "template"
    (template_dir / TEMPLATE_CONTENT_DIR).mkdir(parents=True)
    (template_dir / TEMPLATE_CONTENT_DIR / "README.md").write_text("", encoding="utf-8")
    (template_dir / HOOKS_DIR).mkdir()
    (template_dir / TEMPLATE_METADATA).write_text(
        "name: tpl\n"
        "hook_options:\n  greeting: Hi\n"
        "variables:\n  board:\n    default: A\n    choices: [A, B]\n",
        encoding="utf-8",
    )
    (template_dir / HOOKS_DIR / POST_CREATE_HOOK).write_text(
        "from pathlib import Path\n\n\ndef post_create(context):\n"
        "    template = context['template']\n"
        "    choices = template['variables']['board']['choices']\n"
        "    text = template['hook_options']['greeting'] + ' ' + ','.join(choices)\n"
        "    Path(context['project_dir'], 'hook.txt').write_text(text)\n",
        encoding="utf-8",
    )
    metadata = read_template_metadata(template_dir)
    assert metadata is not None
    project_dir = tmp_path / "project"

    assert create_project_from_template(
        _discovered(template_dir, metadata), project_dir, PROJECT
    )

    assert (project_dir / "hook.txt").read_text(encoding="utf-8") == "Hi A,B"


def test_hook_sees_custom_keys_as_loaded(tmp_path: Path) -> None:
    """Integer and text keys stay distinct, also inside variables and dependencies."""
    template_dir = tmp_path / TEMPLATES_DIR / "tpl"
    (template_dir / TEMPLATE_CONTENT_DIR).mkdir(parents=True)
    (template_dir / TEMPLATE_CONTENT_DIR / "README.md").write_text("", encoding="utf-8")
    (template_dir / HOOKS_DIR).mkdir()
    (template_dir / TEMPLATE_METADATA).write_text(
        "name: tpl\n7: first\n'7': second\n"
        "variables:\n  board:\n    default: A\n    7: int\n    '7': text\n"
        "dependencies:\n  recommended: []\n  7: dep\n",
        encoding="utf-8",
    )
    (template_dir / HOOKS_DIR / POST_CREATE_HOOK).write_text(
        "from pathlib import Path\n\n\ndef post_create(context):\n"
        "    t = context['template']\n"
        "    board = t['variables']['board']\n"
        "    values = [t[7], t['7'], board[7], board['7'], t['dependencies'][7]]\n"
        "    Path(context['project_dir'], 'hook.txt').write_text(' '.join(values))\n",
        encoding="utf-8",
    )
    templates = list_templates_in_directory(tmp_path)
    assert [template["name"] for template in templates] == ["tpl"]
    project_dir = tmp_path / "project"

    assert create_project_from_template(templates[0], project_dir, PROJECT)

    hook_output = (project_dir / "hook.txt").read_text(encoding="utf-8")
    assert hook_output == "first second int text dep"


def test_create_project_dry_run_writes_nothing(
    template: DiscoveredTemplate, tmp_path: Path
) -> None:
    """A dry run succeeds without creating the project directory."""
    project_dir = tmp_path / "project"

    assert create_project_from_template(template, project_dir, PROJECT, dry_run=True)
    assert not project_dir.exists()


def test_starting_hook_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The hook that template make writes loads and runs as written."""
    create_hook_script(tmp_path)

    run_post_create_hook(
        tmp_path / POST_CREATE_HOOK,
        tmp_path / "project",
        PROJECT,
        create_template_metadata("tpl"),
    )

    assert "Project MyProject created successfully!" in capsys.readouterr().out


class _LibraryConfig:
    """Config stand-in exposing only the libraries find_all_templates reads."""

    def __init__(self, libraries: list[ConfiguredLibrary]) -> None:
        self._libraries = libraries

    def get_libraries(self) -> Sequence[ConfiguredLibrary]:
        return self._libraries


def test_find_all_templates_keeps_first_duplicate(tmp_path: Path) -> None:
    """The first configured library wins a template name clash."""
    libraries: list[ConfiguredLibrary] = []
    for library_name in ("first", "second"):
        template_dir = tmp_path / library_name / TEMPLATES_DIR / "board"
        template_dir.mkdir(parents=True)
        write_template_metadata(
            template_dir, create_template_metadata("board", description=library_name)
        )
        libraries.append(
            ConfiguredLibrary(name=library_name, path=str(tmp_path / library_name))
        )

    templates = find_all_templates(_LibraryConfig(libraries))

    board = templates["board"]
    assert board.get("description") == "first"
    assert board["source_library"] == "first"
    assert board["library_path"] == str(tmp_path / "first")


def test_main_kicad_files_are_named_after_the_new_project(tmp_path: Path) -> None:
    """The main project, schematic, and PCB take the project_filename variable."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "Board.kicad_pro").write_text(
        '{"meta": {"filename": "Board.kicad_pro"}}', encoding="utf-8"
    )
    (source / "Board.kicad_sch").write_text(
        '(kicad_sch (project "Board"))', encoding="utf-8"
    )
    (source / "Board.kicad_pcb").write_text(
        '(kicad_pcb (sheetfile "Board.kicad_sch"))', encoding="utf-8"
    )
    template_dir = tmp_path / "template"
    metadata = create_template_metadata("tpl")
    create_template_structure(source, template_dir, metadata)
    project = tmp_path / "project"

    create_project_from_template(
        _discovered(template_dir, metadata),
        project,
        {"project_name": "Widget", "project_filename": "Widget"},
        skip_hooks=True,
    )

    assert sorted(path.name for path in project.iterdir()) == [
        "Widget.kicad_pcb",
        "Widget.kicad_pro",
        "Widget.kicad_sch",
    ]
    project_file = json.loads((project / "Widget.kicad_pro").read_text())
    assert project_file["meta"]["filename"] == "Widget.kicad_pro"
    schematic = (project / "Widget.kicad_sch").read_text(encoding="utf-8")
    assert '(project "Widget")' in schematic
    pcb = (project / "Widget.kicad_pcb").read_text(encoding="utf-8")
    assert '(sheetfile "Widget.kicad_sch")' in pcb


def test_variable_scan_skips_directories_make_does_not_copy(tmp_path: Path) -> None:
    """Dependencies and VCS data do not contribute variable suggestions."""
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text(
        'author = "Someone"', encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text('author = "Jane"', encoding="utf-8")

    assert find_potential_variables(tmp_path) == {"jane": ["Jane"]}


def test_variable_scan_with_no_patterns_finds_nothing(tmp_path: Path) -> None:
    """An empty pattern list means no patterns, not the default ones."""
    (tmp_path / "notes.txt").write_text('author = "Jane"', encoding="utf-8")

    assert find_potential_variables(tmp_path, patterns=[]) == {}
