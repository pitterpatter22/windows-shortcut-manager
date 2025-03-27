import json
import logging
import os
import subprocess
import threading
import sys
import webbrowser
import keyboard
import pystray
from pystray import MenuItem as item
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import tkinter.ttk as ttk
from PIL import Image, ImageDraw

# --------------------------
# Dark Theme Colors and Fonts
# --------------------------
BG_COLOR = "#2e2e2e"        # window background
FG_COLOR = "#ffffff"        # text color
BUTTON_BG = "#3e3e3e"       # button background
ENTRY_BG = "#3e3e3e"        # entry widget background
ACCENT_COLOR = "#0078d7"    # accent (for recording feedback)
FONT_NAME = "Segoe UI"
FONT_SIZE = 10
FONT = (FONT_NAME, FONT_SIZE)

# Log level colors for log viewer
LOG_COLORS = {
    "DEBUG": "#aaaaaa",   # light grey
    "INFO": "#ffffff",    # white
    "WARNING": "#ffcc00", # yellow-ish
    "ERROR": "#ff5555",   # light red
    "CRITICAL": "#ff0000" # red
}

# --------------------------
# Configuration and Logging
# --------------------------
CONFIG_FILE = "config.json"
LOG_FILE = "hotkey_manager.log"
hotkey_handles = {}  # mapping of hotkey strings to their registered handles

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

def load_config():
    """Load configuration from the JSON file."""
    if not os.path.exists(CONFIG_FILE):
        default_config = {"hotkeys": []}
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=4)
        logging.info("Created default config file: %s", CONFIG_FILE)
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logging.error("Error loading config file: %s", e)
        return {"hotkeys": []}

# ---------------------
# Hotkey Callback and Registration
# ---------------------
def execute_command(command):
    """Execute a shell command."""
    try:
        subprocess.Popen(command, shell=True)
        logging.info("Executed command: %s", command)
    except Exception as e:
        logging.error("Error executing command '%s': %s", command, e)

def hotkey_callback(action, command, args=""):
    """Return a callback function based on action type."""
    def callback():
        logging.info("Hotkey triggered: action=%s, command=%s, args=%s", action, command, args)
        if action == "shell":
            execute_command(command)
        elif action == "open_link":
            try:
                webbrowser.open(command)
                logging.info("Opened link: %s", command)
            except Exception as e:
                logging.error("Error opening link '%s': %s", command, e)
        elif action == "open_program":
            try:
                # If arguments provided, split into list; otherwise, run the program directly.
                if args.strip():
                    subprocess.Popen([command] + args.split())
                else:
                    subprocess.Popen(command)
                logging.info("Opened program: %s with args: %s", command, args)
            except Exception as e:
                logging.error("Error opening program '%s': %s", command, e)
        else:
            logging.error("Unknown action type: %s", action)
    return callback

def register_hotkeys(config):
    """Register global hotkeys from configuration."""
    global hotkey_handles
    # Unregister previously registered hotkeys.
    for hotkey, handle in hotkey_handles.items():
        try:
            keyboard.remove_hotkey(handle)
            logging.info("Removed hotkey: %s", hotkey)
        except Exception as e:
            logging.error("Error removing hotkey '%s': %s", hotkey, e)
    hotkey_handles = {}

    for entry in config.get("hotkeys", []):
        keys = entry.get("keys")
        action = entry.get("action")
        command = entry.get("command")
        args = entry.get("args", "")
        if not keys or not action or not command:
            logging.warning("Invalid config entry, skipping: %s", entry)
            continue
        try:
            handle = keyboard.add_hotkey(keys, hotkey_callback(action, command, args))
            hotkey_handles[keys] = handle
            logging.info("Registered hotkey: %s -> %s (%s)", keys, command, action)
        except Exception as e:
            logging.error("Error registering hotkey '%s': %s", keys, e)

def reload_config():
    """Reload configuration and re-register hotkeys."""
    logging.info("Reloading configuration.")
    config = load_config()
    register_hotkeys(config)
    logging.info("Configuration reloaded.")

# -----------------------------------
# File Watcher for Configuration File
# -----------------------------------
class ConfigFileEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.basename(event.src_path) == CONFIG_FILE:
            logging.info("Config file modified; reloading configuration.")
            reload_config()

def start_config_watcher():
    event_handler = ConfigFileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()
    logging.info("Started config file watcher.")
    return observer

# -------------------------
# Global Tkinter Root for GUIs
# -------------------------
main_root = tk.Tk()
main_root.withdraw()  # hidden root; all windows will be Toplevel

