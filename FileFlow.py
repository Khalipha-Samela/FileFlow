"""FileFlow - sort the loose files in a folder into category folders."""

import os
import queue
import sys
import threading
from collections import Counter
from tkinter import filedialog, messagebox

import customtkinter as ctk

from organizer import (
    DEFAULT_CATEGORIES,
    Organizer,
    Settings,
    data_dir,
    normalize_extensions,
    quick_folders,
    valid_category_name,
)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

BG = "#F4F5F6"          # window canvas
SIDEBAR = "#E7EAED"     # navigation rail
PANEL = "#FFFFFF"       # inputs and content panels
HOVER = "#EDEFF1"       # hover fill on quiet buttons
LINE = "#D3D8DD"        # hairlines and borders
INK = "#1E2429"         # primary text
MUTED = "#626C76"       # secondary text
FAINT = "#9AA3AB"       # disabled text
ACCENT = "#1F6F6B"      # the single accent, used for the main action only
ACCENT_HOVER = "#185A57"
STATUS = {"muted": MUTED, "ok": "#2B7A4B", "warn": "#94650F", "error": "#B3423A"}

FAMILY = {"win32": "Segoe UI", "darwin": "Helvetica Neue"}.get(sys.platform, "DejaVu Sans")
MONO = {"win32": "Consolas", "darwin": "Menlo"}.get(sys.platform, "DejaVu Sans Mono")

RADIUS = 4
PREVIEW_LIMIT = 500


def resource_path(relative_path):
    """Resolve bundled files, including inside a PyInstaller .exe."""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)


def font(size=13, weight="normal", mono=False):
    return ctk.CTkFont(family=MONO if mono else FAMILY, size=size, weight=weight)


# ---------------------------------------------------------------------------
# Small widget factories, so every screen shares one look
# ---------------------------------------------------------------------------

def primary_button(parent, text, command, width=130):
    return ctk.CTkButton(
        parent, text=text, command=command, width=width, height=34,
        corner_radius=RADIUS, font=font(13), fg_color=ACCENT, hover_color=ACCENT_HOVER,
        text_color="#FFFFFF", text_color_disabled="#BFD6D4",
    )


def quiet_button(parent, text, command, width=110):
    return ctk.CTkButton(
        parent, text=text, command=command, width=width, height=34,
        corner_radius=RADIUS, font=font(13), fg_color=PANEL, hover_color=HOVER,
        border_width=1, border_color=LINE, text_color=INK, text_color_disabled=FAINT,
    )


def chip_button(parent, text, command):
    return ctk.CTkButton(
        parent, text=text, command=command, width=90, height=28, corner_radius=RADIUS,
        font=font(12), fg_color=PANEL, hover_color=HOVER, border_width=1, border_color=LINE,
        text_color=INK, text_color_disabled=FAINT,
    )


def text_entry(parent, **options):
    return ctk.CTkEntry(
        parent, height=34, corner_radius=RADIUS, border_width=1, border_color=LINE,
        fg_color=PANEL, text_color=INK, font=font(13), **options,
    )


def panel(parent):
    return ctk.CTkFrame(parent, fg_color=PANEL, border_width=1, border_color=LINE, corner_radius=RADIUS)


def read_only_text(parent):
    box = ctk.CTkTextbox(
        parent, fg_color=PANEL, text_color=INK, font=font(12, mono=True), border_width=0,
        corner_radius=RADIUS, scrollbar_button_color=LINE, scrollbar_button_hover_color=FAINT,
        wrap="none",
    )
    box.configure(state="disabled")
    return box


def set_text(box, text):
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.insert("1.0", text)
    box.configure(state="disabled")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

class Page(ctk.CTkFrame):
    title = ""
    subtitle = ""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self.app = app
        self.columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=self.title, font=font(20, "bold"), text_color=INK, anchor="w").grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text=self.subtitle, font=font(13), text_color=MUTED, anchor="w").grid(
            row=1, column=0, sticky="w", pady=(2, 22))

    def on_show(self):
        """Called each time the page is brought to the front."""


