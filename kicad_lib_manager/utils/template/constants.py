"""Fixed values for KiCad project templates."""

import re

from kicad_lib_manager.utils.constants import TEMPLATES_DIR

# Hook script that runs after a project is created, inside the hooks directory.
POST_CREATE_HOOK = "post_create.py"

# Content files with this suffix are rendered with Jinja2 and lose the suffix.
JINJA_SUFFIX = ".jinja2"

# KiCad file extensions.
KICAD_PROJECT_EXT = ".kicad_pro"
KICAD_SCHEMATIC_EXT = ".kicad_sch"
KICAD_PCB_EXT = ".kicad_pcb"
# Per-user project preferences, never part of a template.
KICAD_PRL_EXT = ".kicad_prl"
MARKDOWN_EXT = ".md"

# Variable that names the main KiCad files of a project created from a template.
PROJECT_FILENAME_VARIABLE = "project_filename"
# Names under which a template may define the project name.
PROJECT_NAME_VARIABLES = frozenset({"project_name", "projectname", "project"})

# Windows-compatible filename placeholders: %{variable.transform}.
FILENAME_VAR_PATTERN = re.compile(r"%\{([^}]+)\}")

# Regexes whose first group is a value worth offering as a template variable.
DEFAULT_VARIABLE_PATTERNS = (
    # Project title in a KiCad project file.
    r'"title": "([^"]+)"',
    # Common project name assignments.
    r'project_name\s*[=:]\s*["\']([^"\']+)["\']',
    r'projectName\s*[=:]\s*["\']([^"\']+)["\']',
    r'PROJECT_NAME\s*[=:]\s*["\']([^"\']+)["\']',
    # Author information.
    r'author\s*[=:]\s*["\']([^"\']+)["\']',
)
# Files larger than this are not scanned for variables.
MAX_SCANNED_FILE_BYTES = 1024 * 1024

# Ignored in addition to a project's .gitignore rules when choosing the files
# of a template; a project without a .gitignore uses neither.
ALWAYS_IGNORED_PATTERNS = (
    "__pycache__/",
    "*.py[cod]",
    "*$py.class",
    "*.so",
    "*.dylib",
    ".env",
    ".venv",
    "env/",
    "venv/",
    "ENV/",
    "node_modules/",
    ".DS_Store",
)

# Directory names never copied into a template, at any depth. The templates
# directory is excluded to avoid copying templates into themselves.
EXCLUDED_DIRECTORIES = frozenset(
    {
        "venv",
        "env",
        ".venv",
        ".env",
        ".git",
        "node_modules",
        "__pycache__",
        "dist",
        "build",
        ".pytest_cache",
        ".idea",
        ".vscode",
        TEMPLATES_DIR,
    }
)

# Longer template paths are skipped to avoid "file name too long" errors.
MAX_TEMPLATE_PATH_LENGTH = 512

# Files copied byte for byte instead of being read as text.
BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".pdf",
        ".zip",
        ".gz",
        ".tar",
        ".7z",
        ".rar",
        ".exe",
        ".dll",
        ".so",
        ".pyc",
        ".pyo",
        ".obj",
        ".lib",
        ".a",
    }
)

# Files that operating systems create, never copied into a project.
SYSTEM_FILES_TO_IGNORE = frozenset(
    {
        ".DS_Store",
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd",
        ".AppleDouble",
        "Thumbs.db",
        "desktop.ini",
    }
)
