"""Constants used throughout KiCad Library Manager."""

# Metadata filenames
GITHUB_METADATA_FILE = "kilm.yaml"
CLOUD_METADATA_FILE = ".kilm_metadata"

# KiCad's own configuration file in its configuration directory
KICAD_COMMON_FILE = "kicad_common.json"

# Configuration paths and directories
CONFIG_DIR_NAME = "kicad-lib-manager"
CONFIG_FILE_NAME = "config.yaml"

# Template-related constants
TEMPLATES_DIR = "templates"
TEMPLATE_METADATA = "metadata.yaml"
TEMPLATE_CONTENT_DIR = "template"
HOOKS_DIR = "hooks"

# Library metadata
# Longest environment variable name KiLM generates; some systems limit length.
MAX_ENV_VAR_NAME_LENGTH = 50

# Default configuration values
DEFAULT_MAX_BACKUPS = 5
