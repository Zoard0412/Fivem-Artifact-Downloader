"""Core logic for downloading FiveM server artifacts: querying data sources,
downloading and extracting. UI-agnostic - used by the TUI application."""

import json
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from version import __version__

JG_PAGE_URL = "https://artifacts.jgscripts.com"
JG_DB_URL = "https://raw.githubusercontent.com/jgscripts/fivem-artifacts-db/main/db.json"
WINDOWS_LISTING_URL = "https://runtime.fivem.net/artifacts/fivem/build_server_windows/master/"
LINUX_LISTING_URL = "https://runtime.fivem.net/artifacts/fivem/build_proot_linux/master/"
TXADMIN_LATEST_RELEASE_API = "https://api.github.com/repos/citizenfx/txAdmin/releases/latest"

USER_AGENT = f"fivem-artifact-downloader/{__version__}"


class FivemError(Exception):
    """Error meant to be shown to the user (network or data error)."""


@dataclass(frozen=True)
class Build:
    version: int
    build_hash: str
    date: str  # "YYYY-MM-DD HH:MM:SS"


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise FivemError(f"Could not reach: {url}\n{exc}") from exc


def listing_url(platform: str) -> str:
    return WINDOWS_LISTING_URL if platform == "windows" else LINUX_LISTING_URL


_BUILD_ROW_PATTERN = re.compile(
    r'href="\./(\d+)-([0-9a-f]{40})/[^"]+"[^>]*>\s*<div class="level">'
    r'.*?level-left">\s*<span class="panel-icon">.*?</span>\s*(\d+)\s*</div>'
    r'.*?level-item">\s*([\d-]+ [\d:]+)\s*</div>',
    re.DOTALL,
)

_OFFICIAL_TAG_PATTERN = re.compile(
    r'href=\s*"\./(\d+)-([0-9a-f]{40})/[^"]+"[^>]*>\s*LATEST (RECOMMENDED|OPTIONAL)'
)


def _parse_builds(html: str) -> list[Build]:
    builds = []
    for m in _BUILD_ROW_PATTERN.finditer(html):
        version = int(m.group(1))
        build_hash = m.group(2)
        date = m.group(4).strip()
        builds.append(Build(version=version, build_hash=build_hash, date=date))
    return builds


def _parse_official_tags(html: str) -> dict[str, tuple[int, str]]:
    """Parses the "LATEST RECOMMENDED" / "LATEST OPTIONAL" badges that
    runtime.fivem.net itself displays at the top of the listing page.
    Returns e.g. {"recommended": (25770, "8ddc..."), "optional": (7290, "a654...")}."""
    tags: dict[str, tuple[int, str]] = {}
    for m in _OFFICIAL_TAG_PATTERN.finditer(html):
        version = int(m.group(1))
        build_hash = m.group(2)
        key = m.group(3).lower()
        tags[key] = (version, build_hash)
    return tags


def list_builds(platform: str) -> list[Build]:
    """Returns every build from the runtime.fivem.net listing page, newest first."""
    html = http_get(listing_url(platform)).decode("utf-8", errors="replace")
    return _parse_builds(html)


def fetch_platform_data(platform: str) -> tuple[list[Build], dict[str, tuple[int, str]]]:
    """Fetches the runtime.fivem.net listing page once and returns both the
    full build list and the official "latest recommended"/"latest optional"
    tags (see _parse_official_tags)."""
    html = http_get(listing_url(platform)).decode("utf-8", errors="replace")
    return _parse_builds(html), _parse_official_tags(html)


def get_recommended_version(platform: str) -> int:
    """Fetches the current, issue-free build number from the jgscripts page."""
    html = http_get(JG_PAGE_URL).decode("utf-8", errors="replace")
    m = re.search(r'bg-green-500[^>]*>(\d+)</code>', html)
    if not m:
        raise FivemError(
            f"Could not determine the recommended build from {JG_PAGE_URL} "
            "(the page structure may have changed)."
        )
    return int(m.group(1))


def get_broken_ranges() -> list[tuple[int, int, str]]:
    """Fetches the known broken builds from the jgscripts database (db.json)."""
    raw = http_get(JG_DB_URL)
    data = json.loads(raw)
    broken = data.get("brokenArtifacts", {})
    ranges = []
    for key, desc in broken.items():
        if "-" in key:
            start_s, end_s = key.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(key)
        ranges.append((start, end, desc))
    return ranges


def find_issues(version: int, ranges: list[tuple[int, int, str]]) -> list[str]:
    return [desc for start, end, desc in ranges if start <= version <= end]


def build_download_url(version: int, build_hash: str, platform: str) -> str:
    if platform == "windows":
        return f"{WINDOWS_LISTING_URL}{version}-{build_hash}/server.zip"
    return f"{LINUX_LISTING_URL}{version}-{build_hash}/fx.tar.xz"


