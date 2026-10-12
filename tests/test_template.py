"""Tests for template utilities and commands."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from kicad_lib_manager.utils.template import (
    HOOKS_DIR,
    POST_CREATE_HOOK,
    TEMPLATE_CONTENT_DIR,
    TEMPLATE_METADATA,
    TEMPLATES_DIR,
    create_project_from_template,
    create_template_metadata,
    create_template_structure,
    find_all_templates,
    find_potential_variables,
    render_filename,
    render_filename_custom,
    render_template_file,
    render_template_string,
    write_template_metadata,
)


class TestTemplateUtils:
    """Tests for template utility functions."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.templates_dir = Path(self.temp_dir) / TEMPLATES_DIR
        self.templates_dir.mkdir(exist_ok=True)

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_render_template_string(self):
        """Test rendering a template string."""
        template_str = "Hello, {{ name }}!"
        variables = {"name": "World"}
        result = render_template_string(template_str, variables)
        assert result == "Hello, World!"

    def test_render_filename(self):
        """Test rendering a filename with variables."""
        filename = "{{ project_name }}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename(filename, variables)
        assert result == "MyProject.kicad_pro"

    def test_render_filename_no_variables(self):
        """Test rendering a filename with no variables."""
        filename = "project.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename(filename, variables)
        assert result == "project.kicad_pro"

    def test_render_filename_custom_basic(self):
        """Test basic custom filename rendering."""
        filename = "%{project_name}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename_custom(filename, variables)
        assert result == "MyProject.kicad_pro"

    def test_render_filename_custom_lower(self):
        """Test custom filename rendering with lower transformation."""
        filename = "%{project_name.lower}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename_custom(filename, variables)
        assert result == "myproject.kicad_pro"

    def test_render_filename_custom_upper(self):
        """Test custom filename rendering with upper transformation."""
        filename = "%{project_name.upper}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename_custom(filename, variables)
        assert result == "MYPROJECT.kicad_pro"

    def test_render_filename_custom_replace(self):
        """Test custom filename rendering with replace transformation."""
        filename = "%{project_name.replace(' ', '-')}.kicad_pro"
        variables = {"project_name": "My Project"}
        result = render_filename_custom(filename, variables)
        assert result == "My-Project.kicad_pro"

    def test_render_filename_custom_chained(self):
        """Test custom filename rendering with chained transformations."""
        filename = "%{project_name.replace(' ', '-').lower}.kicad_pro"
        variables = {"project_name": "My Project"}
        result = render_filename_custom(filename, variables)
        assert result == "my-project.kicad_pro"

    def test_render_filename_custom_replace_quotes(self):
        """Test custom filename rendering with quoted replace arguments."""
        filename = "%{project_name.replace(' ', '_')}.kicad_pro"
        variables = {"project_name": "My Project"}
        result = render_filename_custom(filename, variables)
        assert result == "My_Project.kicad_pro"

    def test_render_filename_custom_missing_variable(self):
        """Test custom filename rendering with missing variable."""
        filename = "%{missing_var}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename_custom(filename, variables)
        # Should return original when variable is missing
        assert result == "%{missing_var}.kicad_pro"

    def test_render_filename_fallback_to_jinja(self):
        """Test that render_filename falls back to Jinja2 for backward compatibility."""
        filename = "{{ project_name }}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename(filename, variables)
        assert result == "MyProject.kicad_pro"

    def test_render_filename_custom_priority(self):
        """Test that custom syntax takes priority over Jinja2."""
        filename = "%{project_name}.kicad_pro"
        variables = {"project_name": "MyProject"}
        result = render_filename(filename, variables)
        assert result == "MyProject.kicad_pro"

    def test_create_project_template_structure(self):
        """Test creating a template structure."""
        # Create a template directory
        template_name = "test-template"
        template_dir = self.templates_dir / template_name
        template_dir.mkdir(exist_ok=True)

        # Create template metadata
        metadata = create_template_metadata(
            name=template_name,
            description="Test template",
            use_case="For testing",
            variables={
                "project_name": {
                    "description": "Project name",
                    "default": "TestProject",
                }
            },
        )

        # Write metadata
        write_template_metadata(template_dir, metadata)

        # Check that metadata was written
        metadata_file = template_dir / TEMPLATE_METADATA
        assert metadata_file.exists()

        # Read back metadata
        with Path(metadata_file).open() as f:
            read_metadata = yaml.safe_load(f)

        # Check metadata contents
        assert read_metadata is not None
        assert read_metadata["name"] == template_name
        assert read_metadata["description"] == "Test template"
        assert read_metadata["use_case"] == "For testing"
        assert "project_name" in read_metadata["variables"]

    def test_render_template_file(self):
        """Test rendering a template file."""
        # Create a template file
        template_dir = Path(self.temp_dir) / "template_files"
        template_dir.mkdir(exist_ok=True)

        template_file = template_dir / "test.txt.jinja2"
        with Path(template_file).open("w") as f:
            f.write("Hello, {{ name }}!")

        # Render the template file
        target_dir = Path(self.temp_dir) / "target"
        target_dir.mkdir(exist_ok=True)

        target_file = target_dir / "test.txt"

        variables = {"name": "World"}

        success = render_template_file(
            source_file=template_file, target_file=target_file, variables=variables
        )

        assert success
        assert target_file.exists()

        # Check contents
        with Path(target_file).open() as f:
            content = f.read()

        assert content == "Hello, World!"


