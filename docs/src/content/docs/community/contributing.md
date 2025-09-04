---
title: Contributing
description: How to contribute to the KiLM project.
---

Contributions to KiLM are welcome! Whether it's reporting bugs, suggesting features, improving documentation, or submitting code changes, your help is appreciated.

## Reporting Issues

- **Search Existing Issues:** Before creating a new issue, please check if a similar one already exists on the [GitHub Issues page](https://github.com/barisgit/kilm/issues).
- **Provide Details:** If creating a new issue, please include:
    - KiLM version (`kilm --version`)
    - KiCad version
    - Operating System
    - Clear description of the bug or feature request
    - Steps to reproduce the issue (for bugs)
    - Any relevant error messages or logs (use `--verbose` flag if applicable)

## Submitting Changes (Pull Requests)

1.  **Fork the Repository:** Create your own fork of the [KiLM repository](https://github.com/barisgit/kilm) on GitHub.
2.  **Clone Your Fork:** Clone your forked repository to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/kilm.git
    cd kilm
    ```
3.  **Set up Development Environment:** Follow the [Development Setup guide](/community/development/) to install dependencies in a virtual environment.
4.  **Create a Feature Branch:** Create a new branch for your changes.
    ```bash
    git checkout -b feature/my-amazing-feature  # Or fix/issue-number
    ```
5.  **Make Your Changes:** Implement your feature or bug fix.
6.  **Add Tests:** If adding a new feature or fixing a bug, please add corresponding tests in the `tests/` directory.
7.  **Format Code:** Ensure your code is formatted using Black.
    ```bash
    black .
    ```
8.  **Run Tests:** Make sure all tests pass.
    ```bash
    pytest
    ```
9.  **Commit Changes:** Commit your changes with a clear and descriptive commit message.
    ```bash
    git add .
    git commit -m "feat: Add support for XYZ feature"
    ```
10. **Push to Your Fork:** Push your feature branch to your fork on GitHub.
    ```bash
    git push origin feature/my-amazing-feature
    ```
11. **Open a Pull Request:** Go to the original KiLM repository on GitHub and open a Pull Request (PR) from your feature branch to the `main` branch of the upstream repository.
    - Provide a clear description of your changes in the PR.
    - Link to any relevant issues (e.g., "Closes #123").

## Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) guidelines.
- Use [Black](https://github.com/psf/black) for code formatting.
- Write clear and concise code with comments where necessary.

Thank you for contributing! 