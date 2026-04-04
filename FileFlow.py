import os
import shutil
import customtkinter as ctk
from tkinter import filedialog
import datetime
import json
import sys

# -------------------------------
# Theme Setup
# -------------------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# -------------------------------
# Resource Path (FIX FOR .EXE)
# -------------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# -------------------------------
# Global Stats
# -------------------------------
stats = {
    "total": 0,
    "categories": {}
}

# -------------------------------
# Logging
# -------------------------------
def log_action(message):
    with open("history.txt", "a") as f:
        time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"{time} - {message}\n")

# -------------------------------
# Config
# -------------------------------
def load_categories():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_categories(data):
    with open("config.json", "w") as f:
        json.dump(data, f, indent=4)

# -------------------------------
# Folder Memory
# -------------------------------
def save_last_folder(folder):
    with open("last_folder.txt", "w") as f:
        f.write(folder)

def load_last_folder():
    try:
        with open("last_folder.txt", "r") as f:
            return f.read()
    except:
        return ""

# -------------------------------
# Organizer Logic
# -------------------------------
def organize_files():
    folder = folder_path.get()

    if not folder:
        status_label.configure(text="Select a folder", text_color="orange")
        return

    file_types = load_categories()

    if not file_types:
        status_label.configure(text="No config file found", text_color="red")
        return

    stats["total"] = 0
    stats["categories"] = {}

    moved = 0

    for file in os.listdir(folder):
        file_path = os.path.join(folder, file)

        if os.path.isdir(file_path):
            continue

        _, ext = os.path.splitext(file)

        for category, extensions in file_types.items():
            if ext.lower() in extensions:
                target = os.path.join(folder, category)
                os.makedirs(target, exist_ok=True)

                new_path = os.path.join(target, file)

                count = 1
                while os.path.exists(new_path):
                    name, extension = os.path.splitext(file)
                    new_path = os.path.join(target, f"{name}_{count}{extension}")
                    count += 1

                try:
                    shutil.move(file_path, new_path)
                    log_action(f"Moved '{file}' → '{category}'")

                    stats["total"] += 1
                    stats["categories"][category] = stats["categories"].get(category, 0) + 1
                    moved += 1
                except Exception as e:
                    log_action(f"Error: {str(e)}")
                break

    status_label.configure(text=f"Organized {moved} files", text_color="green")

    summary = " | ".join([f"{k}: {v}" for k, v in stats["categories"].items()])
    stats_label.configure(text=f"{stats['total']} files → {summary if summary else 'No data'}")

# -------------------------------
# UI Navigation
# -------------------------------
def show_frame(frame):
    frame.tkraise()

# -------------------------------
# History Page
# -------------------------------
def load_history():
    try:
        with open("history.txt", "r") as f:
            content = f.read()
    except:
        content = "No history yet."

    history_textbox.delete("0.0", "end")
    history_textbox.insert("0.0", content)

def clear_history():
    open("history.txt", "w").close()
    history_textbox.delete("0.0", "end")

# -------------------------------
# Settings Page
# -------------------------------
def load_settings_ui():
    for widget in settings_frame.winfo_children():
        widget.destroy()

    title = ctk.CTkLabel(settings_frame, text="Settings", font=("Arial", 24, "bold"))
    title.pack(pady=10)

    categories = load_categories()
    textboxes = {}

    for category, extensions in categories.items():
        frame = ctk.CTkFrame(settings_frame)
        frame.pack(fill="x", padx=10, pady=5)

        label = ctk.CTkLabel(frame, text=category, width=120)
        label.pack(side="left", padx=5)

        entry = ctk.CTkEntry(frame)
        entry.insert(0, ", ".join(extensions))
        entry.pack(side="left", padx=5)

        textboxes[category] = entry

    def save_changes():
        new_data = {}
        for category, entry in textboxes.items():
            new_data[category] = entry.get().replace(" ", "").split(",")

        save_categories(new_data)
        status_label.configure(text="Settings saved", text_color="green")

    save_btn = ctk.CTkButton(settings_frame, text="Save", command=save_changes)
    save_btn.pack(pady=20)

