#!/usr/bin/env python3
"""FiveM server artifact downloader - Midnight Commander style TUI."""

import tempfile
import threading
from pathlib import Path

from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.coordinate import Coordinate
from textual.markup import escape as escape_markup
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Static,
)

import fivem_common as fc
from version import __version__


def _no_focus(widget):
    """Excludes a widget from the keyboard focus chain (Tab/Shift+Tab), while
    leaving it fully clickable with the mouse. Used on the main screen's
    buttons so Tab only switches between the two panels (artifact table /
    file list), never stopping on a button."""
    widget.can_focus = False
    return widget


# --------------------------------------------------------------------------
# Popup windows (modal screens)
# --------------------------------------------------------------------------

class MessageModal(ModalScreen[None]):
    """Simple info / error popup with a single OK button."""

    DEFAULT_CSS = """
    MessageModal {
        align: center middle;
    }
    MessageModal > Vertical {
        width: 60%;
        max-width: 80;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    MessageModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    MessageModal .body {
        margin-bottom: 1;
    }
    MessageModal Horizontal {
        height: auto;
        align: center middle;
    }
    """

    def __init__(self, title: str, body: str, error: bool = False):
        super().__init__()
        self._title = title
        self._body = body
        self._error = error

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, classes="title", markup=False)
            yield Static(self._body, classes="body", markup=False)
            with Horizontal():
                yield Button("OK", id="ok", variant="error" if self._error else "primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation popup."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    ConfirmModal > Vertical {
        width: 70%;
        max-width: 90;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    ConfirmModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmModal .body {
        margin-bottom: 1;
    }
    ConfirmModal Horizontal {
        height: auto;
        align: center middle;
    }
    ConfirmModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, title: str, body: str, yes_label="Yes", no_label="No", danger=False):
        super().__init__()
        self._title = title
        self._body = body
        self._yes_label = yes_label
        self._no_label = no_label
        self._danger = danger

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, classes="title", markup=False)
            yield Static(self._body, classes="body", markup=False)
            with Horizontal():
                yield Button(self._yes_label, id="yes", variant="error" if self._danger else "primary")
                yield Button(self._no_label, id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)


