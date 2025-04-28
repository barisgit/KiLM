"""
Template utility functions for KiCad Library Manager.
Provides functions for working with project templates.
"""

import os
import re
import yaml
import json
import shutil
import importlib.util
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union
import pathspec
import jinja2
import click

# Default template directory name in a library
TEMPLATES_DIR = "templates"

# Template metadata file name
TEMPLATE_METADATA = "metadata.yaml"

# Default template directory name within the template
TEMPLATE_CONTENT_DIR = "template"

# Default hooks directory
HOOKS_DIR = "hooks"

# Post-creation hook name
POST_CREATE_HOOK = "post_create.py"

# Default patterns to look for potentially variable values
DEFAULT_VARIABLE_PATTERNS = [
    # Look for project title/name in KiCad project file
    r'"title": "([^"]+)"',
    # Common project name patterns
    r'project_name\s*[=:]\s*["\']([^"\']+)["\']',
    r'projectName\s*[=:]\s*["\']([^"\']+)["\']',
    r'PROJECT_NAME\s*[=:]\s*["\']([^"\']+)["\']',
    # Look for author info
    r'author\s*[=:]\s*["\']([^"\']+)["\']',
]

# KiCad file extensions
KICAD_PROJECT_EXT = '.kicad_pro'
KICAD_SCHEMATIC_EXT = '.kicad_sch'
KICAD_PCB_EXT = '.kicad_pcb'
KICAD_PRL_EXT = '.kicad_prl'  # Project local settings file


def get_gitignore_spec(directory: Path) -> Optional[pathspec.PathSpec]:
    """
    Get a PathSpec object representing the gitignore patterns in the given directory.
    
    Args:
        directory: Path to the directory containing .gitignore
        
    Returns:
        PathSpec object or None if no .gitignore is present
    """
    gitignore_file = directory / ".gitignore"
    if not gitignore_file.exists():
        return None
    
    try:
        with open(gitignore_file, "r") as f:
            lines = f.readlines()
        
        # Add patterns to explicitly ignore common directories if not present
        common_patterns = ["__pycache__/", "*.py[cod]", "*$py.class", "*.so", "*.dylib", 
                          ".env", ".venv", "env/", "venv/", "ENV/", "node_modules/",
                          ".DS_Store"]
        
        # Add common patterns if not already in gitignore
        for pattern in common_patterns:
            if not any(pattern in line for line in lines):
                lines.append(pattern + "\n")
        
        return pathspec.PathSpec.from_lines('gitwildmatch', lines)
    except Exception as e:
        # Use click.echo for warnings/errors
        click.echo(f"Warning: Error reading .gitignore file: {e}", err=True)
        return None


def list_templates_in_directory(directory: Path) -> List[Dict[str, Any]]:
    """
    List all templates in a given directory.
    
    Args:
        directory: Path to the directory to scan for templates
        
    Returns:
        List of dictionaries containing template metadata
    """
    templates_dir = directory / TEMPLATES_DIR
    if not templates_dir.exists() or not templates_dir.is_dir():
        return []
    
    templates = []
    
    for template_dir in templates_dir.iterdir():
        if not template_dir.is_dir():
            continue
        
        metadata_file = template_dir / TEMPLATE_METADATA
        if not metadata_file.exists():
            continue
        
        try:
            with open(metadata_file, "r") as f:
                metadata = yaml.safe_load(f)
            
            if not metadata or not isinstance(metadata, dict):
                continue
            
            # Add template directory path to metadata
            metadata["path"] = str(template_dir)
            metadata["source_library"] = directory.name
            
            templates.append(metadata)
        except Exception as e:
            # Use click.echo for warnings/errors
            click.echo(f"Error reading template metadata from {metadata_file}: {e}", err=True)
    
    return templates