class OrganizePage(Page):
    title = "Organize"
    subtitle = "Sort the loose files in a folder into category folders."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.busy = False
        self.quick_buttons = []
        self._events = queue.Queue()
        self.rowconfigure(5, weight=1)

        ctk.CTkLabel(self, text="Folder", font=font(13, "bold"), text_color=INK, anchor="w").grid(
            row=2, column=0, sticky="w", pady=(0, 6))

        picker = ctk.CTkFrame(self, fg_color="transparent")
        picker.grid(row=3, column=0, sticky="ew")
        picker.columnconfigure(0, weight=1)
        self.folder = ctk.StringVar(value=app.settings.last_folder)
        text_entry(picker, textvariable=self.folder).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        quiet_button(picker, "Choose folder", self.browse, width=120).grid(row=0, column=1)

        folders = quick_folders()
        if folders:
            quick = ctk.CTkFrame(picker, fg_color="transparent")
            quick.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
            ctk.CTkLabel(quick, text="Quick access", font=font(12), text_color=MUTED).pack(
                side="left", padx=(0, 10))
            for name, path in folders:
                button = chip_button(quick, name, lambda target=path: self.pick(target))
                button.pack(side="left", padx=(0, 6))
                self.quick_buttons.append(button)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", pady=(14, 18))
        actions.columnconfigure(2, weight=1)
        self.preview_button = quiet_button(actions, "Preview", self.preview, width=100)
        self.preview_button.grid(row=0, column=0, padx=(0, 8))
        self.organize_button = primary_button(actions, "Organize files", self.organize, width=130)
        self.organize_button.grid(row=0, column=1)
        self.undo_button = quiet_button(actions, "Undo last run", self.undo, width=120)
        self.undo_button.grid(row=0, column=3)

        results = ctk.CTkFrame(self, fg_color="transparent")
        results.grid(row=5, column=0, sticky="nsew")
        results.columnconfigure(0, weight=1)
        results.rowconfigure(1, weight=1)
        self.summary = ctk.CTkLabel(results, text="Nothing previewed yet", font=font(13, "bold"),
                                    text_color=INK, anchor="w")
        self.summary.grid(row=0, column=0, sticky="w", pady=(0, 6))
        frame = panel(results)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.listing = read_only_text(frame)
        self.listing.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        set_text(self.listing, "Choose a folder, then select Preview to see which files will move.")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=6, column=0, sticky="ew", pady=(14, 0))
        footer.columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(footer, text="Ready", font=font(12), text_color=MUTED, anchor="w")
        self.status.grid(row=0, column=0, sticky="w")
        self.progress = ctk.CTkProgressBar(footer, height=3, corner_radius=0, fg_color=LINE,
                                           progress_color=ACCENT)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.progress.set(0)

    # -- helpers -----------------------------------------------------------

    def on_show(self):
        self._refresh_buttons()

    def set_status(self, text, kind="muted"):
        self.status.configure(text=text, text_color=STATUS[kind])

    def _refresh_buttons(self):
        state = "disabled" if self.busy else "normal"
        self.preview_button.configure(state=state)
        self.organize_button.configure(state=state)
        can_undo = self.app.organizer.last_undoable() is not None
        self.undo_button.configure(state="normal" if can_undo and not self.busy else "disabled")
        for button in self.quick_buttons:
            button.configure(state=state)

    def _valid_folder(self):
        folder = self.folder.get().strip()
        if not folder:
            self.set_status("Choose a folder first.", "warn")
            return None
        if not os.path.isdir(folder):
            self.set_status("That folder doesn't exist. Check the path or choose another.", "error")
            return None
        return folder

    def _remember(self, folder):
        self.app.settings.last_folder = folder
        try:
            self.app.settings.save()
        except OSError:
            pass

    def _show_plan(self, moves):
        if not moves:
            self.summary.configure(text="Nothing to move")
            set_text(self.listing, "No files in this folder match your categories.")
            return
        counts = Counter(move.category for move in moves)
        noun = "file" if len(moves) == 1 else "files"
        self.summary.configure(text=f"{len(moves)} {noun} to move")
        lines = [f"{move.category:<16}{move.src.name}" for move in moves[:PREVIEW_LIMIT]]
        if len(moves) > PREVIEW_LIMIT:
            lines.append(f"... and {len(moves) - PREVIEW_LIMIT} more")
        lines += ["", "By category:"] + [f"  {name:<14}{count}" for name, count in sorted(counts.items())]
        set_text(self.listing, "\n".join(lines))

    # -- actions -----------------------------------------------------------

    def browse(self):
        options = {}
        if os.path.isdir(self.folder.get()):
            options["initialdir"] = self.folder.get()
        chosen = filedialog.askdirectory(**options)
        if chosen:  # an empty string means the dialog was cancelled
            self.folder.set(chosen)
            self._remember(chosen)

    def pick(self, path):
        """Quick access: point at a common folder and show what would move."""
        if self.busy:
            return
        self.folder.set(str(path))
        self._remember(str(path))
        self.preview()

    def preview(self):
        folder = self._valid_folder()
        if not folder:
            return
        try:
            moves = self.app.organizer.plan(folder)
        except ValueError as error:
            self.set_status(str(error), "error")
            return
        self._show_plan(moves)
        self.set_status("Preview ready. Nothing has been moved." if moves else "No matching files.")

    def organize(self):
        folder = self._valid_folder()
        if not folder:
            return
        try:
            moves = self.app.organizer.plan(folder)
        except ValueError as error:
            self.set_status(str(error), "error")
            return
        self._show_plan(moves)
        if not moves:
            self.set_status("No matching files.")
            return
        noun = "file" if len(moves) == 1 else "files"
        confirmed = messagebox.askyesno(
            "Organize files",
            f"Move {len(moves)} {noun} into category folders inside:\n\n{folder}\n\n"
            "You can undo this afterwards.",
            parent=self.app,
        )
        if not confirmed:
            return
        self._remember(folder)
        self._start(lambda progress: self.app.organizer.run(folder, progress),
                    self._organized, "Moving files")

    def undo(self):
        run = self.app.organizer.last_undoable()
        if run is None:
            return
        count = len(run["moves"])
        noun = "file" if count == 1 else "files"
        confirmed = messagebox.askyesno(
            "Undo last run",
            f"Move {count} {noun} back to where they were?\n\n{run['folder']}\nOrganized on {run['time']}",
            parent=self.app,
        )
        if not confirmed:
            return
        self._start(lambda progress: self.app.organizer.undo_last(progress),
                    self._undone, "Restoring files")

    # -- background work ---------------------------------------------------

    def _start(self, work, on_done, label):
        self.busy = True
        self._refresh_buttons()
        self.set_status(label + "...")
        self.progress.set(0)

        def target():
            try:
                outcome = work(lambda done, total: self._events.put(("progress", done, total)))
            except Exception as error:  # surfaced in the UI rather than lost in the thread
                outcome = error
            self._events.put(("done", outcome))

        threading.Thread(target=target, daemon=True).start()
        self.after(50, lambda: self._poll(on_done))

    def _poll(self, on_done):
        outcome, finished = None, False
        while True:
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            if event[0] == "progress":
                _, done, total = event
                self.progress.set(done / total if total else 1)
            else:
                outcome, finished = event[1], True
                break
        if finished:
            self.busy = False
            self.progress.set(0)
            self._refresh_buttons()
            on_done(outcome)
        else:
            self.after(50, lambda: self._poll(on_done))

    def _organized(self, result):
        if isinstance(result, Exception):
            self.set_status(f"Couldn't finish: {result}", "error")
            return
        noun = "file" if result.moved == 1 else "files"
        self.summary.configure(text=f"Moved {result.moved} {noun}")
        lines = [f"{name:<16}{count}" for name, count in sorted(result.counts.items())]
        if result.failed:
            lines += ["", "Could not move:"] + [f"  {item}" for item in result.failed[:50]]
        set_text(self.listing, "\n".join(lines) or "No files were moved.")
        if result.failed:
            self.set_status(f"Moved {result.moved}, {len(result.failed)} failed. Details are in Activity.", "warn")
        else:
            self.set_status("Done. You can undo this run at any time.", "ok")

    def _undone(self, result):
        if isinstance(result, Exception):
            self.set_status(f"Couldn't undo: {result}", "error")
            return
        noun = "file" if result.restored == 1 else "files"
        self.summary.configure(text=f"Restored {result.restored} {noun}")
        set_text(self.listing, "Files are back where they started.")
        if result.skipped:
            self.set_status(f"{result.skipped} could not be restored because they were moved or deleted.", "warn")
        else:
            self.set_status("Undo complete.", "ok")