class VersionInputModal(ModalScreen[int | None]):
    """Prompts for a specific build number."""

    DEFAULT_CSS = """
    VersionInputModal {
        align: center middle;
    }
    VersionInputModal > Vertical {
        width: 50%;
        max-width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    VersionInputModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    VersionInputModal .error {
        color: $error;
        height: auto;
    }
    VersionInputModal Horizontal {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    VersionInputModal Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Enter the build number to download:", classes="title")
            yield Input(placeholder="e.g. 32561", id="version-input")
            yield Static("", id="error-label", classes="error")
            with Horizontal():
                yield Button("Download", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#version-input", Input).focus()

    def _submit(self) -> None:
        raw = self.query_one("#version-input", Input).value.strip()
        if not raw.isdigit():
            self.query_one("#error-label", Static).update("Invalid build number.")
            return
        self.dismiss(int(raw))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self._submit()
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class FolderNameModal(ModalScreen[str | None]):
    """Prompts for a new folder name in the file panel."""

    DEFAULT_CSS = """
    FolderNameModal {
        align: center middle;
    }
    FolderNameModal > Vertical {
        width: 50%;
        max-width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    FolderNameModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    FolderNameModal .error {
        color: $error;
        height: auto;
    }
    FolderNameModal Horizontal {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    FolderNameModal Button {
        margin: 0 1;
    }
    """

    INVALID_CHARS = set('/\\:*?"<>|')

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("New folder name:", classes="title")
            yield Input(placeholder="e.g. fivemserver", id="folder-input")
            yield Static("", id="error-label", classes="error")
            with Horizontal():
                yield Button("Create", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#folder-input", Input).focus()

    def _submit(self) -> None:
        name = self.query_one("#folder-input", Input).value.strip()
        if not name or name in (".", ".."):
            self.query_one("#error-label", Static).update("Enter a valid folder name.")
            return
        if any(ch in self.INVALID_CHARS for ch in name):
            self.query_one("#error-label", Static).update("The folder name cannot contain a path separator.")
            return
        self.dismiss(name)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self._submit()
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class RunShConflictModal(ModalScreen[bool]):
    """Resolves the run.sh conflict: compares the existing content with the new one."""

    DEFAULT_CSS = """
    RunShConflictModal {
        align: center middle;
    }
    RunShConflictModal > Vertical {
        width: 90%;
        height: 80%;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    RunShConflictModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    RunShConflictModal .col-title {
        text-style: bold underline;
    }
    RunShConflictModal Horizontal.columns {
        height: 1fr;
    }
    RunShConflictModal VerticalScroll {
        border: round $primary;
        width: 1fr;
        margin: 0 1;
        padding: 0 1;
    }
    RunShConflictModal Horizontal.buttons {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    RunShConflictModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, old_content: bytes, new_content: bytes):
        super().__init__()
        self._old = old_content.decode("utf-8", errors="replace")
        self._new = new_content.decode("utf-8", errors="replace")

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                "run.sh already exists and differs from the version bundled with the new artifact.",
                classes="title",
            )
            with Horizontal(classes="columns"):
                with VerticalScroll():
                    yield Static("Existing run.sh", classes="col-title")
                    yield Static(self._old, markup=False)
                with VerticalScroll():
                    yield Static("New run.sh", classes="col-title")
                    yield Static(self._new, markup=False)
            with Horizontal(classes="buttons"):
                yield Button("Overwrite with new", id="overwrite", variant="error")
                yield Button("Keep existing", id="keep", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "overwrite")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)


class HelpModal(ModalScreen[None]):
    """F1 help screen: full rundown of the panels, keybindings and behavior."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > Vertical {
        width: 90%;
        max-width: 100;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    HelpModal .title {
        text-style: bold;
        margin-bottom: 1;
    }
    HelpModal .section {
        text-style: bold underline;
        margin-top: 1;
    }
    HelpModal VerticalScroll {
        height: 1fr;
    }
    HelpModal Horizontal {
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    """

    KEYBINDINGS_TEXT = (
        "  F1              Show this help screen\n"
        "  F2              Switch between Windows / Linux builds\n"
        "  F3              Download a specific build number\n"
        "  F4              Check a build's known issues without downloading it\n"
        "  F6              Update txAdmin in the right-hand panel's install\n"
        "  F7              Create a new folder in the right-hand panel\n"
        "  F8              Delete the selected file/folder in the right-hand panel\n"
        "  F10 / q         Quit\n"
        "  Tab / Shift+Tab Switch focus between the artifact list and the file panel\n"
        "  Arrow keys      Move the selection within the focused panel\n"
        "  Enter           Download the selected build / open the selected folder\n"
        "  Escape          Close the current popup"
    )

    LEFT_PANEL_TEXT = (
        "Lists every available build for the selected platform (version + "
        "release date). Builds with known issues are flagged with a red '!' - "
        "select one and press F4 (or check before downloading) to see the "
        "details. The Windows/Linux buttons (or F2) switch platform, "
        "'Specific version...' (or F3) lets you type a build number directly, "
        "and 'Recommended'/'Optional' download the build FiveM's own "
        "runtime.fivem.net page currently designates as such."
    )

    RIGHT_PANEL_TEXT = (
        "A file manager for choosing the destination folder - whatever folder "
        "is open here is where a download gets installed. Double click (or "
        "Enter) opens a folder; 'New folder...' (or F7) creates one; "
        "'Delete' (or F8) deletes the highlighted file/folder after "
        "confirming - this can't be undone, and doesn't work on the '../' "
        "entry. If the current folder is (or directly contains) a 'server' "
        "or 'alpine' install, its detected FXServer artifact build number "
        "and bundled txAdmin version (highlighted in yellow) are shown at "
        "the bottom of the panel's border. 'Update txAdmin' (or F6) updates "
        "just txAdmin in that install to the latest release from "
        "github.com/citizenfx/txAdmin, without touching the FXServer artifact."
    )

    DOWNLOADING_TEXT = (
        "Downloading (via double click, Enter, or the Recommended/Optional "
        "buttons) removes any previous installation in the destination folder "
        "('server' on Windows, 'alpine' on Linux) before installing the new "
        "build. On Linux, if an existing run.sh differs from the new "
        "artifact's, you're asked which one to keep instead of it being "
        "silently overwritten. txAdmin only ever moves forward: if the build "
        "being installed bundles an older txAdmin than the one already "
        "present (e.g. rolling back after a broken newer build), the newer, "
        "already-installed txAdmin is kept automatically and noted in the "
        "'Done' popup."
    )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"FiveM Artifact Downloader — Help (v{__version__})", classes="title")
            with VerticalScroll():
                yield Static("Keybindings", classes="section")
                yield Static(self.KEYBINDINGS_TEXT, markup=False)
                yield Static("Left panel - artifact list", classes="section")
                yield Static(self.LEFT_PANEL_TEXT, markup=False)
                yield Static("Right panel - file manager", classes="section")
                yield Static(self.RIGHT_PANEL_TEXT, markup=False)
                yield Static("Downloading a build", classes="section")
                yield Static(self.DOWNLOADING_TEXT, markup=False)
            with Horizontal():
                yield Button("Close", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key in ("escape", "f1"):
            self.dismiss(None)


class ProgressModal(ModalScreen[None]):
    """Status indicator during download/extraction. Controlled by the background thread."""

    DEFAULT_CSS = """
    ProgressModal {
        align: center middle;
    }
    ProgressModal > Vertical {
        width: 70%;
        max-width: 90;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    ProgressModal .status {
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str):
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self._title, classes="title")
            yield Static("Preparing...", id="status", classes="status")
            yield ProgressBar(id="progress", show_eta=False)

    def set_status(self, text: str) -> None:
        self.query_one("#status", Static).update(text)

    def set_progress(self, downloaded: int, total: int) -> None:
        bar = self.query_one("#progress", ProgressBar)
        mb_done = downloaded // 1024 // 1024
        if total:
            bar.update(total=total, progress=downloaded)
            mb_total = total // 1024 // 1024
            self.set_status(f"Downloading... {mb_done} MB / {mb_total} MB")
        else:
            bar.update(total=None, progress=downloaded)
            self.set_status(f"Downloading... {mb_done} MB")


# --------------------------------------------------------------------------
# Left panel: artifact list
# --------------------------------------------------------------------------

class ArtifactTable(DataTable):
    """DataTable where a single click only moves the cursor (selection), and
    only a genuine double click (chain >= 2) triggers the download - Enter
    always works regardless. The built-in DataTable, by contrast, already
    selects on a single click if it lands on the current cursor row, so that
    behavior has to be overridden.

    IMPORTANT: Textual runs "internal" handlers like `_on_click` from EVERY
    class in the inheritance chain, not just the most derived one (see
    MessagePump._get_dispatch_methods) - so a plain override does NOT silence
    DataTable's own (single-click-selects) behavior. That requires explicitly
    calling `event.prevent_default()`."""

    async def _on_click(self, event) -> None:
        event.prevent_default()
        self._set_hover_cursor(True)
        meta = event.style.meta
        if "row" not in meta or "column" not in meta:
            return
        if not (self.show_cursor and self.cursor_type != "none"):
            return

        row_index = meta["row"]
        column_index = meta["column"]
        if row_index == -1 or column_index == -1:
            return  # header / row-label click - not used here

        self.cursor_coordinate = Coordinate(row_index, column_index)
        self._scroll_cursor_into_view(animate=True)
        event.stop()

        if event.chain >= 2:
            self.action_select_cursor()


class ArtifactPanel(Vertical):
    DEFAULT_CSS = """
    ArtifactPanel {
        width: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    ArtifactPanel .buttons {
        height: 4;
        margin-bottom: 1;
        overflow-x: auto;
        scrollbar-size-horizontal: 1;
    }
    ArtifactPanel .buttons Button {
        margin-right: 1;
        min-width: 10;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(classes="buttons"):
            yield _no_focus(Button("Windows", id="btn-windows", variant="primary"))
            yield _no_focus(Button("Linux", id="btn-linux"))
            yield _no_focus(Button("Specific version...", id="btn-manual"))
            yield _no_focus(Button("Recommended", id="btn-latest-recommended", disabled=True))
            yield _no_focus(Button("Optional", id="btn-latest-optional", disabled=True))
        yield ArtifactTable(id="artifact-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#artifact-table", DataTable)
        table.add_columns("Version", "", "Released")

    def load_builds(self, builds: list[fc.Build], broken_ranges: list[tuple[int, int, str]]) -> None:
        table = self.query_one("#artifact-table", DataTable)
        table.clear()
        for b in builds:
            flagged = fc.find_issues(b.version, broken_ranges)
            flag_cell = Text("!", style="bold #ff1744") if flagged else Text("")
            table.add_row(str(b.version), flag_cell, b.date, key=str(b.version))
        table.focus()

    def set_active_platform(self, platform: str) -> None:
        self.query_one("#btn-windows", Button).variant = "primary" if platform == "windows" else "default"
        self.query_one("#btn-linux", Button).variant = "primary" if platform == "linux" else "default"
        self.border_title = f"FiveM Artifacts ({'Windows' if platform == 'windows' else 'Linux'})"

    def set_official_tags(self, tags: dict[str, tuple[int, str]]) -> None:
        """Updates the "Recommended"/"Optional" buttons with the version
        numbers taken from the official runtime.fivem.net "latest" badges."""
        rec_btn = self.query_one("#btn-latest-recommended", Button)
        if "recommended" in tags:
            rec_btn.label = f"Recommended ({tags['recommended'][0]})"
            rec_btn.disabled = False
        else:
            rec_btn.label = "Recommended"
            rec_btn.disabled = True

        opt_btn = self.query_one("#btn-latest-optional", Button)
        if "optional" in tags:
            opt_btn.label = f"Optional ({tags['optional'][0]})"
            opt_btn.disabled = False
        else:
            opt_btn.label = "Optional"
            opt_btn.disabled = True

        # Button.label is a plain reactive (no layout=True), so changing it
        # alone doesn't widen the button to fit the new (longer) text -
        # force a layout pass or the version number gets clipped off.
        rec_btn.refresh(layout=True)
        opt_btn.refresh(layout=True)


# --------------------------------------------------------------------------
# Right panel: file manager (navigation only)
# --------------------------------------------------------------------------

class NavListItem(ListItem):
    """ListItem where a single click only selects (moves the cursor), and
    only a genuine double click (chain >= 2) opens the folder - Enter always
    works regardless. The built-in ListItem, by contrast, already selects on
    a single click, so that behavior has to be overridden.

    IMPORTANT: Textual runs "internal" handlers like `_on_click` from EVERY
    class in the inheritance chain (see MessagePump._get_dispatch_methods),
    so a plain override alone is not enough - it requires explicitly calling
    `event.prevent_default()` to silence ListItem's own (always-selecting)
    behavior."""

    def _on_click(self, event) -> None:
        event.prevent_default()
        event.stop()
        list_view = self.parent
        if not isinstance(list_view, ListView):
            return
        try:
            list_view.index = list_view._nodes.index(self)
        except ValueError:
            return
        list_view.focus()
        if event.chain >= 2:
            list_view.action_select_cursor()


class FilePanel(Vertical):
    DEFAULT_CSS = """
    FilePanel {
        width: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    FilePanel .buttons {
        height: 4;
        margin-bottom: 1;
        overflow-x: auto;
        scrollbar-size-horizontal: 1;
    }
    FilePanel .buttons Button {
        margin-right: 1;
        min-width: 10;
    }
    """

    def __init__(self, start_path: Path):
        super().__init__()
        self.current_path = start_path
        self._entries: list[Path] = []
        self._has_parent_entry = False

    def compose(self) -> ComposeResult:
        with Horizontal(classes="buttons"):
            yield _no_focus(Button("New folder...", id="btn-new-folder"))
            yield _no_focus(Button("Delete", id="btn-delete", variant="error"))
            yield _no_focus(Button("Update txAdmin", id="btn-update-txadmin"))
        yield ListView(id="file-list")

    def on_mount(self) -> None:
        self.refresh_listing()

    def refresh_listing(self) -> None:
        self.border_title = str(self.current_path)
        list_view = self.query_one("#file-list", ListView)
        list_view.clear()
        self._entries = []

        self._has_parent_entry = self.current_path.parent != self.current_path
        if self._has_parent_entry:
            list_view.append(NavListItem(Label("../")))
            self._entries.append(self.current_path.parent)

        try:
            children = sorted(
                self.current_path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (PermissionError, FileNotFoundError):
            children = []

        for child in children:
            label = f"{child.name}/" if child.is_dir() else child.name
            list_view.append(NavListItem(Label(label)))
            self._entries.append(child)

        list_view.index = 0
        self.border_subtitle = self._detect_versions_label(children)

    def _detect_versions_label(self, children: list[Path]) -> str:
        """Looks for a "server"/"alpine" install (the current folder itself,
        or a direct child) and reports its detected artifact/txAdmin
        versions, so the panel shows what's actually installed there."""
        candidates = [self.current_path] if self.current_path.name in ("server", "alpine") else []
        candidates += [c for c in children if c.is_dir() and c.name in ("server", "alpine")]

        parts = []
        for folder in candidates:
            artifact_version, txadmin_version = fc.detect_installed_versions(folder)
            if artifact_version is None and txadmin_version is None:
                continue
            artifact_text = (
                f"artifact [bold yellow]{artifact_version}[/]" if artifact_version else "artifact unknown"
            )
            txadmin_text = (
                f"txAdmin [bold yellow]{escape_markup(txadmin_version)}[/]"
                if txadmin_version else "txAdmin unknown"
            )
            parts.append(f"{folder.name}: {artifact_text}, {txadmin_text}")
        return " | ".join(parts)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        if index is None or index >= len(self._entries):
            return
        target = self._entries[index]
        if target.is_dir():
            self.current_path = target
            self.refresh_listing()

    def get_selected_entry(self) -> Path | None:
        """Returns the file/folder currently highlighted in the list, or
        None if nothing is selected or it's the '../' navigation entry."""
        index = self.query_one("#file-list", ListView).index
        if index is None or index >= len(self._entries):
            return None
        if self._has_parent_entry and index == 0:
            return None
        return self._entries[index]

    def find_install_dir(self) -> Path | None:
        """Returns the "server"/"alpine" install folder to act on for
        actions like updating txAdmin: the current folder itself if it's
        one, otherwise a direct child of that name."""
        if self.current_path.name in ("server", "alpine"):
            return self.current_path
        for name in ("server", "alpine"):
            candidate = self.current_path / name
            if candidate.is_dir():
                return candidate
        return None


# --------------------------------------------------------------------------
# Main application
# --------------------------------------------------------------------------

class FivemApp(App):
    TITLE = "FiveM Artifact Downloader"
    SUB_TITLE = f"v{__version__}"

    CSS = """
    Screen {
        layout: vertical;
    }
    #main {
        height: 1fr;
    }
    #status-bar {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("f1", "show_help", "Help"),
        ("f2", "toggle_platform", "Windows/Linux"),
        ("f3", "manual_version", "Specific version"),
        ("f4", "check_issues", "Check issues"),
        ("f6", "update_txadmin", "Update txAdmin"),
        ("f7", "create_folder", "New folder"),
        ("f8", "delete_entry", "Delete"),
        ("f10", "quit", "Quit"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.platform = "windows"
        self.builds: list[fc.Build] = []
        self.broken_ranges: list[tuple[int, int, str]] = []
        self.official_tags: dict[str, tuple[int, str]] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield ArtifactPanel()
            yield FilePanel(Path.cwd())
        yield Static("Loading data...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        artifact_panel = self.query_one(ArtifactPanel)
        artifact_panel.set_active_platform(self.platform)
        self.load_data()

    def set_status(self, text: str) -> None:
        self.query_one("#status-bar", Static).update(text)

    # -- help screen -------------------------------------------------------

    def action_show_help(self) -> None:
        self.push_screen(HelpModal())

    # -- data loading ----------------------------------------------------

    @work(thread=True, exclusive=True, group="load")
    def load_data(self) -> None:
        try:
            if not self.broken_ranges:
                self.broken_ranges = fc.get_broken_ranges()
            builds, official_tags = fc.fetch_platform_data(self.platform)
        except fc.FivemError as exc:
            self.call_from_thread(self.set_status, f"Error loading data: {exc}")
            self.call_from_thread(self.push_screen, MessageModal("Error", str(exc), error=True))
            return
        self.builds = builds
        self.official_tags = official_tags
        self.call_from_thread(self._apply_loaded_builds)

    def _apply_loaded_builds(self) -> None:
        panel = self.query_one(ArtifactPanel)
        panel.load_builds(self.builds, self.broken_ranges)
        panel.set_active_platform(self.platform)
        panel.set_official_tags(self.official_tags)
        self.set_status(f"{len(self.builds)} builds loaded ({self.platform}).")

    # -- platform switching ------------------------------------------------

    def action_toggle_platform(self) -> None:
        self.platform = "linux" if self.platform == "windows" else "windows"
        self.set_status("Loading...")
        self.load_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-windows" and self.platform != "windows":
            self.platform = "windows"
            self.set_status("Loading...")
            self.load_data()
        elif event.button.id == "btn-linux" and self.platform != "linux":
            self.platform = "linux"
            self.set_status("Loading...")
            self.load_data()
        elif event.button.id == "btn-manual":
            self.action_manual_version()
        elif event.button.id == "btn-new-folder":
            self.action_create_folder()
        elif event.button.id == "btn-delete":
            self.action_delete_entry()
        elif event.button.id == "btn-update-txadmin":
            self.action_update_txadmin()
        elif event.button.id == "btn-latest-recommended" and "recommended" in self.official_tags:
            self.request_download(self.official_tags["recommended"][0])
        elif event.button.id == "btn-latest-optional" and "optional" in self.official_tags:
            self.request_download(self.official_tags["optional"][0])

    # -- entering a specific version ----------------------------------------

    def action_manual_version(self) -> None:
        def handle(version: int | None) -> None:
            if version is not None:
                self.request_download(version)

        self.push_screen(VersionInputModal(), handle)

    # -- creating a new folder in the right panel ---------------------------

    def action_create_folder(self) -> None:
        file_panel = self.query_one(FilePanel)

        def handle(name: str | None) -> None:
            if not name:
                return
            new_dir = file_panel.current_path / name
            try:
                new_dir.mkdir()
            except FileExistsError:
                self.push_screen(MessageModal("Error", f"Already exists: {new_dir}", error=True))
                return
            except OSError as exc:
                self.push_screen(
                    MessageModal("Error", f"Could not create the folder:\n{exc}", error=True)
                )
                return
            file_panel.refresh_listing()
            self.set_status(f"Folder created: {new_dir}")

        self.push_screen(FolderNameModal(), handle)

    # -- deleting a file/folder in the right panel ---------------------------

    def action_delete_entry(self) -> None:
        file_panel = self.query_one(FilePanel)
        target = file_panel.get_selected_entry()
        if target is None:
            return

        kind = "folder" if target.is_dir() else "file"

        def after_confirm(proceed: bool) -> None:
            if not proceed:
                return
            try:
                fc.delete_path(target)
            except OSError as exc:
                self.push_screen(MessageModal("Error", f"Could not delete:\n{exc}", error=True))
                return
            file_panel.refresh_listing()
            self.set_status(f"Deleted: {target}")

        self.push_screen(
            ConfirmModal(
                "Confirm delete",
                f"Delete this {kind}?\n\n{target}\n\nThis cannot be undone.",
                yes_label="Delete",
                no_label="Cancel",
                danger=True,
            ),
            after_confirm,
        )

    # -- updating txAdmin on its own, independent of the FXServer artifact ----

    def action_update_txadmin(self) -> None:
        file_panel = self.query_one(FilePanel)
        install_dir = file_panel.find_install_dir()
        if install_dir is None:
            self.push_screen(
                MessageModal(
                    "No install found",
                    "No 'server' or 'alpine' FXServer install found here.",
                    error=True,
                )
            )
            return
        self.set_status("Checking latest txAdmin release...")
        self.check_txadmin_update(install_dir)

    @work(thread=True, exclusive=True, group="txadmin-check")
    def check_txadmin_update(self, install_dir: Path) -> None:
        _, current_version = fc.detect_installed_versions(install_dir)
        try:
            latest_version, download_url = fc.get_latest_txadmin_release()
        except fc.FivemError as exc:
            self.call_from_thread(self.set_status, "")
            self.call_from_thread(self.push_screen, MessageModal("Error", str(exc), error=True))
            return

        if current_version and fc.compare_versions(latest_version, current_version) <= 0:
            self.call_from_thread(self.set_status, "")
            self.call_from_thread(
                self.push_screen,
                MessageModal(
                    "Up to date",
                    f"The installed txAdmin ({current_version}) is already the latest "
                    f"available release ({latest_version}) or newer.",
                ),
            )
            return

        def after_confirm(proceed: bool) -> None:
            if proceed:
                self.run_txadmin_update(install_dir, latest_version, download_url)

        body = (
            f"Update txAdmin in:\n{install_dir}\n\n"
            f"{current_version or 'unknown'} -> {latest_version}"
        )
        self.call_from_thread(self.set_status, "")
        self.call_from_thread(
            self.push_screen,
            ConfirmModal("Update txAdmin", body, yes_label="Update"),
            after_confirm,
        )

    @work(thread=True, exclusive=True, group="download")
    def run_txadmin_update(self, install_dir: Path, new_version: str, download_url: str) -> None:
        progress_modal = ProgressModal(f"Updating txAdmin to {new_version}")
        self.call_from_thread(self.push_screen, progress_modal)

        def log(text: str) -> None:
            self.call_from_thread(progress_modal.set_status, text)

        def progress(downloaded: int, total: int) -> None:
            self.call_from_thread(progress_modal.set_progress, downloaded, total)

        try:
            with tempfile.TemporaryDirectory(prefix="fivem-txadmin-") as tmp:
                archive_path = Path(tmp) / "monitor.zip"
                fc.download_file(download_url, archive_path, progress_cb=progress)
                log("Installing...")
                fc.install_txadmin(install_dir, archive_path, log_cb=log)
        except fc.FivemError as exc:
            self.call_from_thread(self.pop_screen)
            self.call_from_thread(self.push_screen, MessageModal("Error", str(exc), error=True))
            return
        except Exception as exc:  # surface unexpected errors too, don't fail silently
            self.call_from_thread(self.pop_screen)
            self.call_from_thread(self.push_screen, MessageModal("Unexpected error", str(exc), error=True))
            return

        self.call_from_thread(self.pop_screen)
        self.call_from_thread(
            self.push_screen,
            MessageModal("Done", f"txAdmin {new_version} installed to:\n{install_dir}"),
        )
        self.call_from_thread(self.query_one(FilePanel).refresh_listing)
        self.call_from_thread(self.set_status, f"Done: txAdmin {new_version} installed to: {install_dir}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        version = int(str(event.row_key.value))
        self.request_download(version)

    # -- checking a build's issues without downloading it ---------------------

    def action_check_issues(self) -> None:
        table = self.query_one(ArtifactTable)
        if table.row_count == 0:
            return
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        version = int(str(row_key.value))
        issues = fc.find_issues(version, self.broken_ranges)
        if issues:
            body = f"Build {version} has known issues:\n\n" + "\n".join(
                f"- {issue}" for issue in issues
            )
            self.push_screen(MessageModal("Known issues", body, error=True))
        else:
            self.push_screen(
                MessageModal("No known issues", f"Build {version} has no known issues.")
            )

    # -- starting a download -------------------------------------------------

    def request_download(self, version: int) -> None:
        match = next((b for b in self.builds if b.version == version), None)
        if match is None:
            self.push_screen(
                MessageModal(
                    "Not found",
                    f"Build {version} was not found in the {self.platform} list.",
                    error=True,
                )
            )
            return

        issues = fc.find_issues(version, self.broken_ranges)

        def after_issue_confirm(proceed: bool) -> None:
            if proceed:
                self._confirm_and_download(match)

        if issues:
            body = f"Build {version} has known issues:\n\n" + "\n".join(
                f"- {issue}" for issue in issues
            )
            self.push_screen(
                ConfirmModal("Warning: broken build", body, yes_label="Download anyway",
                              no_label="Cancel", danger=True),
                after_issue_confirm,
            )
        else:
            self._confirm_and_download(match)

    def _confirm_and_download(self, build: fc.Build) -> None:
        dest_dir = self.query_one(FilePanel).current_path

        def after_confirm(proceed: bool) -> None:
            if proceed:
                self.run_download(build, self.platform, dest_dir)

        self.push_screen(
            ConfirmModal(
                "Confirm download",
                f"Download build {build.version} to:\n{dest_dir}\n\n"
                "Any existing artifact in the destination folder will be removed.",
            ),
            after_confirm,
        )

    # -- download + extraction on a background thread -------------------------

    def ask_confirm_from_thread(self, title: str, body: str, danger: bool = False) -> bool:
        result: dict[str, bool] = {}
        event = threading.Event()

        def show() -> None:
            def handle(value: bool) -> None:
                result["v"] = value
                event.set()

            self.push_screen(ConfirmModal(title, body, danger=danger), handle)

        self.call_from_thread(show)
        event.wait()
        return result.get("v", False)

    def ask_run_sh_from_thread(self, old_content: bytes, new_content: bytes) -> bool:
        result: dict[str, bool] = {}
        event = threading.Event()

        def show() -> None:
            def handle(value: bool) -> None:
                result["v"] = value
                event.set()

            self.push_screen(RunShConflictModal(old_content, new_content), handle)

        self.call_from_thread(show)
        event.wait()
        return result.get("v", False)

    @work(thread=True, exclusive=True, group="download")
    def run_download(self, build: fc.Build, platform: str, dest_dir: Path) -> None:
        progress_modal = ProgressModal(f"Installing build {build.version} ({platform})")
        self.call_from_thread(self.push_screen, progress_modal)

        def log(text: str) -> None:
            self.call_from_thread(progress_modal.set_status, text)

        def progress(downloaded: int, total: int) -> None:
            self.call_from_thread(progress_modal.set_progress, downloaded, total)

        kept_newer_txadmin = False
        old_txadmin_version = None
        txadmin_backup = None
        try:
            artifact_dir, extraction_parent, other_dir = fc.resolve_artifact_dir(dest_dir, platform)
            download_url = fc.build_download_url(build.version, build.build_hash, platform)

            _, old_txadmin_version = fc.detect_installed_versions(artifact_dir)
            txadmin_backup = fc.backup_txadmin(artifact_dir)

            with tempfile.TemporaryDirectory(prefix="fivem-artifact-") as tmp:
                archive_name = "server.zip" if platform == "windows" else "fx.tar.xz"
                archive_path = Path(tmp) / archive_name
                fc.download_file(download_url, archive_path, progress_cb=progress)

                log("Extracting...")
                if platform == "windows":
                    fc.extract_windows(archive_path, artifact_dir, other_dir, log_cb=log)
                else:
                    fc.extract_linux(
                        archive_path, artifact_dir, extraction_parent, other_dir,
                        run_sh_resolver=self.ask_run_sh_from_thread, log_cb=log,
                    )

            # txAdmin can only move forward: if this build bundles an older
            # txAdmin than what was already installed here (e.g. rolling back
            # to an earlier build after a broken newer one), automatically
            # keep the newer, already-installed txAdmin instead of downgrading it.
            if txadmin_backup is not None and old_txadmin_version:
                _, new_txadmin_version = fc.detect_installed_versions(artifact_dir)
                if new_txadmin_version and fc.compare_versions(new_txadmin_version, old_txadmin_version) < 0:
                    log(
                        f"Bundled txAdmin ({new_txadmin_version}) is older than the installed "
                        f"one ({old_txadmin_version}) - keeping the installed version."
                    )
                    fc.restore_txadmin(artifact_dir, txadmin_backup)
                    kept_newer_txadmin = True
        except fc.FivemError as exc:
            self.call_from_thread(self.pop_screen)
            self.call_from_thread(self.push_screen, MessageModal("Error", str(exc), error=True))
            return
        except Exception as exc:  # surface unexpected errors too, don't fail silently
            self.call_from_thread(self.pop_screen)
            self.call_from_thread(self.push_screen, MessageModal("Unexpected error", str(exc), error=True))
            return
        finally:
            if txadmin_backup is not None:
                fc.cleanup_txadmin_backup(txadmin_backup)

        self.call_from_thread(self.pop_screen)
        done_body = f"Build {build.version} installed to:\n{artifact_dir}"
        if kept_newer_txadmin:
            done_body += (
                f"\n\nNote: this build bundles an older txAdmin; the previously "
                f"installed version ({old_txadmin_version}) was kept instead."
            )
        self.call_from_thread(self.push_screen, MessageModal("Done", done_body))
        self.call_from_thread(self.query_one(FilePanel).refresh_listing)
        self.call_from_thread(self.set_status, f"Done: {build.version} installed to: {artifact_dir}")


def main() -> None:
    FivemApp().run()


if __name__ == "__main__":
    main()