def find_potential_variables(directory: Path, patterns: List[str] = None) -> Dict[str, List[str]]:
    """
    Scan files in a directory for potential template variables.
    
    Args:
        directory: Path to the directory to scan
        patterns: List of regex patterns to look for, defaults to DEFAULT_VARIABLE_PATTERNS
        
    Returns:
        Dictionary mapping variable names to found values
    """
    if patterns is None:
        patterns = DEFAULT_VARIABLE_PATTERNS
    
    # Compile patterns
    compiled_patterns = [re.compile(pattern) for pattern in patterns]
    
    # Initialize results
    variables = {}
    
    # Get .gitignore spec if it exists
    gitignore_spec = get_gitignore_spec(directory)
    
    # Walk directory
    for root, _, files in os.walk(directory):
        rel_root = os.path.relpath(root, directory)
        if rel_root == ".":
            rel_root = ""
        
        for file in files:
            # Skip gitignored files - ensure proper path format
            rel_path = os.path.join(rel_root, file)
            git_path = rel_path.replace(os.sep, "/")
            if gitignore_spec and gitignore_spec.match_file(git_path):
                continue
            
            # Skip binary files and large files
            file_path = os.path.join(root, file)
            try:
                # Skip files larger than 1MB
                if os.path.getsize(file_path) > 1024 * 1024:
                    continue
                
                # Try to read as text
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # Search for patterns
                for pattern in compiled_patterns:
                    matches = pattern.findall(content)
                    for match in matches:
                        if match:
                            var_name = re.sub(r'[^a-zA-Z0-9_]', '_', match.lower())
                            if var_name not in variables:
                                variables[var_name] = []
                            if match not in variables[var_name]:
                                variables[var_name].append(match)
            except Exception:
                # Skip files that can't be read as text
                continue
    
    return variables


def create_template_metadata(
    name: str,
    directory: Path,
    description: str = None,
    use_case: str = None,
    variables: Dict[str, Dict[str, Any]] = None,
    extends: str = None,
    dependencies: List[str] = None
) -> Dict[str, Any]:
    """
    Create template metadata dictionary.
    
    Args:
        name: Template name
        directory: Template directory
        description: Template description
        use_case: Template use case
        variables: Dictionary of template variables
        extends: Parent template name
        dependencies: List of recommended dependencies
        
    Returns:
        Template metadata dictionary
    """
    # Default variables if none provided
    if not variables:
        variables = {
            "project_name": {
                "description": "Project name (used in documentation and KiCad files)",
                "default": name
            },
            "directory_name": {
                "description": "Directory/repository name (used for folder structure)",
                "default": "{{ project_name|lower|replace(' ', '-') }}"
            },
            "project_filename": {
                "description": "Main KiCad project filename (without extension)",
                "default": "{{ project_name }}"
            }
        }
    else:
        # Make sure we have the predefined variables
        if not any(k.lower() == 'project_name' for k in variables.keys()):
            variables["project_name"] = {
                "description": "Project name (used in documentation and KiCad files)",
                "default": name
            }
            
        if not any(k.lower() == 'directory_name' for k in variables.keys()):
            variables["directory_name"] = {
                "description": "Directory/repository name (used for folder structure)",
                "default": "{{ project_name|lower|replace(' ', '-') }}"
            }
            
        if not any(k.lower() == 'project_filename' for k in variables.keys()):
            variables["project_filename"] = {
                "description": "Main KiCad project filename (without extension)",
                "default": "{{ project_name }}"
            }
    
    metadata = {
        "name": name,
        "description": description or f"KiCad project template for {name}",
        "use_case": use_case or "",
        "version": "1.0.0",
        "variables": variables
    }
    
    if extends:
        metadata["extends"] = extends
    
    if dependencies:
        metadata["dependencies"] = {
            "recommended": dependencies
        }
    
    return metadata


def write_template_metadata(directory: Path, metadata: Dict[str, Any]) -> None:
    """
    Write template metadata to a file.
    
    Args:
        directory: Template directory
        metadata: Metadata dictionary
        
    Raises:
        IOError: If the file can't be written
    """
    metadata_file = directory / TEMPLATE_METADATA
    
    with open(metadata_file, "w") as f:
        yaml.dump(metadata, f, default_flow_style=False)