class TestTemplateCreation:
    """Tests for template creation functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.template_dir = Path(self.temp_dir) / "template"
        self.template_content_dir = self.template_dir / TEMPLATE_CONTENT_DIR
        self.hooks_dir = self.template_dir / HOOKS_DIR

        # Create template structure
        self.template_dir.mkdir(exist_ok=True)
        self.template_content_dir.mkdir(exist_ok=True)
        self.hooks_dir.mkdir(exist_ok=True)

        # Create metadata
        metadata = {
            "name": "test-template",
            "description": "Test template",
            "use_case": "For testing",
            "variables": {
                "project_name": {
                    "description": "Project name",
                    "default": "TestProject",
                },
                "directory_name": {
                    "description": "Directory name",
                    "default": "{{ project_name.lower.replace(' ', '-') }}",
                },
            },
        }

        # Write metadata
        with Path(self.template_dir / TEMPLATE_METADATA).open("w") as f:
            yaml.dump(metadata, f)

        # Create post-creation hook
        with Path(self.hooks_dir / POST_CREATE_HOOK).open("w") as f:
            f.write("""
def post_create(context):
    print(f"Project created successfully: {context['variables']['project_name']}")
""")

        # Create template files
        test_file = self.template_content_dir / "README.md.jinja2"
        with Path(test_file).open("w") as f:
            f.write("# {{ project_name }}\n\nThis is a test project.")

        template_file = self.template_content_dir / "{{ project_name }}.txt.jinja2"
        with Path(template_file).open("w") as f:
            f.write("Hello from {{ project_name }}!")

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_create_project_from_template(self):
        """Test creating a project from a template."""
        project_dir = Path(self.temp_dir) / "project"

        variables = {"project_name": "MyProject", "directory_name": "my-project"}

        # Mock the post-creation hook to avoid runtime errors
        with patch("kicad_lib_manager.utils.template.run_post_create_hook"):
            success = create_project_from_template(
                template_dir=self.template_dir,
                project_dir=project_dir,
                variables=variables,
                dry_run=False,
                skip_hooks=False,
            )

        assert success

        # Check that files were created
        assert (project_dir / "README.md").exists()
        assert (project_dir / "MyProject.txt").exists()

        # Check contents
        with Path(project_dir / "README.md").open() as f:
            content = f.read()

        assert content == "# MyProject\n\nThis is a test project."

        with Path(project_dir / "MyProject.txt").open() as f:
            content = f.read()

        assert content == "Hello from MyProject!"

    def test_create_project_dry_run(self):
        """Test dry run of project creation."""
        project_dir = Path(self.temp_dir) / "project_dry_run"

        variables = {"project_name": "MyProject", "directory_name": "my-project"}

        # Create project with dry run
        success = create_project_from_template(
            template_dir=self.template_dir,
            project_dir=project_dir,
            variables=variables,
            dry_run=True,
            skip_hooks=True,
        )

        assert success

        # Check that files were NOT created
        assert not project_dir.exists()


class _LibraryConfig:
    """Config stand-in exposing only the libraries find_all_templates reads."""

    def __init__(self, libraries: list[dict[str, str]]) -> None:
        self._libraries = libraries

    def get_libraries(self) -> list[dict[str, str]]:
        return self._libraries


def test_find_all_templates_keeps_first_duplicate(tmp_path: Path) -> None:
    """The first configured library wins a template name clash."""
    libraries = []
    for library_name in ("first", "second"):
        template_dir = tmp_path / library_name / TEMPLATES_DIR / "board"
        template_dir.mkdir(parents=True)
        write_template_metadata(
            template_dir, create_template_metadata("board", description=library_name)
        )
        libraries.append({"name": library_name, "path": str(tmp_path / library_name)})

    templates = find_all_templates(_LibraryConfig(libraries))

    board = templates["board"]
    assert board["description"] == "first"
    assert board["source_library"] == "first"
    assert board["library_path"] == str(tmp_path / "first")


def test_main_kicad_files_are_named_after_the_new_project(tmp_path: Path) -> None:
    """The main project, schematic, and PCB take the project_filename variable."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "Board.kicad_pro").write_text('{"meta": {"filename": "Board.kicad_pro"}}')
    (source / "Board.kicad_sch").write_text('(kicad_sch (project "Board"))')
    (source / "Board.kicad_pcb").write_text('(kicad_pcb (sheetfile "Board.kicad_sch"))')
    template_dir = tmp_path / "template"
    create_template_structure(source, template_dir, create_template_metadata("tpl"))
    project = tmp_path / "project"

    create_project_from_template(
        template_dir,
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
    assert '(project "Widget")' in (project / "Widget.kicad_sch").read_text()
    assert '(sheetfile "Widget.kicad_sch")' in (project / "Widget.kicad_pcb").read_text()

def test_rendered_files_keep_markup_characters(tmp_path: Path) -> None:
    """Variables are inserted verbatim, not HTML-escaped."""
    source = tmp_path / "title.txt.jinja2"
    source.write_text("{{ project_name }}")
    target = tmp_path / "title.txt"

    render_template_file(source, target, {"project_name": "R&D <1>"})

    assert target.read_text() == "R&D <1>"

def test_variable_scan_skips_directories_make_does_not_copy(tmp_path: Path) -> None:
    """Dependencies and VCS data do not contribute variable suggestions."""
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text('author = "Someone"')
    (tmp_path / "notes.txt").write_text('author = "Jane"')

    assert find_potential_variables(tmp_path) == {"jane": ["Jane"]}

if __name__ == "__main__":
    pytest.main()
