# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.1] - 2026-07-17

### Added

- `build.sh` / `build.bat` build standalone, single-file executables with
  PyInstaller, tagged by OS, CPU architecture and app version (e.g.
  `build/macos-arm64-v1.1.1/fivem-artifact-downloader-1.1.1`), including a
  `BUILD_INFO.txt` with the same details. PyInstaller cannot cross-compile,
  so each script only builds for the machine it's run on - producing every
  OS/architecture combination requires running the script on a matching
  machine (or a CI matrix build).

## [1.1.0] - 2026-07-17

### Added

- The right-hand file panel now detects and displays the installed FXServer
  artifact build number and bundled txAdmin version (highlighted in yellow)
  whenever the current folder is (or directly contains) a `server`/`alpine`
  install, read straight from the installed files (`FXServer(.exe)`'s build
  stamp and the `monitor` system resource's `fxmanifest.lua`).
- `F4` checks the selected build's known issues on demand, without having to
  start a download first.
- `F1` opens a help screen listing every keybinding and describing how the
  two panels and the download flow work.
- `F8` (or the "Delete" button) deletes the highlighted file/folder in the
  right-hand file panel after a confirmation prompt.

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

[Unreleased]: https://github.com/Zoard0412/Fivem-Artifact-Downloader/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/Zoard0412/Fivem-Artifact-Downloader/releases/tag/v1.1.1
[1.1.0]: https://github.com/Zoard0412/Fivem-Artifact-Downloader/releases/tag/v1.1.0
[1.0.0]: https://github.com/Zoard0412/Fivem-Artifact-Downloader/releases/tag/v1.0.0