def download_file(url: str, dest: Path, progress_cb=None):
    """progress_cb(downloaded_bytes, total_bytes) - total_bytes may be 0 if unknown."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = resp.length or 0
            downloaded = 0
            chunk_size = 1024 * 1024
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
    except urllib.error.URLError as exc:
        raise FivemError(f"Download error: {exc}") from exc


def resolve_artifact_dir(output: Path, platform: str):
    """
    Returns: (artifact_dir, extraction_parent, other_dir)
    artifact_dir: path to the "server" (windows) or "alpine" (linux) folder.
    extraction_parent: where we actually extract to (for linux this is the
    parent of artifact_dir, because the archive itself contains the "alpine"
    folder and run.sh).
    other_dir: a previous installation of the other platform, if any (gets removed).
    """
    own_name = "server" if platform == "windows" else "alpine"
    other_name = "alpine" if platform == "windows" else "server"

    if output.name in ("server", "alpine"):
        if output.name != own_name:
            raise FivemError(
                f"The destination folder is named '{output.name}', but platform "
                f"'{platform}' is selected (that would require a folder named '{own_name}')."
            )
        return output, output.parent, None

    parent = output
    artifact_dir = parent / own_name
    other_dir = parent / other_name
    return artifact_dir, parent, (other_dir if other_dir.exists() else None)



# The FXServer binary embeds a plain-text build stamp used for its "-V"
# output, e.g. "master SERVER v1.0.0.32561 win32" (Windows) or
# "master v1.0.0.32561 linux" (Linux) - this is the only place the actual
# artifact build number appears anywhere in an already-extracted install.
_ARTIFACT_STAMP_PATTERN = re.compile(rb"master(?: SERVER)? v1\.0\.0\.(\d+) (?:win32|linux)")
_TXADMIN_VERSION_PATTERN = re.compile(r"^\s*version\s+'([^']+)'", re.MULTILINE)


def _artifact_paths(folder: Path) -> tuple[Path, Path] | tuple[None, None]:
    """Given a "server" (Windows) or "alpine" (Linux) install folder, returns
    (fxserver_exe, citizen_dir); (None, None) if the folder name doesn't
    match either platform layout."""
    if folder.name == "server":
        return folder / "FXServer.exe", folder / "citizen"
    if folder.name == "alpine":
        return folder / "opt" / "cfx-server" / "FXServer", folder / "opt" / "cfx-server" / "citizen"
    return None, None


def _monitor_dir(folder: Path) -> Path | None:
    """Returns the bundled txAdmin resource folder (system_resources/monitor)
    for a "server"/"alpine" install folder, or None if not recognized."""
    _, citizen = _artifact_paths(folder)
    if citizen is None:
        return None
    return citizen / "system_resources" / "monitor"


def detect_installed_versions(folder: Path) -> tuple[int | None, str | None]:
    """Given a "server" (Windows) or "alpine" (Linux) install folder, tries to
    detect the installed FXServer artifact build number and the bundled
    txAdmin version. Returns (artifact_version, txadmin_version); either (or
    both) may be None if the file layout doesn't match what's expected, or
    detection otherwise fails - never raises."""
    exe, citizen = _artifact_paths(folder)
    if exe is None:
        return None, None

    artifact_version = None
    try:
        m = _ARTIFACT_STAMP_PATTERN.search(exe.read_bytes())
        if m:
            artifact_version = int(m.group(1))
    except OSError:
        pass

    txadmin_version = None
    try:
        manifest = citizen / "system_resources" / "monitor" / "fxmanifest.lua"
        m = _TXADMIN_VERSION_PATTERN.search(manifest.read_text(encoding="utf-8", errors="replace"))
        if m:
            txadmin_version = m.group(1)
    except OSError:
        pass

    return artifact_version, txadmin_version


def compare_versions(a: str, b: str) -> int:
    """Compares two dotted version strings (e.g. "8.1.1"). Numeric segments
    are compared numerically. Returns -1, 0 or 1. Falls back to a plain
    string comparison if the two versions aren't structurally comparable
    (e.g. mismatched pre-release suffixes)."""
    def parts(v: str) -> list[int | str]:
        return [int(p) if p.isdigit() else p for p in v.split(".")]

    pa, pb = parts(a), parts(b)
    length = max(len(pa), len(pb))
    pa += [0] * (length - len(pa))
    pb += [0] * (length - len(pb))
    try:
        if pa == pb:
            return 0
        return -1 if pa < pb else 1
    except TypeError:
        return -1 if a < b else (1 if a > b else 0)


def backup_txadmin(artifact_dir: Path) -> Path | None:
    """Copies the currently installed txAdmin (system_resources/monitor) to a
    temp folder before it gets wiped by a fresh artifact extraction. Returns
    the backup path, or None if there's nothing installed to back up. Pair
    with cleanup_txadmin_backup() once done."""
    monitor = _monitor_dir(artifact_dir)
    if monitor is None or not monitor.exists():
        return None
    backup_path = Path(tempfile.mkdtemp(prefix="fivem-txadmin-backup-")) / "monitor"
    shutil.copytree(monitor, backup_path)
    return backup_path


def restore_txadmin(artifact_dir: Path, backup: Path) -> None:
    """Restores a previously backed-up txAdmin over whatever a fresh artifact
    extraction just installed."""
    monitor = _monitor_dir(artifact_dir)
    if monitor is None:
        return
    if monitor.exists():
        shutil.rmtree(monitor)
    shutil.copytree(backup, monitor)


def cleanup_txadmin_backup(backup: Path) -> None:
    shutil.rmtree(backup.parent, ignore_errors=True)


def get_latest_txadmin_release() -> tuple[str, str]:
    """Fetches the latest stable txAdmin release from GitHub. Returns
    (version, monitor.zip download URL)."""
    raw = http_get(TXADMIN_LATEST_RELEASE_API)
    data = json.loads(raw)
    version = str(data.get("tag_name", "")).lstrip("v")
    asset = next((a for a in data.get("assets", []) if a.get("name") == "monitor.zip"), None)
    if not version or asset is None:
        raise FivemError(
            f"Could not determine the latest txAdmin release from {TXADMIN_LATEST_RELEASE_API} "
            "(the API response may have changed)."
        )
    return version, asset["browser_download_url"]


def install_txadmin(artifact_dir: Path, archive: Path, log_cb=None) -> None:
    """Extracts a txAdmin monitor.zip release into an existing FXServer
    install's system_resources/monitor, replacing whatever is there."""
    monitor = _monitor_dir(artifact_dir)
    if monitor is None:
        raise FivemError(
            f"'{artifact_dir}' is not a recognized FXServer install "
            "(expected a 'server' or 'alpine' folder)."
        )
    if not monitor.parent.exists():
        raise FivemError(
            f"No system_resources folder found in '{artifact_dir}' - "
            "is FXServer actually installed there?"
        )
    if monitor.exists():
        if log_cb:
            log_cb(f"Removing old txAdmin: {monitor}")
        shutil.rmtree(monitor)
    monitor.mkdir(parents=True, exist_ok=True)
    if log_cb:
        log_cb(f"Extracting txAdmin to: {monitor}")
    with zipfile.ZipFile(archive) as z:
        z.extractall(monitor)


