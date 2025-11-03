# Contributing to MP3paraMIDI

## Welcome
Thank you for your interest in contributing to **MP3paraMIDI**! This project was created by **Zarigata** to make audio-to-MIDI conversion accessible to everyone. Whether you are a musician, developer, tester, or documentation enthusiast, your help is appreciated.

## Code of Conduct
We are committed to providing a welcoming and inclusive environment. By participating in this project you agree to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). Be respectful, constructive, and inclusive—harassment and discrimination are not tolerated.

## Ways to Contribute
- 🐞 Report bugs
- 💡 Suggest new features or improvements
- ✍️ Improve documentation or tutorials
- 💻 Write code for new features or fixes
- 🌐 Translate the application or docs
- ✅ Test releases and report findings

## Getting Started
1. **Fork and clone** the repository to your local machine.
2. **Install prerequisites:**
   - Python 3.10 or 3.11
   - Git
   - Build tools for your platform (C/C++ compilers where required)
3. **Set up the development environment:**
   ```bash
   python -m venv .venv
   # On PowerShell
   .venv\Scripts\Activate.ps1
   # On cmd
   .venv\Scripts\activate.bat
   # On bash
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```
4. **Install optional AI dependencies:**
   ```bash
   pip install -r requirements-ai.txt
   ```
5. **Run the test suite:**
   ```bash
   pytest tests/
   ```
6. **Launch the application (from the repo root):**
   ```bash
   python -m mp3paramidi
   ```

## Development Workflow
1. Create a feature branch from `main` (e.g., `git checkout -b feat/new-feature`).
2. Make focused changes that follow project style guidelines.
3. Write or update tests as needed.
4. Update documentation (README, architecture docs, user guides) when relevant.
5. Commit with [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) prefixes such as `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
6. Push to your fork and open a pull request.

## Code Style
- Follow [PEP 8](https://peps.python.org/pep-0008/) guidelines.
- Format Python code with [Black](https://black.readthedocs.io/en/stable/):
  ```bash
  black src/ tests/
  ```
- Use type hints where practical and keep functions focused.
- Run linters before opening a PR:
  ```bash
  flake8 src/
  mypy src/
  ```
- Write docstrings for public modules, classes, and functions.

## Testing Guidelines
- Add unit tests for each new feature or bug fix.
- Maintain overall test coverage above 80%.
- Use pytest fixtures provided in `tests/fixtures/` for reusable data.
- Mock external services and heavy dependencies (AI models, file I/O) when appropriate.
- Use `pytest-qt` for GUI tests.
- Run the full suite locally before submitting a PR:
  ```bash
  pytest tests/
  ```

## Documentation
- Update `README.md` for user-facing changes.
- Keep docstrings accurate and explanatory.
- Add or update `docs/ARCHITECTURE.md` for significant design changes.
- Include code snippets or screenshots when they help users understand a change.
- Proofread for grammar, clarity, and accessibility.

## Pull Request Process
1. Ensure linting and tests pass locally.
2. Update `CHANGELOG.md` with a summary of your changes.
3. Reference related issues in the PR description (e.g., `Fixes #123`).
4. Respond promptly to review feedback.
5. Squash or tidy commits if requested by maintainers.
6. Wait for maintainer (Zarigata) approval before merging.

## Issue Guidelines
- Search existing issues before opening a new one.
- Use the provided issue templates for bug reports and feature requests.
- Supply detailed reproduction steps, expected vs. actual behavior, system information, and logs/screenshots where applicable.
- Be patient and respectful during discussions.

## Project Structure
- `src/mp3paramidi/` – Core application package
  - `audio/` – Audio loading, preprocessing, pitch/tempo detection, filtering
  - `gui/` – PyQt6 widgets, dialogs, and main window
  - `midi/` – MIDI generation, quantization, and playback utilities
  - `models/` – AI integrations (Demucs, Basic-Pitch, device management)
- `tests/` – Comprehensive unit and integration tests
- `docs/` – Architecture, building, and user documentation
- `build_configs/` – PyInstaller specifications and packaging scripts
- `tools/` – Auxiliary scripts (icon generation, utilities)

## Key Concepts
- **Audio Pipeline:** Loads audio, detects pitch/tempo, filters notes, and prepares data for MIDI conversion.
- **Monophonic vs. Polyphonic:** Choose between traditional single-note detection and AI-powered chord detection.
- **Threading:** Background workers use `QThread` to keep the GUI responsive.
- **Settings Persistence:** User preferences are stored via `QSettings` and applied to new conversions.

## Questions and Support
For help:
- Start with the documentation (`README.md`, `docs/ARCHITECTURE.md`, `docs/AI_MODELS.md`).
- Ask questions in GitHub Discussions or open an issue with relevant details.
- Provide as much context as possible so maintainers can assist effectively.

## License
By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE), the same license as the project.

## Acknowledgments
Thank you to all current and future contributors—every improvement helps make MP3paraMIDI better.

---
**Thank you for contributing to MP3paraMIDI! – Zarigata**
