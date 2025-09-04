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
  *Example:* `kilm add-hook --directory ~/my-kicad-libs-repo`

- `--force / --no-force`: 
  If a `post-merge` hook already exists, overwrite it with the KiLM hook. Without `--force`, the command might fail if a hook already exists.
  *Example:* `kilm add-hook --force`

- `--help`: 
  Show the help message and exit.

## Behavior

1.  **Locates Git Directory:** Finds the `.git/hooks` directory within the specified repository path.
2.  **Checks Existing Hook:** Looks for an existing file named `post-merge`.
3.  **Writes Hook Script:** Creates or overwrites the `.git/hooks/post-merge` file with a script similar to this:
    ```bash
    #!/bin/sh
    # KiCad Library Manager auto-update hook
    # Added by kilm add-hook command

    echo "Running KiCad Library Manager update..."
    kilm update

    # Uncomment to set up libraries automatically (use with caution)
    # kilm setup

    echo "KiCad libraries update complete."
    ```
4.  **Makes Executable:** Sets the execute permission (`chmod +x`) on the `post-merge` script.

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

## Customization

If you want the hook to do more, such as automatically running `kilm setup` after updating (which is potentially riskier as it modifies KiCad config automatically), you can manually edit the generated `.git/hooks/post-merge` script.

**Example (Manual Edit for Auto-Setup):**
```bash
#!/bin/sh
# KiCad Library Manager auto-update hook
# Added by kilm add-hook command

echo "Running KiCad Library Manager update..."
kilm update

# Uncomment to set up libraries automatically (use with caution)
kilm setup

echo "KiCad libraries update complete."
``` 