def delete_path(path: Path) -> None:
    """Deletes a file, or recursively deletes a folder. Raises OSError on failure."""
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def remove_old(artifact_dir: Path, other_dir: Path | None, log_cb=None):
    if other_dir is not None and other_dir.exists():
        if log_cb:
            log_cb(f"Removing previous installation of the other platform: {other_dir}")
        shutil.rmtree(other_dir)
    if artifact_dir.exists():
        if log_cb:
            log_cb(f"Removing old artifact: {artifact_dir}")
        shutil.rmtree(artifact_dir)


def extract_windows(archive: Path, artifact_dir: Path, other_dir: Path | None, log_cb=None):
    remove_old(artifact_dir, other_dir, log_cb)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if log_cb:
        log_cb(f"Extracting to: {artifact_dir}")
    with zipfile.ZipFile(archive) as z:
        z.extractall(artifact_dir)


def extract_linux(archive: Path, artifact_dir: Path, extraction_parent: Path,
                   other_dir: Path | None, run_sh_resolver, log_cb=None):
    """run_sh_resolver(old_bytes, new_bytes) -> bool (True = overwrite with the new one)."""
    remove_old(artifact_dir, other_dir, log_cb)
    extraction_parent.mkdir(parents=True, exist_ok=True)

    if log_cb:
        log_cb(f"Extracting to: {extraction_parent}")
    with tarfile.open(archive, mode="r:xz") as tar:
        members = tar.getmembers()
        run_sh_member = next((m for m in members if m.name == "run.sh"), None)
        other_members = [m for m in members if m.name != "run.sh"]
        # The FiveM linux artifact contains a mini rootfs (alpine/) with absolute
        # symlinks (e.g. /lib/...) - these are intentional in this official,
        # trusted archive, so we need the fully-trusted filter, otherwise
        # tarfile would reject the extraction.
        tar.extractall(extraction_parent, members=other_members, filter="fully_trusted")

        if run_sh_member is not None:
            new_content = tar.extractfile(run_sh_member).read()
            _handle_run_sh(new_content, extraction_parent / "run.sh", run_sh_member.mode,
                            run_sh_resolver, log_cb)


def _handle_run_sh(new_content: bytes, dest: Path, mode: int, run_sh_resolver, log_cb=None):
    if not dest.exists():
        dest.write_bytes(new_content)
        dest.chmod(mode)
        return

    old_content = dest.read_bytes()
    if old_content == new_content:
        return

    if run_sh_resolver(old_content, new_content):
        dest.write_bytes(new_content)
        dest.chmod(mode)
        if log_cb:
            log_cb("run.sh overwritten.")
    else:
        new_path = dest.with_name("run.sh.new")
        new_path.write_bytes(new_content)
        new_path.chmod(mode)
        if log_cb:
            log_cb(f"Existing run.sh was kept, the new version was written to: {new_path}")