class ActivityPage(Page):
    title = "Activity"
    subtitle = "Every file FileFlow has moved or restored."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.rowconfigure(2, weight=1)
        frame = panel(self)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.log = read_only_text(frame)
        self.log.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="e", pady=(14, 0))
        quiet_button(footer, "Clear log", self.clear, width=100).pack()

    def on_show(self):
        set_text(self.log, self.app.organizer.read_log() or "No activity yet. Organize a folder and it will appear here.")
        self.log.see("end")

    def clear(self):
        if messagebox.askyesno("Clear log", "Clear the activity log? Undo history is not affected.", parent=self.app):
            self.app.organizer.clear_log()
            self.on_show()


class CategoriesPage(Page):
    title = "Categories"
    subtitle = "Files are matched by extension. Separate extensions with commas."

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.rows = []
        self.rowconfigure(2, weight=1)

        frame = panel(self)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 0))
        header.columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Folder name", width=160, anchor="w", font=font(12), text_color=MUTED).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(header, text="Extensions", anchor="w", font=font(12), text_color=MUTED).grid(
            row=0, column=1, sticky="w", padx=(8, 0))

        self.list = ctk.CTkScrollableFrame(frame, fg_color="transparent", scrollbar_button_color=LINE,
                                           scrollbar_button_hover_color=FAINT)
        self.list.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 0))

        options = ctk.CTkFrame(frame, fg_color="transparent")
        options.grid(row=2, column=0, sticky="ew", padx=16, pady=12)
        quiet_button(options, "Add category", self.add_row, width=120).pack(side="left")
        self.other = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(options, text='Move unmatched files into "Other"', variable=self.other, font=font(13),
                      text_color=INK, progress_color=ACCENT, button_color=PANEL, button_hover_color=HOVER,
                      fg_color=LINE).pack(side="right")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        footer.columnconfigure(0, weight=1)
        self.message = ctk.CTkLabel(footer, text="", font=font(12), text_color=MUTED, anchor="w")
        self.message.grid(row=0, column=0, sticky="w")
        quiet_button(footer, "Restore defaults", self.restore_defaults, width=130).grid(row=0, column=1, padx=(8, 8))
        primary_button(footer, "Save changes", self.save, width=120).grid(row=0, column=2)

    def on_show(self):
        self._load_rows(self.app.settings.categories)
        self.other.set(self.app.settings.sort_unmatched)
        self._say("")

    def _say(self, text, kind="muted"):
        self.message.configure(text=text, text_color=STATUS[kind])

    def _load_rows(self, categories):
        for row, _, _ in self.rows:
            row.destroy()
        self.rows = []
        for name, extensions in categories.items():
            self.add_row(name, ", ".join(extensions))

    def add_row(self, name="", extensions=""):
        row = ctk.CTkFrame(self.list, fg_color="transparent")
        row.pack(fill="x", pady=3)
        row.columnconfigure(1, weight=1)
        name_entry = text_entry(row, width=160)
        name_entry.grid(row=0, column=0)
        ext_entry = text_entry(row)
        ext_entry.grid(row=0, column=1, sticky="ew", padx=8)
        ctk.CTkButton(row, text="Remove", width=70, height=34, corner_radius=RADIUS, font=font(13),
                      fg_color="transparent", hover_color=HOVER, text_color=MUTED,
                      command=lambda frame=row: self.remove_row(frame)).grid(row=0, column=2)
        if name:
            name_entry.insert(0, name)
        if extensions:
            ext_entry.insert(0, extensions)
        self.rows.append((row, name_entry, ext_entry))

    def remove_row(self, frame):
        self.rows = [entry for entry in self.rows if entry[0] is not frame]
        frame.destroy()

    def restore_defaults(self):
        if messagebox.askyesno("Restore defaults", "Replace the list with the default categories?", parent=self.app):
            self._load_rows(DEFAULT_CATEGORIES)
            self._say("Defaults loaded. Select Save changes to keep them.")

    def save(self):
        categories, seen = {}, set()
        for _, name_entry, ext_entry in self.rows:
            name = name_entry.get().strip()
            extensions = normalize_extensions(ext_entry.get())
            if not name and not extensions:
                continue  # ignore blank rows
            if not name:
                self._say("Every category needs a folder name.", "error")
                return
            if not valid_category_name(name):
                self._say(f'"{name}" can\'t be used as a folder name. Avoid \\ / : * ? " < > |', "error")
                return
            if name.lower() in seen:
                self._say(f'"{name}" appears twice. Category names must be unique.', "error")
                return
            if not extensions:
                self._say(f'"{name}" needs at least one extension.', "error")
                return
            seen.add(name.lower())
            categories[name] = extensions
        if not categories:
            self._say("Add at least one category.", "error")
            return

        settings = self.app.settings
        settings.categories = categories
        settings.sort_unmatched = self.other.get()
        try:
            settings.save()
        except OSError as error:
            self._say(f"Couldn't save: {error.strerror or error}", "error")
            return
        self._load_rows(categories)  # show the cleaned-up extensions
        self._say("Changes saved.", "ok")


