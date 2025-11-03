# Security Policy

## Supported Versions
| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes     |
| < 0.1   | ❌ No      |

This table will be updated as new releases are published.

## Reporting a Vulnerability
If you discover a security vulnerability in MP3paraMIDI, please report it privately so we can address it before public disclosure. Avoid opening public issues for potential security problems.

### How to Report
- **Email:** security@zarigata.dev (preferred)
- **GitHub:** Use the "Report a vulnerability" option in the Security tab (if enabled)

When reporting, please include:
- A detailed description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested remediation or workaround (if available)

## What to Expect
- Acknowledgment of your report within **48 hours**
- Regular updates on the investigation and mitigation progress
- Notification when the issue is resolved
- Optional public credit in release notes if you would like to be acknowledged

## Security Considerations
- **Local Processing:** All audio processing happens locally on the user's machine. No audio data is uploaded to external services.
- **AI Models:** Models are downloaded from official sources (Spotify and Meta) and cached in the `models/` directory.
- **Dependencies:** We keep dependencies up to date and rely on Dependabot alerts to notify us of vulnerabilities.
- **User Data:** Application settings are stored locally via Qt's `QSettings`. No personal data is collected or transmitted.
- **Known Limitations:**
  - FFmpeg is an external dependency that users install separately.
  - MIDI playback relies on system MIDI capabilities (pygame).
  - File system access is required for reading audio files and writing MIDI files.

## Best Practices
- Always download MP3paraMIDI from the official GitHub repository releases page.
- Verify checksums of downloaded binaries when provided.
- Keep your installation up to date with the latest release.
- Use antivirus software and exercise caution with audio files from untrusted sources.

## Disclosure Policy
We follow responsible disclosure practices:
- Security issues are investigated and fixed prior to public disclosure.
- Users are notified of security updates via release notes.
- CVE identifiers may be requested for significant vulnerabilities.

## Contact
- **Security Issues:** security@zarigata.dev or GitHub private reporting
- **General Questions:** GitHub Issues or Discussions
- **Maintainer:** Zarigata

We take security seriously and appreciate responsible disclosure. Thank you for helping keep MP3paraMIDI safe. – Zarigata
