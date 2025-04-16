"""
Tests for template utilities and commands.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
import jinja2

from kicad_lib_manager.utils.template import (
    TEMPLATES_DIR,
    TEMPLATE_METADATA,
    TEMPLATE_CONTENT_DIR,
    HOOKS_DIR,
    POST_CREATE_HOOK,
    get_gitignore_spec,
    list_templates_in_directory,
    find_potential_variables,
    create_template_metadata,
    write_template_metadata,
    render_template_string,
    render_filename,
    find_all_templates,
    render_template_file,
    create_project_from_template,
    run_post_create_hook
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
    
    def test_create_project_template_structure(self):
        """Test creating a template structure."""
        # Create a template directory
        template_name = "test-template"
        template_dir = self.templates_dir / template_name
        template_dir.mkdir(exist_ok=True)
        
        # Create template metadata
        metadata = create_template_metadata(
            name=template_name,
            directory=template_dir,
            description="Test template",
            use_case="For testing",
            variables={
                "project_name": {
                    "description": "Project name",
                    "default": "TestProject"
                }
            }
        )
        
        # Write metadata
        write_template_metadata(template_dir, metadata)
        
        # Check that metadata was written
        metadata_file = template_dir / TEMPLATE_METADATA
        assert metadata_file.exists()
        
        # Read back metadata
        with open(metadata_file, "r") as f:
            read_metadata = yaml.safe_load(f)
        
        # Check metadata contents
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
        with open(template_file, "w") as f:
            f.write("Hello, {{ name }}!")
        
        # Render the template file
        target_dir = Path(self.temp_dir) / "target"
        target_dir.mkdir(exist_ok=True)
        
        target_file = target_dir / "test.txt"
        
        variables = {"name": "World"}
        
        success = render_template_file(
            source_file=template_file,
            target_file=target_file,
            variables=variables
        )
        
        assert success
        assert target_file.exists()
        
        # Check contents
        with open(target_file, "r") as f:
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
                    "default": "TestProject"
                },
                "directory_name": {
                    "description": "Directory name",
                    "default": "{{ project_name|lower|replace(' ', '-') }}"
                }
            }
        }
        
        # Write metadata
        with open(self.template_dir / TEMPLATE_METADATA, "w") as f:
            yaml.dump(metadata, f)
        
        # Create post-creation hook
        with open(self.hooks_dir / POST_CREATE_HOOK, "w") as f:
            f.write("""
def post_create(context):
    print(f"Project created successfully: {context['variables']['project_name']}")
""")
        
        # Create template files
        test_file = self.template_content_dir / "README.md.jinja2"
        with open(test_file, "w") as f:
            f.write("# {{ project_name }}\n\nThis is a test project.")
        
        template_file = self.template_content_dir / "{{ project_name }}.txt.jinja2"
        with open(template_file, "w") as f:
            f.write("Hello from {{ project_name }}!")
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    def test_create_project_from_template(self):
        """Test creating a project from a template."""
        project_dir = Path(self.temp_dir) / "project"
        
        variables = {
            "project_name": "MyProject",
            "directory_name": "my-project"
        }
        
        # Mock the post-creation hook to avoid runtime errors
        with patch("kicad_lib_manager.utils.template.run_post_create_hook"):
            success = create_project_from_template(
                template_dir=self.template_dir,
                project_dir=project_dir,
                variables=variables,
                dry_run=False,
                skip_hooks=False
            )
        
        assert success
        
        # Check that files were created
        assert (project_dir / "README.md").exists()
        assert (project_dir / "MyProject.txt").exists()
        
        # Check contents
        with open(project_dir / "README.md", "r") as f:
            content = f.read()
        
        assert content == "# MyProject\n\nThis is a test project."
        
        with open(project_dir / "MyProject.txt", "r") as f:
            content = f.read()
        
        assert content == "Hello from MyProject!"
    
    def test_create_project_dry_run(self):
        """Test dry run of project creation."""
        project_dir = Path(self.temp_dir) / "project_dry_run"
        
        variables = {
            "project_name": "MyProject",
            "directory_name": "my-project"
        }
        
        # Create project with dry run
        success = create_project_from_template(
            template_dir=self.template_dir,
            project_dir=project_dir,
            variables=variables,
            dry_run=True,
            skip_hooks=True
        )
        
        assert success
        
        # Check that files were NOT created
        assert not project_dir.exists()


if __name__ == "__main__":
    pytest.main() 