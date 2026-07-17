# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-07-17

### Added

- Midnight Commander style TUI for browsing, downloading, extracting and
  updating FiveM server artifacts on Windows and Linux.
- Left panel listing available Windows/Linux builds (version + release
  date), with known-broken builds flagged using the
  [jgscripts/fivem-artifacts-db](https://github.com/jgscripts/fivem-artifacts-db)
  database.
- Right panel file manager for choosing the install/destination folder.
- One-click "Latest recommended" / "Latest optional" download buttons.
- Download a specific build by number (`F3`) or by picking it from the list.
- Automatic removal of the previous installation (`server/` on Windows,
  `alpine/` on Linux) before installing a new build.
- Side-by-side prompt before overwriting an existing `run.sh` on Linux when
  its content differs from the new artifact's version.
- Create new folders directly from the file panel (`F7`).
- `install.sh` / `install.bat` setup scripts (virtual environment + Python
  auto-install prompt) and `run.sh` / `run.bat` launch scripts.

[Unreleased]: https://github.com/Zoard0412/Fivem-Artifact-Downloader/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Zoard0412/Fivem-Artifact-Downloader/releases/tag/v1.0.0
