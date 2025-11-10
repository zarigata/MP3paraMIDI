# Contributing to MP3paraMIDI

Thank you for your interest in contributing to MP3paraMIDI! This document provides guidelines and instructions to help you contribute effectively.

**Developed by [zarigata](https://github.com/zarigata)**

## Table of Contents
1. [Code of Conduct](#code-of-conduct)
2. [How Can I Contribute?](#how-can-i-contribute)
   - [Reporting Bugs](#reporting-bugs)
   - [Suggesting Features](#suggesting-features)
   - [Contributing Code](#contributing-code)
   - [Improving Documentation](#improving-documentation)
3. [Development Setup](#development-setup)
4. [Code Style Guidelines](#code-style-guidelines)
5. [Testing Requirements](#testing-requirements)
6. [Pull Request Process](#pull-request-process)
7. [Attribution and Licensing](#attribution-and-licensing)
8. [Getting Help](#getting-help)

## Code of Conduct

We are committed to fostering an open, welcoming, and inclusive community. By participating, you agree to:

- Be respectful and inclusive of all contributors.
- Welcome newcomers and help them learn.
- Focus on constructive feedback and collaboration.
- Respect differing viewpoints and experiences.
- Accept responsibility and apologize for mistakes.

These principles are inspired by the [Contributor Covenant](https://www.contributor-covenant.org/). If issues arise, contact zarigata via GitHub.

## How Can I Contribute?

### Reporting Bugs

- Use the GitHub issue tracker and the template at [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md).
- Include steps to reproduce, expected vs. actual behavior, environment details, and logs.
- Search existing issues to avoid duplicates.
- Provide sample audio files when relevant (ensure you have rights to share them).

### Suggesting Features

- Open an issue using the template at [.github/ISSUE_TEMPLATE/feature_request.md](.github/ISSUE_TEMPLATE/feature_request.md).
- Describe the use case, motivation, and benefits to users.
- Consider technical complexity and alignment with project goals.

### Contributing Code

- Bug fixes, new features, tests, and documentation improvements are all welcome.
- For significant changes, open an issue first to discuss the proposal.
- Keep changes focused and maintainable.

### Improving Documentation

- Fix typos, clarify instructions, add examples, or update references.
- Verify accuracy against the current codebase before submitting updates.

## Development Setup

Follow the [Installation](README.md#installation) section of the README. Quick start:

```bash
git clone https://github.com/YOUR_USERNAME/MP3paraMIDI.git
cd MP3paraMIDI

python -m venv venv
# Linux/Mac
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

cp .env.example .env
pytest
```

## Code Style Guidelines

MP3paraMIDI follows PEP 8 with automated tooling configured in `requirements-dev.txt`.

### Formatting
- Use **black** (line length 88) and **isort** for import ordering.
- Run before committing:
  ```bash
  black src/ tests/
  isort src/ tests/
  ```

### Linting
- Run **flake8** to catch style and logical issues:
  ```bash
  flake8 src/ tests/
  ```

### Type Checking
- Use **mypy** and add type hints to new code:
  ```bash
  mypy src/
  ```

### Documentation & Naming
- Use Google-style or NumPy-style docstrings for public APIs.
- Naming conventions:
  - Functions & variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private helpers: prefix with `_`

## Testing Requirements

All code changes must include tests. Pytest configuration is defined in `pytest.ini`.

### Structure
- Place tests in the `tests/` directory.
- File names: `test_<module>.py`
- Function names: `test_<behavior>()`

### Markers (see `pytest.ini`)
- `@pytest.mark.unit` – Fast unit tests.
- `@pytest.mark.integration` – Cross-module or external dependency tests.
- `@pytest.mark.slow` – Long-running or resource-intensive tests.
- `@pytest.mark.gradio` – Gradio interface tests.
- `@pytest.mark.main` – Main server end-to-end tests.

### Running Tests
```bash
pytest
pytest -m "not slow"
pytest --cov=src --cov-report=html
pytest tests/test_audio_separation.py
```

Aim for >80% coverage on new modules and >90% on critical paths (audio processing, MIDI conversion). Use `pytest-mock` to mock expensive operations or external calls in unit tests.

## Pull Request Process

1. **Create a branch:**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Implement changes:**
   - Follow style guidelines.
   - Add/adjust tests and documentation.

3. **Run checks:**
   ```bash
   pytest
   black src/ tests/
   flake8 src/ tests/
   mypy src/
   ```

4. **Commit:**
   - Use descriptive commit messages.
   - Preferred format: `<type>: <description>` (e.g., `feat: add midi export option`).

5. **Push to your fork:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Submit PR:**
   - Open a pull request against the main repository.
   - Complete the template at [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).
   - Explain what, why, how to test, and any breaking changes.

7. **Review & Merge:**
   - Maintainers review within 1–2 weeks.
   - Address feedback promptly.
   - After merge, delete your branch and sync with upstream:
     ```bash
     git checkout main
     git pull upstream main
     ```

## Attribution and Licensing

By contributing, you agree that:

1. **License Agreement:**
   - Contributions are licensed under the [MIT License](LICENSE).
   - You have the right to submit the contribution under this license.
   - Commercial use by others is permitted.

2. **Attribution:**
   - The original author, [zarigata](https://github.com/zarigata), must be credited in public uses and derivatives.
   - Retain the LICENSE file and comply with its attribution requirements.

3. **Copyright:**
   - You retain copyright.
   - You grant the project a perpetual, worldwide, non-exclusive license to use your contribution.

4. **Third-Party Code:**
   - Only include code you have rights to share.
   - Ensure third-party licenses are compatible with MIT and document them clearly.

## Getting Help

- **Documentation:** Review [README.md](README.md) and [DOCKER.md](DOCKER.md).
- **Issues:** Search or open tickets in [GitHub Issues](https://github.com/zarigata/MP3paraMIDI/issues).
- **Discussions:** Use GitHub Discussions if enabled.
- **Contact:** Reach out to [zarigata](https://github.com/zarigata).

### Useful Resources
- [Demucs Documentation](https://github.com/facebookresearch/demucs)
- [Basic Pitch Documentation](https://github.com/spotify/basic-pitch)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Gradio Documentation](https://gradio.app/docs/)
- [pytest Documentation](https://docs.pytest.org/)

---

Thank you for contributing to MP3paraMIDI! Your efforts help make this project better for everyone.

**Developed by [zarigata](https://github.com/zarigata)**
