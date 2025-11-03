# Release Process

This guide outlines the steps for preparing, cutting, and publishing MP3paraMIDI releases.

## Release Checklist

1. Update version numbers in:
   - `pyproject.toml`
   - `src/mp3paramidi/__init__.py`
   - `src/mp3paramidi/gui/main_window.py`
2. Update `CHANGELOG.md` with release notes.
3. Ensure build configuration files and icons are up to date.
4. Run the full test suite and smoke tests.
5. Perform local builds (standard + AI) on all target platforms if possible.
6. Update documentation (`README.md`, `docs/BUILDING.md`) if necessary.

## Version Numbering

MP3paraMIDI follows [Semantic Versioning](https://semver.org/):

- **MAJOR**: incompatible API or UI changes.
- **MINOR**: new features while maintaining backward compatibility.
- **PATCH**: backwards-compatible bug fixes and minor improvements.

Increment the version appropriately based on the scope of changes.

## Creating a Release

1. Commit all changes and ensure the repository is clean.
2. Tag the release:
   ```bash
   git tag -a v0.1.0 -m "Release v0.1.0"
   git push origin v0.1.0
   ```
3. Pushing the tag runs `.github/workflows/build.yml`, building artifacts for all platforms and variants.
4. Monitor the GitHub Actions workflow for failures.
5. Once artifacts are uploaded, GitHub automatically creates a release via the workflow.
6. Review and publish the release notes, attaching any additional assets if required.

## Artifact Naming Convention

Artifacts are named using the pattern:
```
MP3paraMIDI-v{VERSION}-{PLATFORM}-{VARIANT}.{EXT}
```
Examples:
- `MP3paraMIDI-v0.1.0-Windows-Standard.exe`
- `MP3paraMIDI-v0.1.0-macOS-AI.dmg`
- `MP3paraMIDI-v0.1.0-Linux-Standard-x86_64.AppImage`

## Code Signing

### Windows

- Use a trusted code-signing certificate or Azure Trusted Signing.
- Store certificate data in GitHub Secrets (`WINDOWS_CERT_BASE64`, `WINDOWS_CERT_PASSWORD`).
- The workflow can be extended to sign executables before artifact upload.

### macOS

- Requires Apple Developer ID and access to notarization services.
- Store relevant credentials in GitHub Secrets (`APPLE_DEVELOPER_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD`).
- Extend the macOS job to run `codesign` and `notarytool submit` using these secrets.

## Post-Release Tasks

1. Update documentation with release highlights if necessary.
2. Announce the release (GitHub Releases, social channels, mailing list, etc.).
3. Monitor issues for regressions or user feedback.
4. Update any roadmap or project boards.

## Hotfix Process

1. Create a branch from the release tag (`git checkout -b hotfix/v0.1.1 v0.1.0`).
2. Apply the fix, update version numbers, and document changes in `CHANGELOG.md`.
3. Run tests and smoke builds.
4. Tag and release the hotfix (`v0.1.1`).

## Rollback Procedure

If a release is broken:

1. Unpublish or delete the release on GitHub.
2. Delete the tag locally and remotely.
   ```bash
   git tag -d v0.1.0
   git push origin :refs/tags/v0.1.0
   ```
3. Fix the issue, bump the version if necessary, and retag.

## CI/CD Integration

- The build workflow (`build.yml`) handles artifact generation and release publication on tags.
- The test workflow (`test-builds.yml`) validates builds on pull requests to catch issues early.
- Ensure secrets for signing/notarization are configured before enabling those steps.