# ---------------------------------------------------------------------------
# Application shell
# ---------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FileFlow")
        self.geometry("980x640")
        self.minsize(860, 560)
        self.configure(fg_color=BG)
        try:
            icon = resource_path("icon.ico")
            if os.path.exists(icon):
                self.iconbitmap(icon)
        except Exception:
            pass

        directory = data_dir()
        self.settings = Settings(directory)
        self.organizer = Organizer(self.settings, directory)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._build_sidebar()

        content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew", padx=36, pady=30)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.pages = {
            "organize": OrganizePage(content, self),
            "activity": ActivityPage(content, self),
            "categories": CategoriesPage(content, self),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self.show("organize")

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=200, fg_color=SIDEBAR, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        ctk.CTkLabel(sidebar, text="FileFlow", font=font(17, "bold"), text_color=INK, anchor="w").pack(
            fill="x", padx=22, pady=(28, 24))

        self.nav = {}
        for key, label in (("organize", "Organize"), ("activity", "Activity"), ("categories", "Categories")):
            button = ctk.CTkButton(
                sidebar, text=label, anchor="w", height=36, corner_radius=RADIUS, font=font(13),
                fg_color="transparent", hover_color=HOVER, text_color=MUTED,
                command=lambda name=key: self.show(name),
            )
            button.pack(fill="x", padx=12, pady=1)
            self.nav[key] = button

    def show(self, key):
        for name, button in self.nav.items():
            active = name == key
            button.configure(fg_color=PANEL if active else "transparent",
                             text_color=INK if active else MUTED)
        page = self.pages[key]
        page.tkraise()
        page.on_show()


def main():
    ctk.set_appearance_mode("light")
    App().mainloop()


if __name__ == "__main__":
    main()