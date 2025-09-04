---
title: add-hook
description: Add a Git post-merge hook to automatically update libraries.
---

The `kilm add-hook` command creates or modifies a Git `post-merge` hook script in a specified repository. This hook is designed to automatically run `kilm update` after successful `git pull` or `git merge` operations.

This helps keep your KiLM-managed libraries that are Git repositories synchronized with their remotes automatically.

## Usage

```bash
kilm add-hook [OPTIONS]
```

## Options

- `--directory DIRECTORY`:
  Specifies the path to the Git repository where the hook should be added. Defaults to the current directory.
  _Example:_ `kilm add-hook --directory ~/my-kicad-libs-repo`

- `--force / --no-force`:
  If a `post-merge` hook already exists, overwrite it with the KiLM hook. Without `--force`, the command might fail if a hook already exists.
  _Example:_ `kilm add-hook --force`

- `--help`:
  Show the help message and exit.

## Behavior

1.  **Detects Active Hooks Directory:**
    - Queries `git config core.hooksPath` for custom hooks directory
    - Falls back to `.git/hooks` (standard location)
    - Handles Git worktrees where hooks live in the linked location
2.  **Checks Existing Hook:** Looks for an existing file named `post-merge`.
3.  **Creates Safe Backup:** If a hook exists, creates a timestamped backup before modification.
4.  **Intelligent Content Management:**
    - If KiLM content already exists, updates the managed section
    - If other content exists, merges KiLM content with clear markers
    - Preserves existing user logic while adding KiLM functionality
5.  **Writes Hook Script:** Creates or updates the hook file with content similar to this:

    ```bash
    #!/bin/sh
    # BEGIN KiLM-managed section
    # KiCad Library Manager auto-update hook
    # Added by kilm add-hook command

    echo "Running KiCad Library Manager update..."
    kilm update

    # Uncomment to set up libraries automatically (use with caution)
    # kilm setup

    echo "KiCad libraries update complete."
    # END KiLM-managed section
    ```

6.  **Sets Permissions:** Ensures the hook has executable permissions (`chmod +x`).

## Examples

**Add hook to the current Git repository:**

```bash
# Make sure you are in the root of your Git repository
kilm add-hook
```

**Add hook to a specific repository, overwriting if necessary:**

```bash
kilm add-hook --directory /path/to/another/repo --force
```

## Advanced Features

### Custom Hooks Directory

If your repository uses `git config core.hooksPath` to specify a custom hooks directory, KiLM will automatically detect and use that location.

### Git Worktree Support

For repositories using Git worktrees, KiLM correctly identifies the main repository location and installs hooks in the appropriate hooks directory.

### Safe Updates

- **First Run:** Creates a new hook with KiLM content
- **Subsequent Runs:** Updates only the KiLM-managed section, preserving other customizations
- **Backup Protection:** Always creates timestamped backups before modifications
- **Idempotent:** Safe to run multiple times without duplicating content

## Customization

If you want the hook to do more, such as automatically running `kilm setup` after updating (which is potentially riskier as it modifies KiCad config automatically), you can manually edit the generated hook script.

**Example (Manual Edit for Auto-Setup):**

```bash
#!/bin/sh
# BEGIN KiLM-managed section
# KiCad Library Manager auto-update hook
# Added by kilm add-hook command

echo "Running KiCad Library Manager update..."
kilm update

# Uncomment to set up libraries automatically (use with caution)
kilm setup

echo "KiCad libraries update complete."
# END KiLM-managed section
```