# -------------------------------
# MAIN APP (WRAPPED)
# -------------------------------
def launch_main_app():
    global app, folder_path, status_label, stats_label
    global dashboard_frame, history_frame, settings_frame, history_textbox

    app = ctk.CTk()
    app.geometry("900x550")
    app.title("FileFlow")

    try:
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            app.iconbitmap(icon_path)
    except:
        pass

    # Sidebar
    sidebar = ctk.CTkFrame(app, width=200)
    sidebar.pack(side="left", fill="y")

    logo = ctk.CTkLabel(sidebar, text="FileFlow", font=("Arial", 18, "bold"))
    logo.pack(pady=20)

    # Content
    content = ctk.CTkFrame(app)
    content.pack(side="right", fill="both", expand=True)

    dashboard_frame = ctk.CTkFrame(content)
    history_frame = ctk.CTkFrame(content)
    settings_frame = ctk.CTkFrame(content)

    for frame in (dashboard_frame, history_frame, settings_frame):
        frame.place(relwidth=1, relheight=1)

    # Sidebar buttons
    ctk.CTkButton(sidebar, text="Dashboard", command=lambda: show_frame(dashboard_frame)).pack(pady=10)
    ctk.CTkButton(sidebar, text="History", command=lambda: [show_frame(history_frame), load_history()]).pack(pady=10)
    ctk.CTkButton(sidebar, text="Settings", command=lambda: [show_frame(settings_frame), load_settings_ui()]).pack(pady=10)

    # Dashboard
    ctk.CTkLabel(dashboard_frame, text="Dashboard", font=("Arial", 26, "bold")).pack(anchor="w", padx=20, pady=10)

    folder_path = ctk.StringVar()
    folder_path.set(load_last_folder())

    ctk.CTkEntry(dashboard_frame, textvariable=folder_path, width=500).pack(pady=10)

    ctk.CTkButton(
        dashboard_frame,
        text="Browse Folder",
        command=lambda: [folder_path.set(filedialog.askdirectory()), save_last_folder(folder_path.get())]
    ).pack(pady=10)

    ctk.CTkButton(dashboard_frame, text="Organize Files", command=organize_files).pack(pady=20)

    status_label = ctk.CTkLabel(dashboard_frame, text="Ready")
    status_label.pack()

    stats_label = ctk.CTkLabel(dashboard_frame, text="No data yet")
    stats_label.pack()

    # History
    ctk.CTkLabel(history_frame, text="History", font=("Arial", 24, "bold")).pack(pady=10)

    history_textbox = ctk.CTkTextbox(history_frame)
    history_textbox.pack(expand=True, fill="both", padx=20, pady=10)

    ctk.CTkButton(history_frame, text="Clear History", command=clear_history).pack(pady=10)

    show_frame(dashboard_frame)
    app.mainloop()

# -------------------------------
# SPLASH SCREEN
# -------------------------------
class SplashScreen(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.geometry("500x300")
        self.overrideredirect(True)
        self.eval('tk::PlaceWindow . center')

        self.configure(fg_color="#1E1E1E")

        ctk.CTkLabel(self, text="FileFlow", font=("Arial", 32, "bold")).pack(pady=(80, 10))
        ctk.CTkLabel(self, text="Smart File Organizer").pack(pady=(0, 20))

        self.progress = ctk.CTkProgressBar(self, width=250)
        self.progress.pack(pady=10)
        self.progress.set(0)

        self.after(300, self.load)

    def load(self):
        for i in range(100):
            self.progress.set(i / 100)
            self.update_idletasks()
            self.after(10)

        self.destroy()
        launch_main_app()

# -------------------------------
# START APP
# -------------------------------
if __name__ == "__main__":
    splash = SplashScreen()
    splash.mainloop()