# FiveM Artifact Downloader

A Midnight Commander style terminal UI (TUI) for downloading, extracting and
updating [FiveM](https://fivem.net) server artifacts on Windows and Linux.

- Left panel: browse available artifact builds (version + release date),
  with known-broken builds flagged in the list.
- Right panel: a file manager to navigate to and select the server's
  install/destination folder.
- Downloads and installs the selected build into that folder, safely
  replacing any previous installation.

## Features

- Lists all available Windows and Linux builds from `runtime.fivem.net`.
- Flags builds with known issues (`!`), sourced from the
  [jgscripts/fivem-artifacts-db](https://github.com/jgscripts/fivem-artifacts-db)
  database — still lets you download a flagged build after confirming.
- One-click download of the "Latest recommended" and "Latest optional"
  builds as designated by FiveM's own `runtime.fivem.net` page (the version
  number is shown right on the button, e.g. "Latest recommended (25770)").
- Download a specific build by number, or pick one from the list.
- Automatically removes the previous installation (`server/` on Windows,
  `alpine/` on Linux) before installing the new one.
- Never silently overwrites an existing `run.sh` on Linux if its content
  differs from the new artifact's version — shows both versions side by side
  and asks which one to keep.
- Create new folders directly from the file panel.
- Single click always just selects; double click (or Enter) downloads a
  build / opens a folder.

## Requirements

- Python 3.10 or newer.
- Internet access (to query build listings and download artifacts).

## Installation

The install scripts create a local virtual environment (`.venv`) in the
project folder and install the only dependency ([Textual](https://textual.textualize.io/)).
They also detect and offer to install Python itself if it's missing —
you'll be asked to confirm before anything is installed on your system.

### macOS / Linux

```bash
./install.sh
```

- **macOS**: if Python is missing, the script offers to install
  [Homebrew](https://brew.sh) first (if not already present) and then
  `python` via `brew install python`.
- **Debian / Ubuntu**: if Python is missing, the script offers to run
  `sudo apt install python3 python3-venv python3-pip` for you.
- Other Linux distributions: not auto-installed — install Python 3.10+
  with your distro's package manager first, then run `./install.sh`.

> On Debian/Ubuntu, if `install.sh` reports a broken virtual environment
> even with Python installed, the `python3-venv` package (or its
> version-specific variant, e.g. `python3.11-venv`) is usually missing —
> the script will offer to install it automatically too.

### Windows

```
install.bat
```

If Python is missing, the script offers to install it via `winget` (built
into Windows 10 1709+ and Windows 11). If `winget` isn't available, install
Python 3.10+ manually from [python.org](https://www.python.org/downloads/windows/)
(check "Add python.exe to PATH" during setup) and run `install.bat` again.

## Usage

### macOS / Linux

```bash
./run.sh
```

### Windows

```
run.bat
```

### Controls

| Action                         | Key / Mouse                          |
|---------------------------------|---------------------------------------|
| Switch Windows/Linux builds     | `F2` or the Windows/Linux buttons     |
| Download a specific version     | `F3` or "Specific version..." button  |
| Download latest recommended/optional | "Latest recommended (X)" / "Latest optional (Y)" buttons |
| Create a new folder             | `F7` or "New folder..." button        |
| Select an item                  | Single click, or arrow keys           |
| Download build / open folder    | Double click, or `Enter`              |
| Quit                            | `F10` or `q`                          |

Navigate to the desired destination folder in the right-hand file panel
before downloading — whatever folder is currently open there is used as the
install target. The same replacement logic applies as if you ran it
manually: if the folder is (or contains) `server` (Windows) or `alpine`
(Linux), its contents are replaced; otherwise the appropriate folder is
created for you.

## Project structure

- `fivem_tui.py` — the TUI application (entry point).
- `fivem_common.py` — UI-agnostic core logic: querying build listings and
  the broken-artifacts database, downloading, and extracting.
- `requirements.txt` — Python dependencies.
- `install.sh` / `install.bat` — one-time setup (virtual environment + deps).
- `run.sh` / `run.bat` — launches the app.

## Data sources

- Build listings: `https://runtime.fivem.net/artifacts/fivem/build_server_windows/master/`
  and `https://runtime.fivem.net/artifacts/fivem/build_proot_linux/master/`
- Known-broken builds: [jgscripts/fivem-artifacts-db](https://github.com/jgscripts/fivem-artifacts-db)
  (via [artifacts.jgscripts.com](https://artifacts.jgscripts.com))

## License

Licensed under the [Apache License 2.0](LICENSE).
