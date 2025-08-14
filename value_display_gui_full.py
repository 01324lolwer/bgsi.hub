import tkinter as tk
from tkinter import ttk
import json
import os
import time
import threading
import requests
from datetime import datetime

JSON_PATH = "bgsi_pet_values.json"

class PetValueViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("🐾 BGSI Pet Value Viewer")

        self.dark_mode = False
        self.last_updated = ""
        self.last_modified = None

        self.top_frame = tk.Frame(root)
        self.top_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(self.top_frame, text="🔍 Suche:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.top_frame, textvariable=self.search_var)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<KeyRelease>", self.update_display)

        tk.Label(self.top_frame, text="📊 Sortierung:").pack(side=tk.LEFT, padx=10)
        self.sort_var = tk.StringVar(value="name")
        self.sort_menu = ttk.Combobox(self.top_frame, textvariable=self.sort_var, state="readonly",
                                      values=["name", "normal_value", "shiny_value"])
        self.sort_menu.pack(side=tk.LEFT)
        self.sort_menu.bind("<<ComboboxSelected>>", self.update_display)

        self.refresh_btn = ttk.Button(self.top_frame, text="🔁 Aktualisieren", command=self.manual_update)
        self.refresh_btn.pack(side=tk.RIGHT, padx=5)

        self.theme_btn = ttk.Button(self.top_frame, text="🌙 Dark Mode", command=self.toggle_theme)
        self.theme_btn.pack(side=tk.RIGHT, padx=5)

        self.status_label = tk.Label(root, text="Letzte Aktualisierung: unbekannt", anchor="w")
        self.status_label.pack(fill=tk.X, padx=5, pady=2)

        self.tree = ttk.Treeview(root)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree["columns"] = ("Normal", "Shiny", "Mythic", "Shiny Mythic")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100, anchor="center")
        self.tree.column("#0", width=300, anchor="w")
        self.tree.heading("#0", text="Pet Name")

        self.data = {}
        self.load_data()
        self.update_display()

        threading.Thread(target=self.watch_file_changes, daemon=True).start()
        threading.Thread(target=self.scraper_loop, daemon=True).start()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode

        # Farben definieren
        if self.dark_mode:
            bg_color = "#3a3a3a"
            fg_color = "white"
            entry_bg = "#4a4a4a"
            selected_bg = "#5e5e5e"
            heading_bg = "#3a3a3a"
            heading_fg = "white"
            theme_button_text = "☀️ Light Mode"
        else:
            bg_color = "SystemButtonFace"
            fg_color = "black"
            entry_bg = "white"
            selected_bg = "#cce6ff"
            heading_bg = "SystemButtonFace"
            heading_fg = "black"
            theme_button_text = "🌙 Dark Mode"

        # Root & Hauptbereiche
        self.root.configure(bg=bg_color)
        self.top_frame.configure(bg=bg_color)
        self.status_label.configure(bg=bg_color, fg=fg_color)
        self.theme_btn.configure(text=theme_button_text)

        # Entry
        self.search_entry.configure(bg=entry_bg, fg=fg_color, insertbackground=fg_color)

        # Labels im Top Frame
        for widget in self.top_frame.winfo_children():
            if isinstance(widget, tk.Label):
                widget.configure(bg=bg_color, fg=fg_color)

        # Treeview Farben (ttk Style)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=entry_bg,
                        fieldbackground=entry_bg,
                        foreground=fg_color)
        style.configure("Treeview.Heading",
                        background=heading_bg,
                        foreground=heading_fg)




    def load_data(self):
        try:
            self.last_modified = os.path.getmtime(JSON_PATH)
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"Fehler beim Laden der JSON-Datei: {e}")
            self.data = {}

    def update_display(self, event=None):
        query = self.search_var.get().lower()
        sort_by = self.sort_var.get()
        self.tree.delete(*self.tree.get_children())

        entries = []
        for pet, variants in self.data.items():
            if query in pet.lower():
                normal = variants.get("Normal", "N/A")
                shiny = variants.get("Shiny", "N/A")
                mythic = variants.get("Mythic", "N/A")
                shiny_mythic = variants.get("Shiny Mythic", "N/A")
                entries.append((pet, normal, shiny, mythic, shiny_mythic))

        if sort_by == "name":
            entries.sort(key=lambda x: x[0].lower())
        elif sort_by == "normal_value":
            entries.sort(key=lambda x: self.parse_value(x[1]), reverse=True)
        elif sort_by == "shiny_value":
            entries.sort(key=lambda x: self.parse_value(x[2]), reverse=True)

        for pet, normal, shiny, mythic, shiny_mythic in entries:
            self.tree.insert("", "end", text=pet, values=(normal, shiny, mythic, shiny_mythic))

    def parse_value(self, val):
        try:
            return float(val)
        except:
            return -1 if val in ("N/A", "O/C", "") else 0

    def watch_file_changes(self):
        while True:
            try:
                current_mtime = os.path.getmtime(JSON_PATH)
                if current_mtime != self.last_modified:
                    self.last_modified = current_mtime
                    self.load_data()
                    self.root.after(0, self.update_display)
            except FileNotFoundError:
                pass
            time.sleep(1)

    def scraper_loop(self):
        while True:
            self.scrape_and_save()
            time.sleep(3600)

    def manual_update(self):
        threading.Thread(target=self.scrape_and_save, daemon=True).start()

    def scrape_and_save(self):
        self.set_status("🔄 Aktualisiere...")
        API_URL = "https://api.bgsi.gg/api/items"
        HEADERS = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "Referer": "https://bgsi.gg/",
            "Origin": "https://bgsi.gg"
        }

        all_pets = {}
        page = 1
        limit = 50

        while True:
            try:
                params = {"limit": limit, "page": page}
                response = requests.get(API_URL, headers=HEADERS, params=params)
                if response.status_code != 200:
                    break

                data = response.json()
                pets_page = data.get("pets", [])
                if not pets_page:
                    break

                for pet in pets_page:
                    full_name = pet.get("name", "")
                    value = pet.get("value")
                    base_name = full_name
                    variant = "Normal"
                    if full_name.startswith("Shiny Mythic "):
                        base_name = full_name.replace("Shiny Mythic ", "")
                        variant = "Shiny Mythic"
                    elif full_name.startswith("Mythic "):
                        base_name = full_name.replace("Mythic ", "")
                        variant = "Mythic"
                    elif full_name.startswith("Shiny "):
                        base_name = full_name.replace("Shiny ", "")
                        variant = "Shiny"

                    if base_name not in all_pets:
                        all_pets[base_name] = {}
                    all_pets[base_name][variant] = value if value is not None else "N/A"

                page += 1
                time.sleep(0.2)
            except:
                break

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(all_pets, f, indent=2, ensure_ascii=False)

        self.last_updated = datetime.now().strftime("%H:%M:%S")
        self.set_status(f"✅ Letzte Aktualisierung: {self.last_updated}")

    def set_status(self, message):
        self.root.after(0, lambda: self.status_label.config(text=message))

def add_to_autostart():
    import os
    import sys
    try:
        import winshell
        from win32com.client import Dispatch

        exe_path = sys.executable

        # Ignoriere Aufruf aus .py-Datei – funktioniert nur mit .exe
        if not exe_path.lower().endswith(".exe"):
            print("ℹ️ Autostart wird nur bei .exe erstellt, nicht bei .py")
            return

        startup_folder = os.path.join(os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup")
        shortcut_path = os.path.join(startup_folder, "BGSI Value Viewer.lnk")

        if os.path.exists(shortcut_path):
            print("✅ Autostart-Link existiert bereits.")
            return

        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = exe_path
        shortcut.WorkingDirectory = os.path.dirname(exe_path)
        shortcut.IconLocation = exe_path
        shortcut.WindowStyle = 1
        shortcut.save()

        print("✅ Autostart-Verknüpfung wurde erstellt.")
    except Exception as e:
        print("❌ Fehler beim Erstellen der Autostart-Verknüpfung:", e)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("950x600")
    app = PetValueViewer(root)
    add_to_autostart()
    root.mainloop()