# -------------------------
# GUI: Add Shortcut Window (Modern, Dark Themed)
# -------------------------
def open_gui():
    window = tk.Toplevel(main_root)
    window.title("Add Hotkey Configuration")
    window.geometry("450x350")
    window.configure(bg=BG_COLOR)
    
    frame = tk.Frame(window, bg=BG_COLOR, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Hotkey entry
    tk.Label(frame, text="Hotkey (e.g., ctrl+shift+a):", bg=BG_COLOR, fg=FG_COLOR, font=FONT)\
        .grid(row=0, column=0, sticky="w")
    keys_entry = tk.Entry(frame, width=30, bg=ENTRY_BG, fg=FG_COLOR, font=FONT)
    keys_entry.grid(row=0, column=1, padx=5, pady=5)
    
    # Recording status
    record_status = tk.Label(frame, text="", bg=BG_COLOR, fg=FG_COLOR, font=FONT)
    record_status.grid(row=1, column=1, sticky="w")
    
    def record_shortcut():
        record_status.config(text="Recording... press your shortcut", fg=ACCENT_COLOR)
        def record():
            try:
                recorded = keyboard.read_hotkey(suppress=False)
                main_root.after(0, lambda: keys_entry.delete(0, tk.END))
                main_root.after(0, lambda: keys_entry.insert(0, recorded))
                main_root.after(0, lambda: record_status.config(text="Recorded", fg=FG_COLOR))
            except Exception as e:
                logging.error("Error recording hotkey: %s", e)
                main_root.after(0, lambda: record_status.config(text="Error", fg=LOG_COLORS["ERROR"]))
        threading.Thread(target=record, daemon=True).start()
    tk.Button(frame, text="Record Shortcut", command=record_shortcut, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
        .grid(row=0, column=2, padx=5, pady=5)
    
    # Action option menu
    tk.Label(frame, text="Action:", bg=BG_COLOR, fg=FG_COLOR, font=FONT)\
        .grid(row=2, column=0, sticky="w")
    action_var = tk.StringVar(frame)
    # Options now include shell, open_link, open_program.
    action_options = ["shell", "open_link", "open_program"]
    action_var.set(action_options[0])
    action_menu = tk.OptionMenu(frame, action_var, *action_options)
    action_menu.config(bg=BUTTON_BG, fg=FG_COLOR, font=FONT)
    action_menu.grid(row=2, column=1, padx=5, pady=5, sticky="w")
    
    # Command field (used differently based on action)
    tk.Label(frame, text="Command / URL / Program:", bg=BG_COLOR, fg=FG_COLOR, font=FONT)\
        .grid(row=3, column=0, sticky="w")
    command_entry = tk.Entry(frame, width=30, bg=ENTRY_BG, fg=FG_COLOR, font=FONT)
    command_entry.grid(row=3, column=1, padx=5, pady=5)
    
    # Browse button (only for open_program)
    browse_button = tk.Button(frame, text="Browse", bg=BUTTON_BG, fg=FG_COLOR, font=FONT,
                              command=lambda: command_entry.delete(0, tk.END) or command_entry.insert(0, filedialog.askopenfilename()))
    # Arguments label and entry (only for open_program)
    args_label = tk.Label(frame, text="Arguments (optional):", bg=BG_COLOR, fg=FG_COLOR, font=FONT)
    args_entry = tk.Entry(frame, width=30, bg=ENTRY_BG, fg=FG_COLOR, font=FONT)
    
    def update_action_fields(*args):
        # If action is open_program, show Browse and Arguments fields; otherwise hide them.
        if action_var.get() == "open_program":
            browse_button.grid(row=3, column=2, padx=5, pady=5)
            args_label.grid(row=4, column=0, sticky="w", pady=(10, 0))
            args_entry.grid(row=4, column=1, padx=5, pady=(10, 5))
        else:
            browse_button.grid_forget()
            args_label.grid_forget()
            args_entry.grid_forget()
    action_var.trace("w", update_action_fields)
    update_action_fields()
    
    def submit():
        keys = keys_entry.get().strip()
        action = action_var.get().strip()
        command = command_entry.get().strip()
        extra_args = args_entry.get().strip() if action == "open_program" else ""
        if not keys or not command:
            messagebox.showerror("Error", "Please fill in all required fields.", parent=window)
            return
        config = load_config()
        new_entry = {"keys": keys, "action": action, "command": command}
        if action == "open_program":
            new_entry["args"] = extra_args
        config["hotkeys"].append(new_entry)
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=4)
            messagebox.showinfo("Success", "Configuration added. Reloading configuration.", parent=window)
            reload_config()
            window.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to write to config file: {e}", parent=window)
    
    tk.Button(frame, text="Submit", command=submit, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
        .grid(row=5, column=0, columnspan=3, pady=20)

# -------------------------
# GUI: Manage Shortcuts Window (Modern, Dark Themed)
# -------------------------
def open_manage_shortcuts():
    window = tk.Toplevel(main_root)
    window.title("Manage Shortcuts")
    window.geometry("600x400")
    window.configure(bg=BG_COLOR)
    
    frame = tk.Frame(window, bg=BG_COLOR, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Treeview", background=BG_COLOR, fieldbackground=BG_COLOR, foreground=FG_COLOR, font=FONT)
    style.configure("Treeview.Heading", background=BUTTON_BG, foreground=FG_COLOR, font=(FONT_NAME, FONT_SIZE, "bold"))
    tree = ttk.Treeview(frame, columns=("Hotkey", "Action", "Command", "Args"), show="headings", selectmode="browse")
    tree.heading("Hotkey", text="Hotkey")
    tree.heading("Action", text="Action")
    tree.heading("Command", text="Command/URL/Program")
    tree.heading("Args", text="Args")
    tree.column("Hotkey", width=100)
    tree.column("Action", width=80)
    tree.column("Command", width=250)
    tree.column("Args", width=100)
    tree.pack(fill=tk.BOTH, expand=True)

    def load_shortcuts():
        for row in tree.get_children():
            tree.delete(row)
        config = load_config()
        for i, entry in enumerate(config.get("hotkeys", [])):
            args_val = entry.get("args", "") if entry.get("action") == "open_program" else ""
            tree.insert("", "end", iid=str(i), values=(entry.get("keys"), entry.get("action"), entry.get("command"), args_val))
    load_shortcuts()

    def edit_shortcut():
        selected = tree.focus()
        if not selected:
            messagebox.showerror("Error", "Please select a shortcut to edit.", parent=window)
            return
        index = int(selected)
        config = load_config()
        entry = config.get("hotkeys", [])[index]
        edit_win = tk.Toplevel(window)
        edit_win.title("Edit Shortcut")
        edit_win.geometry("450x350")
        edit_win.configure(bg=BG_COLOR)
        edit_frame = tk.Frame(edit_win, bg=BG_COLOR, padx=20, pady=20)
        edit_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(edit_frame, text="Hotkey:", bg=BG_COLOR, fg=FG_COLOR, font=FONT)\
            .grid(row=0, column=0, sticky="w")
        hotkey_entry = tk.Entry(edit_frame, width=30, bg=ENTRY_BG, fg=FG_COLOR, font=FONT)
        hotkey_entry.grid(row=0, column=1, padx=5, pady=5)
        hotkey_entry.insert(0, entry.get("keys"))
        
        tk.Label(edit_frame, text="Action:", bg=BG_COLOR, fg=FG_COLOR, font=FONT)\
            .grid(row=1, column=0, sticky="w")
        action_var = tk.StringVar(edit_frame)
        action_options = ["shell", "open_link", "open_program"]
        action_var.set(entry.get("action", "shell"))
        action_menu = tk.OptionMenu(edit_frame, action_var, *action_options)
        action_menu.config(bg=BUTTON_BG, fg=FG_COLOR, font=FONT)
        action_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        tk.Label(edit_frame, text="Command / URL / Program:", bg=BG_COLOR, fg=FG_COLOR, font=FONT)\
            .grid(row=2, column=0, sticky="w")
        command_entry = tk.Entry(edit_frame, width=30, bg=ENTRY_BG, fg=FG_COLOR, font=FONT)
        command_entry.grid(row=2, column=1, padx=5, pady=5)
        command_entry.insert(0, entry.get("command"))
        
        # For open_program action, add Browse button and Arguments field.
        browse_button = tk.Button(edit_frame, text="Browse", bg=BUTTON_BG, fg=FG_COLOR, font=FONT,
                                  command=lambda: command_entry.delete(0, tk.END) or command_entry.insert(0, filedialog.askopenfilename()))
        args_label = tk.Label(edit_frame, text="Arguments (optional):", bg=BG_COLOR, fg=FG_COLOR, font=FONT)
        args_entry = tk.Entry(edit_frame, width=30, bg=ENTRY_BG, fg=FG_COLOR, font=FONT)
        if entry.get("action") == "open_program":
            browse_button.grid(row=2, column=2, padx=5, pady=5)
            args_label.grid(row=3, column=0, sticky="w", pady=(10, 0))
            args_entry.grid(row=3, column=1, padx=5, pady=(10, 5))
            args_entry.insert(0, entry.get("args", ""))
        
        def update_edit_fields(*args):
            if action_var.get() == "open_program":
                browse_button.grid(row=2, column=2, padx=5, pady=5)
                args_label.grid(row=3, column=0, sticky="w", pady=(10, 0))
                args_entry.grid(row=3, column=1, padx=5, pady=(10, 5))
            else:
                browse_button.grid_forget()
                args_label.grid_forget()
                args_entry.grid_forget()
        action_var.trace("w", update_edit_fields)
        update_edit_fields()
        
        def submit_edit():
            new_keys = hotkey_entry.get().strip()
            new_action = action_var.get().strip()
            new_command = command_entry.get().strip()
            new_args = args_entry.get().strip() if new_action == "open_program" else ""
            if not new_keys or not new_command:
                messagebox.showerror("Error", "Please fill in all required fields.", parent=edit_win)
                return
            config["hotkeys"][index] = {"keys": new_keys, "action": new_action, "command": new_command}
            if new_action == "open_program":
                config["hotkeys"][index]["args"] = new_args
            elif "args" in config["hotkeys"][index]:
                del config["hotkeys"][index]["args"]
            try:
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)
                messagebox.showinfo("Success", "Shortcut updated.", parent=edit_win)
                reload_config()
                load_shortcuts()
                edit_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to write to config file: {e}", parent=edit_win)
        
        tk.Button(edit_frame, text="Submit", command=submit_edit, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
            .grid(row=4, column=0, columnspan=3, pady=20)
    
    def remove_shortcut():
        selected = tree.focus()
        if not selected:
            messagebox.showerror("Error", "Please select a shortcut to remove.", parent=window)
            return
        index = int(selected)
        if messagebox.askyesno("Confirm", "Are you sure you want to remove this shortcut?", parent=window):
            config = load_config()
            try:
                del config["hotkeys"][index]
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f, indent=4)
                messagebox.showinfo("Success", "Shortcut removed.", parent=window)
                reload_config()
                load_shortcuts()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update config file: {e}", parent=window)
    
    btn_frame = tk.Frame(frame, bg=BG_COLOR)
    btn_frame.pack(fill=tk.X, pady=10)
    tk.Button(btn_frame, text="Edit", command=edit_shortcut, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
        .pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Remove", command=remove_shortcut, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
        .pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Refresh", command=load_shortcuts, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
        .pack(side=tk.LEFT, padx=5)

# -------------------------
# GUI: Log Viewer Window (Modern, Dark Themed with Colored Logs)
# -------------------------
def open_log_viewer():
    viewer = tk.Toplevel(main_root)
    viewer.title("Log Viewer")
    viewer.geometry("600x400")
    viewer.configure(bg=BG_COLOR)
    
    frame = tk.Frame(viewer, bg=BG_COLOR, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    text_area = scrolledtext.ScrolledText(frame, wrap=tk.WORD, bg=ENTRY_BG, fg=FG_COLOR, font=("Consolas", 10))
    text_area.pack(fill=tk.BOTH, expand=True)
    text_area.config(state="disabled")
    
    for level, color in LOG_COLORS.items():
        text_area.tag_config(level, foreground=color)
    
    def refresh_log():
        try:
            with open(LOG_FILE, "r") as f:
                lines = f.readlines()
            text_area.config(state="normal")
            text_area.delete(1.0, tk.END)
            for line in lines:
                tag = "INFO"
                for level in LOG_COLORS.keys():
                    if f"[{level}]" in line:
                        tag = level
                        break
                text_area.insert(tk.END, line, tag)
            text_area.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Error", f"Could not read log file: {e}", parent=viewer)
    
    tk.Button(frame, text="Refresh", command=refresh_log, bg=BUTTON_BG, fg=FG_COLOR, font=FONT)\
        .pack(pady=10)
    refresh_log()

# -------------------------
# System Tray Icon and Menu
# -------------------------
def open_config_file_gui():
    try:
        os.startfile(CONFIG_FILE)
    except Exception as e:
        logging.error("Error opening config file: %s", e)

def quit_app(icon):
    logging.info("Quitting application.")
    icon.stop()
    os._exit(0)

def create_tray_icon():
    image = Image.new('RGB', (64, 64), color='white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 63, 63), fill="blue")
    menu = (
        item('Reload Config', lambda icon, item: main_root.after(0, reload_config)),
        item('Open Config File', lambda icon, item: main_root.after(0, open_config_file_gui)),
        item('Add Shortcut', lambda icon, item: main_root.after(0, open_gui)),
        item('Manage Shortcuts', lambda icon, item: main_root.after(0, open_manage_shortcuts)),
        item('View Log', lambda icon, item: main_root.after(0, open_log_viewer)),
        item('Quit', lambda icon, item: quit_app(icon))
    )
    icon = pystray.Icon("HotkeyManager", image, "Hotkey Manager", menu)
    return icon

# -------------------------
# Main Application Logic
# -------------------------
def main():
    foreground = ('-foreground' in sys.argv)
    logging.info("Starting Hotkey Manager")
    config = load_config()
    register_hotkeys(config)
    observer = start_config_watcher()
    tray_icon = create_tray_icon()
    tray_thread = threading.Thread(target=tray_icon.run, daemon=True)
    tray_thread.start()
    logging.info("Tray icon started.")

    if foreground:
        main_root.after(0, open_gui)

    main_root.mainloop()
    observer.stop()
    observer.join()

if __name__ == '__main__':
    main()