def process_markdown_file(source_file: Path, target_file: Path, variables: Dict[str, Dict[str, Any]]) -> None:
    """
    Process a Markdown file to add a template header with available variables.
    
    Args:
        source_file: Source file path
        target_file: Target file path
        variables: Dictionary of template variables
    """
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add a Jinja comment and variable reference section at the top
        header = "{# This file is a Jinja template. The section below will be removed when creating a project. #}\n\n"
        header += "{% if false %}\n"  # Trick to make the following section removable
        header += "# Template Variables\n\n"
        header += "This template supports the following variables:\n\n"
        
        # List all available variables with their descriptions
        for var_name, var_info in variables.items():
            description = var_info.get('description', f'Value for {var_name}')
            default = var_info.get('default', '')
            header += f"- `{{ {var_name} }}`: {description} (default: \"{default}\")\n"
        
        header += "\nUse these variables in your content with `{{ variable_name }}`.\n"
        header += "{% endif %}\n"
        
        # Create new content with header and original content
        new_content = header + content
        
        # Write to .jinja2 file
        target_file_jinja = Path(str(target_file) + '.jinja2')
        with open(target_file_jinja, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        click.echo(f"Processed Markdown file: {source_file.name}")
    
    except Exception as e:
        click.echo(f"Error processing Markdown file {source_file.name}: {e}", err=True)
        # Fallback to direct copy
        shutil.copy2(source_file, target_file)


def create_template_structure(
    source_directory: Path,
    template_directory: Path,
    metadata: Dict[str, Any],
    gitignore_spec: Optional[pathspec.PathSpec] = None,
    additional_excludes: Optional[List[str]] = None
) -> None:
    """
    Create template structure from source directory.
    
    Args:
        source_directory: Source directory containing the project
        template_directory: Target directory for the template
        metadata: Template metadata
        gitignore_spec: PathSpec object representing gitignore patterns
        additional_excludes: Additional patterns to exclude
        
    Returns:
        None
    """
    # Create template directories
    template_content_dir = template_directory / TEMPLATE_CONTENT_DIR
    hooks_dir = template_directory / HOOKS_DIR
    
    os.makedirs(template_content_dir, exist_ok=True)
    os.makedirs(hooks_dir, exist_ok=True)
    
    # Write metadata
    write_template_metadata(template_directory, metadata)
    
    # Create hook script
    create_hook_script(hooks_dir)
    
    # Create additional spec for excluded files
    additional_spec = None
    if additional_excludes:
        additional_spec = pathspec.PathSpec.from_lines('gitwildmatch', additional_excludes)
    
    # Define common directories to exclude
    common_excludes = [
        "venv", "env", ".venv", ".env", ".git", "node_modules", "__pycache__", 
        "dist", "build", ".pytest_cache", ".idea", ".vscode", 
        TEMPLATES_DIR  # Avoid recursive copying of templates directory
    ]
    
    # Debug gitignore if available
    if gitignore_spec:
        click.echo("Using .gitignore patterns for exclusion")
    
    # Max path length to prevent "file name too long" errors
    MAX_PATH_LENGTH = 512
    
    # Track main KiCad files
    main_project_file = None
    main_schematic_file = None
    main_pcb_file = None
    
    # First scan to find main KiCad files
    click.echo("Scanning for main KiCad files...")
    for root, _, files in os.walk(source_directory):
        rel_root = os.path.relpath(root, source_directory)
        
        # Skip if in excluded directory
        if any(excl in rel_root for excl in common_excludes):
            continue
            
        # Check for gitignore matches - ensure proper path formatting for directories
        git_path = rel_root.replace(os.sep, "/")
        if not git_path.endswith("/") and git_path != ".":
            git_path += "/"
        if gitignore_spec and gitignore_spec.match_file(git_path):
            continue
        
        # Look for KiCad files in the root directory
        for file in files:
            rel_path = os.path.join(rel_root, file)
            git_path = rel_path.replace(os.sep, "/")
            
            # Skip gitignored files
            if gitignore_spec and gitignore_spec.match_file(git_path):
                continue
                
            # Look for main files in the root directory or top-level folders
            if rel_root == "." or len(rel_root.split(os.sep)) <= 1:
                file_lower = file.lower()
                
                if file_lower.endswith(KICAD_PROJECT_EXT) and not main_project_file:
                    main_project_file = os.path.join(root, file)
                    click.echo(f"Found main project file: {file}")
                    
                elif file_lower.endswith(KICAD_SCHEMATIC_EXT) and not main_schematic_file:
                    main_schematic_file = os.path.join(root, file)
                    click.echo(f"Found main schematic file: {file}")
                    
                elif file_lower.endswith(KICAD_PCB_EXT) and not main_pcb_file:
                    main_pcb_file = os.path.join(root, file)
                    click.echo(f"Found main PCB file: {file}")
    
    # Copy files from source to template
    for root, dirs, files in os.walk(source_directory):
        rel_root = os.path.relpath(root, source_directory)
        if rel_root == ".":
            rel_root = ""
        
        # Skip directories that should be excluded
        dirs_to_remove = []
        for d in dirs:
            # Skip template directories and virtual environments
            if d in common_excludes:
                dirs_to_remove.append(d)
                click.echo(f"Excluding common directory: {d}")
                continue
                
            # Check if this is a path we would exclude
            rel_path = os.path.join(rel_root, d)
            
            # Ensure proper path format for gitignore matching 
            # (pathspec expects paths with forward slashes and trailing slash for directories)
            git_path = rel_path.replace(os.sep, "/")
            if not git_path.endswith("/"):
                git_path += "/"
            
            # Prevent copying into template directory to avoid recursion
            if template_directory.as_posix() in os.path.join(source_directory, rel_path):
                dirs_to_remove.append(d)
                click.echo(f"Preventing recursive template copy: {rel_path}")
                continue
                
            # Check for gitignore and custom exclusions
            if gitignore_spec and gitignore_spec.match_file(git_path):
                dirs_to_remove.append(d)
                click.echo(f"Excluding directory from gitignore: {git_path}")
            elif additional_spec and additional_spec.match_file(git_path):
                dirs_to_remove.append(d)
                click.echo(f"Excluding directory from additional patterns: {git_path}")
                
        for d in dirs_to_remove:
            if d in dirs:  # Extra check to avoid KeyError
                dirs.remove(d)
        
        # Create target directory
        if rel_root:
            target_dir = template_content_dir / rel_root
            
            # Check path length
            if len(str(target_dir)) > MAX_PATH_LENGTH:
                click.echo(f"Skipping directory due to path length: {rel_root}")
                continue
                
            os.makedirs(target_dir, exist_ok=True)
        else:
            target_dir = template_content_dir
        
        # Copy files
        for file in files:
            rel_path = os.path.join(rel_root, file)
            
            # Ensure proper path format for gitignore matching
            git_path = rel_path.replace(os.sep, "/")
            
            # Skip gitignored files and additional excluded files
            if gitignore_spec and gitignore_spec.match_file(git_path):
                click.echo(f"Excluding file from gitignore: {git_path}")
                continue
            if additional_spec and additional_spec.match_file(git_path):
                click.echo(f"Excluding file from additional patterns: {git_path}")
                continue
            
            # Skip .kicad_prl files - they are project-specific preferences
            if file.lower().endswith(KICAD_PRL_EXT):
                click.echo(f"Excluding KiCad project preferences file: {git_path}")
                continue
            
            source_file = source_directory / rel_path
            
            # Special handling for main KiCad files and markdown
            file_path = os.path.join(root, file)
            
            # Generate target file path
            # For main KiCad files, use generic names
            if main_project_file and file_path == main_project_file:
                target_file = template_content_dir / rel_root / "{{ project_filename }}.kicad_pro"
            elif main_schematic_file and file_path == main_schematic_file:
                target_file = template_content_dir / rel_root / "{{ project_filename }}.kicad_sch"
            elif main_pcb_file and file_path == main_pcb_file:
                target_file = template_content_dir / rel_root / "{{ project_filename }}.kicad_pcb"
            else:
                target_file = template_content_dir / rel_path
            
            # Check path length
            if len(str(target_file)) > MAX_PATH_LENGTH:
                click.echo(f"Skipping file due to path length: {rel_path}")
                continue
            
            # Process main project file
            if main_project_file and file_path == main_project_file:
                process_kicad_project_file(source_file, target_file, metadata.get('variables', {}))
            
            # Process main schematic file
            elif main_schematic_file and file_path == main_schematic_file:
                process_kicad_schematic_file(source_file, target_file, metadata.get('variables', {}))
            
            # Process main PCB file
            elif main_pcb_file and file_path == main_pcb_file:
                process_kicad_pcb_file(source_file, target_file, metadata.get('variables', {}))
            
            # Process Markdown files
            elif source_file.name.lower().endswith('.md'):
                process_markdown_file(source_file, target_file, metadata.get('variables', {}))
            
            # All other files are just copied
            else:
                try:
                    shutil.copy2(source_file, target_file)
                except OSError as e:
                    click.echo(f"Error copying file {rel_path}: {e}", err=True)


def create_hook_script(hooks_dir: Path) -> None:
    """
    Create a basic post-creation hook script.
    
    Args:
        hooks_dir: Hooks directory
    """
    hook_script = hooks_dir / POST_CREATE_HOOK
    
    script_content = '''"""
Post-creation hook for template.
This script runs after the template has been used to create a new project.
"""

def post_create(context):
    """
    Hook that runs after project creation.
    
    Args:
        context: Dict containing:
            - project_dir: Path to the created project
            - variables: Dict of all template variables and their values
            - template: Template metadata
    
    Returns:
        None
    """
    # Uncomment and modify as needed
    # import subprocess
    # import os
    
    # Example: Initialize git repository
    # subprocess.run(["git", "init"], cwd=context["project_dir"])
    
    # Example: Create README.md if it doesn't exist
    # readme_path = os.path.join(context["project_dir"], "README.md")
    # if not os.path.exists(readme_path):
    #     with open(readme_path, "w") as f:
    #         f.write(f"# {context['variables']['project_name']}\\n\\n")
    #         f.write("Created with KiCad Library Manager\\n")
    
    # Print message to user
    click.echo(f"Project {context['variables']['project_name']} created successfully!")
    click.echo(f"Location: {context['project_dir']}")
'''
    
    with open(hook_script, "w") as f:
        f.write(script_content)


def process_kicad_project_file(source_file: Path, target_file: Path, variables: Dict[str, Dict[str, Any]]) -> None:
    """
    Process a KiCad project file (.kicad_pro).
    
    Args:
        source_file: Source file path
        target_file: Target file path
        variables: Dictionary of template variables
    """
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get project name variable
        project_name_var = None
        for var_name, var_info in variables.items():
            if var_name.lower() in ('project_name', 'projectname', 'project'):
                project_name_var = var_name
                break
        
        # Parse JSON project file
        try:
            project_data = json.loads(content)
            
            # Replace project title if found
            if project_name_var and 'meta' in project_data and 'filename' in project_data['meta']:
                original_filename = project_data['meta']['filename']
                # Replace with project_filename variable - using {{ project_name }}.kicad_pro pattern
                project_data['meta']['filename'] = "{{ project_filename }}.kicad_pro"
                click.echo(f"  Templated project filename: '{original_filename}' → '{{ project_filename }}.kicad_pro'")
            
            # Write updated JSON to a .jinja2 file
            target_file_jinja = Path(str(target_file) + '.jinja2')
            with open(target_file_jinja, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2)
                
            click.echo(f"Processed KiCad project file: {source_file.name} → {target_file_jinja.name}")
            
        except json.JSONDecodeError:
            click.echo(f"Warning: Could not parse {source_file.name} as JSON. Copying without changes.")
            shutil.copy2(source_file, target_file)
    
    except Exception as e:
        click.echo(f"Error processing KiCad project file {source_file.name}: {e}", err=True)
        # Fallback to direct copy
        shutil.copy2(source_file, target_file)


def process_kicad_schematic_file(source_file: Path, target_file: Path, variables: Dict[str, Dict[str, Any]]) -> None:
    """
    Process a KiCad schematic file (.kicad_sch).
    
    Args:
        source_file: Source file path
        target_file: Target file path
        variables: Dictionary of template variables
    """
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace project name references in schematic file
        # Replace project references
        project_pattern = re.compile(r'\(project\s+"([^"]+)"')
        content = project_pattern.sub(r'(project "{{ project_filename }}"', content)
        click.echo(f"  Templated schematic project name references with '{{ project_filename }}'")
        
        # Write to .jinja2 file
        target_file_jinja = Path(str(target_file) + '.jinja2')
        with open(target_file_jinja, 'w', encoding='utf-8') as f:
            f.write(content)
            
        click.echo(f"Processed KiCad schematic file: {source_file.name} → {target_file_jinja.name}")
    
    except Exception as e:
        click.echo(f"Error processing KiCad schematic file {source_file.name}: {e}", err=True)
        # Fallback to direct copy
        shutil.copy2(source_file, target_file)


def process_kicad_pcb_file(source_file: Path, target_file: Path, variables: Dict[str, Dict[str, Any]]) -> None:
    """
    Process a KiCad PCB file (.kicad_pcb).
    
    Args:
        source_file: Source file path
        target_file: Target file path
        variables: Dictionary of template variables
    """
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find and replace sheet references
        sheet_pattern = re.compile(r'\(sheetfile\s+"([^"]+)"')
        original_filename = source_file.stem
        
        # Replace sheet references with template variable
        def sheet_replacer(match):
            sheet_name = match.group(1)
            if original_filename in sheet_name:
                # Replace with template variable
                return f'(sheetfile "{{ project_filename }}.kicad_sch"'
            return match.group(0)
        
        content = sheet_pattern.sub(sheet_replacer, content)
        click.echo(f"  Templated PCB sheet references with '{{ project_filename }}.kicad_sch'")
        
        # Write to .jinja2 file
        target_file_jinja = Path(str(target_file) + '.jinja2')
        with open(target_file_jinja, 'w', encoding='utf-8') as f:
            f.write(content)
            
        click.echo(f"Processed KiCad PCB file: {source_file.name} → {target_file_jinja.name}")
    
    except Exception as e:
        click.echo(f"Error processing KiCad PCB file {source_file.name}: {e}", err=True)
        # Fallback to direct copy
        shutil.copy2(source_file, target_file)


# Add new functions for rendering templates and creating projects from templates
def render_template_string(template_str: str, variables: Dict[str, Any]) -> str:
    """
    Render a template string using Jinja2.
    
    Args:
        template_str: The template string to render
        variables: Dictionary of variables to use in rendering
        
    Returns:
        Rendered string
    """
    try:
        template = jinja2.Template(template_str)
        return template.render(**variables)
    except jinja2.exceptions.TemplateError as e:
        click.echo(f"Warning: Failed to render template: {e}", err=True)
        return template_str

def render_filename(filename: str, variables: Dict[str, Any]) -> str:
    """
    Render a filename using Jinja2 if it contains template variables.
    
    Args:
        filename: The filename to render
        variables: Dictionary of variables to use in rendering
        
    Returns:
        Rendered filename
    """
    # Only try to render if the filename contains a Jinja2 template pattern
    if "{{" in filename and "}}" in filename:
        try:
            # Create a proper Jinja2 environment
            env = jinja2.Environment(undefined=jinja2.StrictUndefined)
            template = env.from_string(filename)
            return template.render(**variables)
        except jinja2.exceptions.TemplateError as e:
            click.echo(f"Warning: Failed to render filename {filename}: {e}", err=True)
    
    return filename

def find_all_templates(config: Any) -> Dict[str, Dict[str, Any]]:
    """
    Find all templates in all configured libraries.
    
    Args:
        config: The configuration object
        
    Returns:
        Dictionary mapping template names to template metadata
    """
    all_templates = {}
    all_libraries = config.get_libraries()
    
    for library in all_libraries:
        library_path = library.get("path")
        if not library_path or not Path(library_path).exists():
            continue
        
        templates = list_templates_in_directory(Path(library_path))
        for template in templates:
            name = template.get("name")
            if name and name not in all_templates:
                # Add the template
                all_templates[name] = template
                
                # Add source library information
                all_templates[name]["source_library"] = library.get("name", "unknown")
                all_templates[name]["library_path"] = library_path
            else:
                # Store template
                if name in all_templates:
                    # Use click.echo for warnings/errors
                    click.echo(f"Warning: Duplicate template name '{name}' found.", err=True)
                    click.echo(f"  Existing: {all_templates[name]['path']}", err=True)
                    click.echo(f"  New: {template['path']}", err=True)
                all_templates[name] = template

    return all_templates

def render_template_file(
    source_file: Path, 
    target_file: Path, 
    variables: Dict[str, Any],
    is_binary: bool = False
) -> bool:
    """
    Render a template file to a target file.
    
    Args:
        source_file: Source file path
        target_file: Target file path
        variables: Variables to use in rendering
        is_binary: Whether the file is binary (should not be rendered)
        
    Returns:
        True if successful, False otherwise
    """
    # Create target directory if it doesn't exist
    os.makedirs(target_file.parent, exist_ok=True)
    
    if is_binary:
        # Simply copy binary files
        try:
            shutil.copy2(source_file, target_file)
            return True
        except Exception as e:
            click.echo(f"Error copying binary file {source_file}: {e}", err=True)
            return False
    
    # For text files, render them if they have a .jinja2 extension
    try:
        file_content = ""
        with open(source_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        
        # If it's a Jinja template, process it
        if source_file.name.endswith(".jinja2"):
            # Create Jinja2 template environment with safe auto-escaping
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(source_file.parent),
                autoescape=jinja2.select_autoescape(["html", "xml"]),
                undefined=jinja2.StrictUndefined
            )
            
            # Parse the template
            try:
                template = env.from_string(file_content)
                rendered_content = template.render(**variables)
                
                # Write rendered content to target file (without .jinja2 extension)
                target_path = Path(str(target_file).rstrip(".jinja2"))
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(rendered_content)
                
                return True
            except jinja2.exceptions.TemplateError as e:
                click.echo(f"Error rendering template {source_file.name}: {e}", err=True)
                # Fall back to copying the file as-is
                shutil.copy2(source_file, target_file)
                return False
        else:
            # Not a template file, just copy it
            shutil.copy2(source_file, target_file)
            return True
    
    except Exception as e:
        click.echo(f"Error processing file {source_file}: {e}", err=True)
        # Try to copy anyway
        try:
            shutil.copy2(source_file, target_file)
            return True
        except:
            return False

def create_project_from_template(
    template_dir: Path,
    project_dir: Path,
    variables: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    skip_hooks: bool = False
) -> bool:
    """
    Create a new project from a template.
    
    Args:
        template_dir: Path to the template directory
        project_dir: Path to create the project in
        variables: Dictionary of template variables
        metadata: Template metadata
        dry_run: If True, show what would be created without making changes
        skip_hooks: If True, skip running post-creation hooks
        
    Returns:
        True if successful, False otherwise
    """
    template_content_dir = template_dir / TEMPLATE_CONTENT_DIR
    
    if not template_content_dir.exists() or not template_content_dir.is_dir():
        click.echo(f"Error: Template content directory {template_content_dir} does not exist", err=True)
        return False
    
    # Check if project directory exists and is not empty
    if project_dir.exists():
        files = list(project_dir.iterdir())
        if files and not dry_run:
            click.echo(f"Warning: Target directory {project_dir} is not empty", err=True)
            # Continue anyway - we'll merge the template with the existing directory
    
    # Use provided metadata if available, otherwise load it (fallback)
    if metadata is None:
        metadata_file = template_dir / TEMPLATE_METADATA
        if not metadata_file.exists():
            click.echo(f"Error: Template metadata file {metadata_file} does not exist and was not provided.", err=True)
            return False
        try:
            with open(metadata_file, "r") as f:
                metadata = yaml.safe_load(f)
            if not metadata: # Handle empty metadata file
                click.echo(f"Warning: Template metadata file is empty: {metadata_file}", err=True)
                metadata = {} # Use empty dict
        except Exception as e:
            click.echo(f"Error reading template metadata {metadata_file}: {e}", err=True)
            return False
    
    # Check if we need to merge with variables from a parent template
    if "extends" in metadata and metadata["extends"]:
        # TODO: Handle template inheritance
        click.echo(f"Warning: Template inheritance not fully implemented yet", err=True)
    
    # Binary file extensions that should not be rendered
    binary_extensions = {
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.pdf', 
        '.zip', '.gz', '.tar', '.7z', '.rar', '.exe', '.dll', '.so',
        '.pyc', '.pyo', '.obj', '.lib', '.a'
    }
    
    # Collect files to create
    files_to_create = []
    
    # Walk through the template directory
    for root, dirs, files in os.walk(template_content_dir):
        rel_root = os.path.relpath(root, template_content_dir)
        if rel_root == ".":
            rel_root = ""
        
        # Create target directory path
        if rel_root:
            # Render directory name if it contains template variables
            rendered_dir_path = render_filename(rel_root, variables)
            target_dir = project_dir / rendered_dir_path
            
            if dry_run:
                click.echo(f"Would create directory: {target_dir}")
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = project_dir
        
        # Process files
        for file in files:
            source_file = Path(root) / file
            
            # Strip .jinja2 extension from target file if present
            target_filename = file
            if target_filename.endswith(".jinja2"):
                target_filename = target_filename[:-7]
            
            # Render the filename if it contains template variables
            rendered_filename = render_filename(target_filename, variables)
            
            # Create target file path
            if rel_root:
                rendered_dir_path = render_filename(rel_root, variables)
                target_file = project_dir / rendered_dir_path / rendered_filename
            else:
                target_file = project_dir / rendered_filename
            
            # Check if it's a binary file
            is_binary = any(target_filename.lower().endswith(ext) for ext in binary_extensions)
            
            # Add to the list of files to create
            files_to_create.append({
                "source": source_file,
                "target": target_file,
                "is_binary": is_binary
            })
    
    # In dry run mode, just show what would be created
    if dry_run:
        click.echo() # Add spacing
        click.echo("The following files would be created:")
        for file_info in files_to_create:
            click.echo(f"  {file_info['target']}")
        return True
    
    # Actually create the files
    for file_info in files_to_create:
        success = render_template_file(
            source_file=file_info["source"],
            target_file=file_info["target"],
            variables=variables,
            is_binary=file_info["is_binary"]
        )
        
        if not success:
            click.echo(f"Warning: Failed to create {file_info['target']}", err=True)
    
    # Run post-creation hook if present and not skipped
    if not skip_hooks:
        hook_script = template_dir / HOOKS_DIR / POST_CREATE_HOOK
        if hook_script.exists():
            try:
                run_post_create_hook(hook_script, project_dir, variables, metadata)
            except Exception as e:
                click.echo(f"Error running post-creation hook: {e}", err=True)
                traceback.print_exc()
    
    return True

def run_post_create_hook(
    hook_script: Path,
    project_dir: Path,
    variables: Dict[str, Any],
    template_metadata: Dict[str, Any]
) -> None:
    """
    Run a post-creation hook script.
    
    Args:
        hook_script: Path to the hook script
        project_dir: Path to the created project
        variables: Dictionary of template variables
        template_metadata: Template metadata
        
    Raises:
        Exception: If the hook script fails
    """
    # Check if the hook script exists
    if not hook_script.exists():
        return
    
    # Load the hook script
    spec = importlib.util.spec_from_file_location("hook", hook_script)
    if not spec or not spec.loader:
        click.echo(f"Error: Could not load hook script {hook_script}", err=True)
        return
    
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    
    # Check if the post_create function exists
    if not hasattr(hook, "post_create"):
        click.echo(f"Warning: Hook script {hook_script} does not have a post_create function", err=True)
        return
    
    # Create the context
    context = {
        "project_dir": str(project_dir),
        "variables": variables,
        "template": template_metadata
    }
    
    # Run the post_create function
    hook.post_create(context) 