import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, sys, json, subprocess, threading, requests, re, shutil, time
from datetime import datetime
from urllib.parse import urlparse
import re as _semver_re
import requests
import threading

APP_TITLE = "BGSI Hub"

# -------- Self-Update (dein Repo + Assetname hier eintragen) --------
HUB_UPDATE_REPO = "01324lolwer/bgsi.hub"
# case-insensitive; findet auch "bgsi_hub_launcher.exe"
HUB_ASSET_MATCH = r"(?i)(bgsi.*hub.*|hub.*launcher).*\.exe$"
HUB_VERSION = "1.5.2"  # oder was lokal wirklich läuft
# -------------------------------------------------------------------

CONFIG_FILE = "launcher_programs.json"
ACCENT = "#009ac1"
BG_DARK = "#0e0f12"
PANEL_DARK = "#14161a"
PANEL_LIGHT = "#1b1f24"
TXT_MAIN = "#e7eef6"
TXT_WEAK = "#9aa7b3"
BTN_HOVER = "#0f2b33"
DANGER = "#bd0000"

TIMEOUT = 30

# ---------- Deine GitHub Download-Liste (einfach erweitern) ----------
GITHUB_ITEMS = [
    {
        "name": "Mythic/Reroll Tool",
        "repo": "01324lolwer/bgsi.hub",
        "asset_match": r"comp_mythic_reroll_click_2\.exe$",
        "target_dir": os.path.abspath("Tools"),
        "auto_add_to_installed": True
    },
    {
        "name": "BGSI Value Viewer",
        "repo": "01324lolwer/bgsi.hub",
        "asset_match": r"value_display_gui_full\.exe$",
        "target_dir": os.path.abspath("Tools"),
        "auto_add_to_installed": True
    },
    {
        "name": "AutoKeyDruecker",
        "repo": "01324lolwer/bgsi.hub",
        "asset_match": r"AutoKeyDrueckertest2\.exe$",
        "target_dir": os.path.abspath("Tools"),
        "auto_add_to_installed": True
    },
]
# --------------------------------------------------------------------

# ======================= UTILS =========================
def semver_tuple(s: str):
    if not s: return (0,0,0,"")
    s = s.strip().lstrip("vV")
    m = _semver_re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", s)
    if m: return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
    m = _semver_re.match(r"^(\d+)\.(\d+)(.*)$", s)
    if m: return (int(m.group(1)), int(m.group(2)), 0, m.group(3))
    m = _semver_re.match(r"^(\d+)(.*)$", s)
    if m: return (int(m.group(1)), 0, 0, m.group(2))
    return (0,0,0,"")

def is_newer(remote: str, local: str) -> bool:
    r = semver_tuple(remote); l = semver_tuple(local)
    return (r[0],r[1],r[2]) > (l[0],l[1],l[2])

def load_programs():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_programs(programs):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(programs, f, indent=4, ensure_ascii=False)

def open_in_explorer(path):
    if not os.path.exists(path):
        messagebox.showerror("Fehler", f"Pfad nicht gefunden:\n{path}")
        return
    folder = os.path.dirname(path) if os.path.isfile(path) else path
    if sys.platform.startswith("win"):
        subprocess.Popen(["explorer", folder])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", folder])
    else:
        subprocess.Popen(["xdg-open", folder])

def start_external(path):
    if not os.path.exists(path):
        messagebox.showerror("Fehler", f"Datei nicht gefunden:\n{path}")
        return
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".jar":
            subprocess.Popen(["java", "-jar", path], shell=True)
        elif ext == ".py":
            py = sys.executable or "python"
            subprocess.Popen([py, path], shell=True)
        else:
            subprocess.Popen(path, shell=True)
    except Exception as e:
        messagebox.showerror("Start", f"Konnte Programm nicht starten:\n{e}")

# ======================= GITHUB API =========================
GH_TOKEN = os.getenv("GITHUB_TOKEN")  # optional
TIMEOUT = 30

class RepoAssetNotFound(Exception): ...
class RepoNotFoundOrPrivate(Exception): ...

def _gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        h["Authorization"] = f"Bearer {GH_TOKEN}"
    return h

# Semver-Utils falls noch nicht vorhanden
def semver_tuple(s: str):
    import re
    if not s: return (0,0,0,"")
    s = s.strip().lstrip("vV")
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", s)
    if m: return (int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4))
    m = re.match(r"^(\d+)\.(\d+)(.*)$", s)
    if m: return (int(m.group(1)), int(m.group(2)), 0, m.group(3))
    m = re.match(r"^(\d+)(.*)$", s)
    if m: return (int(m.group(1)), 0, 0, m.group(2))
    return (0,0,0,"")

def is_newer(remote: str, local: str) -> bool:
    r = semver_tuple(remote); l = semver_tuple(local)
    return (r[0],r[1],r[2]) > (l[0],l[1],l[2])

def gh_find_asset_across_releases(repo: str, pattern: str, allow_prerelease: bool=False, per_page: int=50):
    import re, requests
    url = f"https://api.github.com/repos/{repo}/releases?per_page={per_page}"
    r = requests.get(url, headers=_gh_headers(), timeout=TIMEOUT)
    if r.status_code == 404:
        raise RepoNotFoundOrPrivate("Repo nicht gefunden oder privat.")
    r.raise_for_status()
    rels = r.json() or []
    rels = [x for x in rels if not x.get("draft")]
    stable = [x for x in rels if not x.get("prerelease")]
    pre    = [x for x in rels if x.get("prerelease")]

    def key(rel):
        tag = rel.get("tag_name") or rel.get("name") or ""
        v = semver_tuple(tag)
        ts = rel.get("published_at") or rel.get("created_at") or ""
        return (v[0], v[1], v[2], ts)

    stable.sort(key=key, reverse=True)
    pre.sort(key=key, reverse=True)

    rx = re.compile(pattern, re.IGNORECASE)

    def find_in(lst):
        for rel in lst:
            for a in (rel.get("assets") or []):
                if rx.search(a.get("name","") or ""):
                    return rel, a
        return None

    found = find_in(stable) or (find_in(pre) if allow_prerelease else None)
    if not found:
        raise RepoAssetNotFound("Kein passender Asset in den Releases gefunden.")
    return found

def gh_get_releases_sorted(repo: str, per_page: int = 50, allow_prerelease: bool = False):
    """Alle Releases laden, Drafts raus, (optional) Pre-Releases, semver-absteigend sortiert, dann Datum."""
    url = f"https://api.github.com/repos/{repo}/releases?per_page={per_page}"
    r = requests.get(url, headers=_gh_headers(), timeout=TIMEOUT)
    if r.status_code == 404:
        raise RepoNotFoundOrPrivate("Repo nicht gefunden oder privat.")
    r.raise_for_status()
    rels = r.json() or []
    rels = [x for x in rels if not x.get("draft")]
    if not allow_prerelease:
        rels = [x for x in rels if not x.get("prerelease")]

    def key(rel):
        tag = rel.get("tag_name") or rel.get("name") or ""
        v = semver_tuple(tag)
        ts = rel.get("published_at") or rel.get("created_at") or ""
        return (v[0], v[1], v[2], ts)

    rels.sort(key=key, reverse=True)
    return rels

def pick_asset_regex(assets, pattern):
    rx = re.compile(pattern, re.IGNORECASE)
    for a in (assets or []):
        if rx.search(a.get("name","")):
            return a
    return None

# --- Gemeinsamer Downloader (Progress + Abbruch + Aufräumen) ---
def stream_download(url, target_path, progress_cb=None, stop_event=None, timeout=30, chunk_size=8192):
    """
    Lädt eine Datei als Stream nach target_path.
    - progress_cb(done_bytes, total_bytes) wird regelmäßig aufgerufen
    - stop_event (threading.Event) kann den Download abbrechen
    Hebt Exceptions hoch, damit der Aufrufer sie anzeigen kann.
    """
    # Zielordner sicherstellen
    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)

    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", "0") or 0)
        done = 0

        # in temporäre Datei schreiben → bei Erfolg atomar umbenennen
        tmp_path = target_path + ".part"
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if stop_event is not None and stop_event.is_set():
                    # Abbruch: temporäre Datei löschen und abbrechen
                    try: f.close(); os.remove(tmp_path)
                    except Exception: pass
                    raise RuntimeError("Download abgebrochen")

                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        try:
                            progress_cb(done, total)
                        except Exception:
                            # UI-Callback darf keinen Download crashen
                            pass

        # erfolgreich: .part → Ziel
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
        except Exception:
            # falls Ziel gesperrt ist, trotzdem überschreiben versuchen
            pass
        os.replace(tmp_path, target_path)

# ======================= UI Widgets =========================
class SideButton(ttk.Frame):
    def __init__(self, master, text, icon="●", command=None, active=False):
        super().__init__(master, padding=(8,6,8,6), style="Side.TFrame")
        self.command = command
        self.active = active
        self.btn = tk.Label(self, text=f"{icon}  {text}", anchor="w",
                            bg=PANEL_DARK, fg=TXT_MAIN if active else TXT_WEAK,
                            font=("Segoe UI", 11, "bold" if active else "normal"),
                            padx=14, pady=8)
        self.btn.pack(fill="x")
        self.btn.bind("<Button-1>", lambda e: self.command() if self.command else None)
        self.btn.bind("<Enter>", self._enter)
        self.btn.bind("<Leave>", self._leave)

    def set_active(self, is_active):
        self.active = is_active
        self.btn.config(fg=TXT_MAIN if is_active else TXT_WEAK, bg=PANEL_DARK)

    def _enter(self, _): 
        if not self.active: self.btn.config(bg=BTN_HOVER)
    def _leave(self, _): 
        self.btn.config(bg=PANEL_DARK if not self.active else PANEL_DARK)

class PillButton(ttk.Frame):
    def __init__(self, master, text, command=None, danger=False):
        super().__init__(master, style="Card.TFrame")
        self.command = command
        self.bg = ACCENT if not danger else DANGER
        self.lbl = tk.Label(self, text=text, bg=self.bg, fg="#0b0e11",
                            font=("Segoe UI Semibold", 10), padx=16, pady=8)
        self.lbl.pack()
        self.lbl.bind("<Button-1>", lambda e: self.command() if self.command else None)
        self.lbl.bind("<Enter>", lambda e: self.lbl.config(bg=self._brighten(self.bg)))
        self.lbl.bind("<Leave>", lambda e: self.lbl.config(bg=self.bg))
    @staticmethod
    def _brighten(hex_color):
        c = int(hex_color[1:], 16)
        r = min(((c >> 16) & 255) + 18, 255)
        g = min(((c >> 8) & 255) + 18, 255)
        b = min((c & 255) + 18, 255)
        return f"#{r:02x}{g:02x}{b:02x}"

# ======================= Seiten =========================
class InstalledPage(ttk.Frame):
    def __init__(self, master, programs_ref, on_change):
        super().__init__(master, style="Card.TFrame")
        self.programs = programs_ref
        self.on_change = on_change

        top = ttk.Frame(self, style="Card.TFrame")
        top.pack(fill="x", padx=14, pady=(14,8))
        PillButton(top, "➕ Hinzufügen", self.add_program).pack(side="left")
        ttk.Label(top, text="  ", background=PANEL_LIGHT).pack(side="left")
        PillButton(top, "✏️ Umbenennen", self.rename_selected).pack(side="left")
        ttk.Label(top, text="  ", background=PANEL_LIGHT).pack(side="left")
        PillButton(top, "🗑️ Entfernen", self.remove_selected, danger=True).pack(side="left")

        columns = ("name","path","added")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Pfad")
        self.tree.heading("added", text="Hinzugefügt")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("path", width=520, anchor="w")
        self.tree.column("added", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=14, pady=8)
        self.tree.bind("<Double-1>", lambda e: self.start_selected())
        self.tree.bind("<Return>",   lambda e: self.start_selected())

        bottom = ttk.Frame(self, style="Card.TFrame")
        bottom.pack(fill="x", padx=14, pady=(0,14))
        PillButton(bottom, "▶️ Starten", self.start_selected).pack(side="left")
        ttk.Label(bottom, text="  ", background=PANEL_LIGHT).pack(side="left")
        PillButton(bottom, "📂 Ordner", self.open_selected_folder).pack(side="left")
        ttk.Label(bottom, text="  ", background=PANEL_LIGHT).pack(side="left")
        PillButton(bottom, "🔄 Neu laden", self.refresh).pack(side="left")

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for p in self.programs():
            self.tree.insert("", "end", values=(p.get("name",""), p.get("path",""), p.get("added","")))

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte zuerst einen Eintrag auswählen.")
            return None
        return self.tree.index(sel[0])

    def add_program(self):
        file_path = filedialog.askopenfilename(
            title="Programm wählen",
            filetypes=[("Programme", "*.exe;*.bat;*.cmd;*.jar;*.py"), ("Alle Dateien", "*.*")]
        )
        if not file_path: return
        default_name = os.path.basename(file_path)
        name = simple_input(self, "Name vergeben", f"Anzeigename für:\n{file_path}", default=default_name)
        if not name: return
        data = self.programs()
        data.append({"name": name, "path": file_path, "added": datetime.now().strftime("%Y-%m-%d %H:%M")})
        save_programs(data); self.on_change(); self.refresh()

    def rename_selected(self):
        idx = self._selected_index()
        if idx is None: return
        data = self.programs()
        new_name = simple_input(self, "Umbenennen", "Neuer Name:", default=data[idx]["name"])
        if not new_name: return
        data[idx]["name"] = new_name
        save_programs(data); self.on_change(); self.refresh()

    def remove_selected(self):
        idx = self._selected_index()
        if idx is None: return
        data = self.programs()
        item = data[idx]
        if not messagebox.askyesno("Entfernen", f"„{item['name']}“ aus der Liste entfernen?\n(Die Datei bleibt erhalten)"):
            return
        del data[idx]
        save_programs(data); self.on_change(); self.refresh()

    def start_selected(self):
        idx = self._selected_index()
        if idx is None: return
        start_external(self.programs()[idx]["path"])

    def open_selected_folder(self):
        idx = self._selected_index()
        if idx is None: return
        open_in_explorer(self.programs()[idx]["path"])

class DownloadsPage(ttk.Frame):
    def __init__(self, master, add_to_installed_cb):
        super().__init__(master, style="Card.TFrame")
        self.add_to_installed_cb = add_to_installed_cb
        self.stop_event = threading.Event()

        header = ttk.Frame(self, style="Card.TFrame")
        header.pack(fill="x", padx=14, pady=(14,8))
        tk.Label(header, text="GitHub Downloads", bg=PANEL_LIGHT, fg=TXT_MAIN,
                 font=("Segoe UI Semibold", 13)).pack(side="left")
        PillButton(header, "🔄 Alle prüfen", self.check_all).pack(side="right")

        cols = ("name","repo","latest","status","path")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("repo", width=220, anchor="w")
        self.tree.column("latest", width=100, anchor="center")
        self.tree.column("status", width=160, anchor="w")
        self.tree.column("path", width=350, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=14, pady=8)

        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", padx=14, pady=(0,10))
        PillButton(bar, "ℹ️ Details", self.show_details).pack(side="left")
        ttk.Label(bar, text="  ", background=PANEL_LIGHT).pack(side="left")
        PillButton(bar, "⬇️ Installieren / Updaten", self.install_selected).pack(side="left")
        ttk.Label(bar, text="  ", background=PANEL_LIGHT).pack(side="left")
        PillButton(bar, "📂 Zielordner", self.open_folder).pack(side="left")

        # Progress + log
        self.prog = ttk.Progressbar(self, mode="determinate")
        self.prog.pack(fill="x", padx=14, pady=(0,6))
        self.lbl = tk.Label(self, text="Bereit", bg=PANEL_LIGHT, fg=TXT_WEAK, anchor="w")
        self.lbl.pack(fill="x", padx=14, pady=(0,12))

        self.items = []  # will hold runtime info
        self.refresh_table(initial=True)

    def refresh_table(self, initial=False):
        for r in self.tree.get_children(): self.tree.delete(r)
        self.items = []
        for item in GITHUB_ITEMS:
            row = {
                "name": item["name"],
                "repo": item["repo"],
                "asset_match": item["asset_match"],
                "target_dir": item.get("target_dir") or os.path.abspath("."),
                "auto_add": bool(item.get("auto_add_to_installed")),
                "latest": "?",
                "status": "Nicht geprüft",
                "path": ""
            }
            self.items.append(row)
            self.tree.insert("", "end",
                values=(row["name"], row["repo"], row["latest"], row["status"], row["path"]))
        if not initial:
            self.lbl.config(text="Liste aktualisiert")

    def _set_row(self, idx, latest=None, status=None, path=None):
        item = self.items[idx]
        if latest is not None: item["latest"] = latest
        if status is not None: item["status"] = status
        if path is not None: item["path"] = path
        self.tree.delete(self.tree.get_children()[idx])
        self.tree.insert("", idx, values=(item["name"], item["repo"], item["latest"], item["status"], item["path"]))

    def get_selected_index(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte Eintrag auswählen.")
            return None
        return self.tree.index(sel[0])

    def show_details(self):
        idx = self.get_selected_index()
        if idx is None: return
        d = self.items[idx]
        messagebox.showinfo("Details",
                            f"Name: {d['name']}\nRepo: {d['repo']}\nAsset-Match: {d['asset_match']}\n"
                            f"Zielordner: {d['target_dir']}\nLetzte Version: {d['latest']}\nStatus: {d['status']}\nPfad: {d['path']}")

    def check_all(self):
        def run():
            total = len(self.items) or 1
            self._progress(0, total, "Prüfe Releases…")
            for idx, it in enumerate(self.items):
                try:
                    # neu: suche das NEUSTE Release, das den gewünschten Asset wirklich enthält
                    rel, asset = gh_find_asset_across_releases(
                        it["repo"],
                        it["asset_match"],
                        allow_prerelease=False  # auf True, wenn du auch Pre-Releases zulassen willst
                    )
                    tag = rel.get("tag_name") or rel.get("name") or "?"
                    asset_name = asset.get("name", "")
                    # Status + „Latest“-Spalte updaten
                    self._set_row(idx, latest=tag, status=f"Gefunden: {asset_name}")
                except RepoAssetNotFound:
                    self._set_row(idx, latest="—", status="Kein Asset in Releases")
                except RepoNotFoundOrPrivate:
                    self._set_row(idx, latest="—", status="Repo privat/404 (Token?)")
                except Exception as e:
                    self._set_row(idx, latest="—", status=f"Fehler: {e}")
                self._progress(idx + 1, total, f"Geprüft {idx + 1}/{total}")
            self._status("Fertig")
        threading.Thread(target=run, daemon=True).start()

    def install_selected(self):
        idx = self.get_selected_index()
        if idx is None: return
        d = self.items[idx]
        self._download_and_install(idx, d)

    def _download_and_install(self, idx, d):
        def run():
            try:
                self._progress(0, 100, f"Frage Release von {d['repo']} ab…")
                rel, asset = gh_find_asset_across_releases(d["repo"], d["asset_match"], allow_prerelease=False)
                url   = asset["browser_download_url"]
                fname = asset["name"]
                os.makedirs(d["target_dir"], exist_ok=True)
                target = os.path.join(d["target_dir"], fname)

                # Download
                self._progress(0, 100, f"Lade {fname}…")
                def cb(done, total):
                    pct = int(done * 100 / total) if total else 0
                    self._progress(pct, 100, f"Lade {fname}… {pct}%")
                stream_download(url, target, cb, self.stop_event)

                # Erfolg
                self._set_row(idx, latest=rel.get("tag_name") or "?", status="Installiert", path=target)
                self._status(f"Installiert: {target}")

                if d["auto_add"]:
                    self.add_to_installed_cb(d["name"], target)
            except Exception as e:
                self._set_row(idx, status=f"Fehler: {e}")
                self._status(f"Fehler: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _progress(self, v, m, text):
        try:
            self.prog.config(maximum=m, value=v)
            self.lbl.config(text=text)
            self.update_idletasks()
        except tk.TclError:
            pass

    def _status(self, text):
        try:
            self.lbl.config(text=text)
        except tk.TclError:
            pass

    def open_folder(self):
        idx = self.get_selected_index()
        if idx is None: return
        path = self.items[idx]["target_dir"]
        open_in_explorer(path)

class CreditsPage(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, style="Card.TFrame")
        txt = tk.Text(self, wrap="word", bg=PANEL_LIGHT, fg=TXT_MAIN,
                      insertbackground=TXT_MAIN, relief="flat",
                      padx=16, pady=16)
        txt.pack(fill="both", expand=True, padx=14, pady=14)
        content = (
            "BGSI Hub — Credits\n"
            "\n"
            "• Entwicklung: [Lol wer / GitHub: 01324lolwer]\n"
            "• Stack: Python (tkinter/ttk, requests, json, threading, subprocess, re, shutil)\n"
            "• API: GitHub REST API (Releases/Downloads)\n"
            "• Packaging: optional PyInstaller\n"
            "• Icons/Font: Unicode, Segoe UI\n"
            "• Danke an alle Tester & Contributor\n"
            "\n"
            "Disclaimer:\n"
            "BGSI Hub startet und lädt externe Programme. Nutzung auf eigene Verantwortung. "
            "Keine Haftung für Schäden oder Datenverlust. Nicht mit Roblox, GitHub oder Microsoft verbunden; "
            "Marken gehören ihren Inhabern. Beachte stets AGB/ToS der jeweiligen Software/Spiele (inkl. Roblox) – "
            "Verstöße können zu Sperren führen. Prüfe Downloads/Hashes, nutze nur vertrauenswürdige Quellen. "
            "Der Self-Update-Prozess ersetzt die EXE und startet sie neu.\n"
            "\n"
            "Datenschutz\n"
            "Keine Telemetrie, keine personenbezogenen Daten. Lokal gespeichert: launcher_programs.json, "
            "ggf. Download-Historie. Netzwerkzugriffe nur zu GitHub-Endpunkten für Releases/Downloads.\n"
            "\n"
            "Kontakt/Issues: github.com/01324lolwer/bgsi.hub\n"
        )
        txt.insert("1.0", content)
        txt.config(state="disabled")

# ======================= Hub / Styles / Self-Update =========================
class HubApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg=BG_DARK)
        self.root.minsize(980, 600)

        self._programs_cache = load_programs()

        style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("Card.TFrame", background=PANEL_LIGHT)
        style.configure("Side.TFrame", background=PANEL_DARK)
        style.configure("Treeview",
                        background=PANEL_LIGHT, fieldbackground=PANEL_LIGHT,
                        foreground=TXT_MAIN, bordercolor=PANEL_DARK,
                        rowheight=26, font=("Segoe UI", 10))
        style.configure("Treeview.Heading",
                        background=PANEL_DARK, foreground=TXT_WEAK,
                        font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", BTN_HOVER)],
                  foreground=[("selected", TXT_MAIN)])

        # Sidebar
        self.left = ttk.Frame(root, style="Side.TFrame", width=210)
        self.left.pack(side="left", fill="y")
        self.right = ttk.Frame(root, style="Card.TFrame")
        self.right.pack(side="right", fill="both", expand=True)

        brand = tk.Label(self.left, text="  BGSI Hub", anchor="w",
                         bg=PANEL_DARK, fg=ACCENT, font=("Segoe UI Semibold", 14),
                         padx=14, pady=18)
        brand.pack(fill="x")

        self.btn_inst = SideButton(self.left, "Installiert", "📜",
                                   command=lambda: self.show("installed"), active=True)
        self.btn_inst.pack(fill="x")
        self.btn_dl = SideButton(self.left, "Downloads", "⬇️",
                                 command=lambda: self.show("downloads"))
        self.btn_dl.pack(fill="x")
        self.btn_update = SideButton(self.left, "Hub‑Update", "🛠️",
                                     command=self.check_self_update)
        self.btn_update.pack(fill="x")
        self.btn_credit = SideButton(self.left, "Credits", "ℹ️",
                                     command=lambda: self.show("credits"))
        self.btn_credit.pack(fill="x")

        footer = tk.Label(self.left, text=f"v{HUB_VERSION}", anchor="w",
                          bg=PANEL_DARK, fg=TXT_WEAK, padx=14, pady=10)
        footer.pack(side="bottom", fill="x")

        # Pages
        self.pages = {}
        self.pages["installed"] = InstalledPage(self.right, self.programs, self._on_programs_changed)
        self.pages["downloads"] = DownloadsPage(self.right, self._add_to_installed)
        self.pages["credits"]   = CreditsPage(self.right)

        # ALLES VERSTECKEN (wichtig!)
        for p in self.pages.values():
            p.place_forget()

        self.current = None
        self.show("installed")  # zeigt nur die gewählte Seite

    def programs(self):
        return self._programs_cache

    def _on_programs_changed(self):
        save_programs(self._programs_cache)

    def show(self, key):
        # immer erst alle Seiten weg
        for f in self.pages.values():
            f.place_forget()

        # dann die gewünschte Seite zeigen
        self.pages[key].place(relx=0, rely=0, relwidth=1, relheight=1)
        self.current = key

        # Sidebar-Status updaten
        self.btn_inst.set_active(key == "installed")
        self.btn_dl.set_active(key == "downloads")
        self.btn_credit.set_active(key == "credits")

        # falls du einen Update-Button hast:
        if hasattr(self, "btn_update"):
            self.btn_update.set_active(False)

    def _status_bar(self, text: str):
        try:
            if not hasattr(self, "_status_lbl") or not getattr(self, "_status_lbl").winfo_exists():
                self._status_lbl = tk.Label(self.right, text=text, bg=PANEL_LIGHT, fg=TXT_WEAK, anchor="w")
                self._status_lbl.pack(side="bottom", fill="x")
            else:
                self._status_lbl.config(text=text)
        except tk.TclError:
            pass

    def _add_to_installed(self, name, path):
        for p in self._programs_cache:
            if p["path"] == path:
                return  # schon drin
        self._programs_cache.append({"name": name, "path": path,
                                     "added": datetime.now().strftime("%Y-%m-%d %H:%M")})
        save_programs(self._programs_cache)
        # UI aktualisieren, falls installierte Seite sichtbar:
        if self.current == "installed":
            self.pages["installed"].refresh()

    # -------- Self-Update (GitHub) ----------
    def check_self_update(self):
        if not HUB_UPDATE_REPO or not HUB_ASSET_MATCH:
            messagebox.showwarning("Update", "Self-Update ist nicht konfiguriert (Repo/Asset).")
            return

        def run():
            try:
                # a) neuestes Release insgesamt (z.B. v1.2.0)
                rels = gh_get_releases_sorted(HUB_UPDATE_REPO, allow_prerelease=False)
                if not rels:
                    messagebox.showerror("Update", "Keine Releases gefunden.")
                    return
                latest = rels[0]
                latest_tag = latest.get("tag_name") or latest.get("name") or "?"
                # b) brauchst du ein Update?
                if latest_tag and not is_newer(latest_tag, HUB_VERSION):
                    messagebox.showinfo("Update", f"Du bist auf dem neuesten Stand (lokal v{HUB_VERSION}, remote {latest_tag}).")
                    return

                # c) Versuche Asset im neuesten Release (nicht „irgendeinem“)
                asset = pick_asset_regex(latest.get("assets") or [], HUB_ASSET_MATCH)
                if not asset:
                    # Liste der vorhandenen Assets zeigen – dann weißt du, woran der Regex scheitert
                    names = [a.get("name","") for a in (latest.get("assets") or [])]
                    # Optional: neueste Version MIT Asset als Fallback suchen
                    try:
                        rel_with_asset, asset2 = gh_find_asset_across_releases(
                            HUB_UPDATE_REPO, HUB_ASSET_MATCH, allow_prerelease=False
                        )
                        tag2 = rel_with_asset.get("tag_name") or rel_with_asset.get("name") or "?"
                        messagebox.showwarning(
                            "Update-Asset fehlt",
                            "Im neuesten Release "
                            f"{latest_tag} wurde kein passender Asset gefunden.\n\n"
                            f"Vorhandene Assets: {names}\n\n"
                            f"Gefunden in älterem Release {tag2}: {asset2.get('name','')}\n"
                            "• Hänge den korrekten EXE-Asset an das neueste Release an\n"
                            "• oder passe HUB_ASSET_MATCH an.\n"
                            "Du kannst auch das ältere Asset installieren."
                        )
                        if messagebox.askyesno("Älteres Asset verwenden?", f"{tag2} installieren?"):
                            url = asset2["browser_download_url"]
                            exe_dir = os.path.abspath(os.path.dirname(
                                sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
                            ))
                            expected = asset.get("size")  # Byte-Größe aus GitHub
                            self._download_update(url, asset["name"], expected)
                        return
                    except RepoAssetNotFound:
                        messagebox.showerror(
                            "Update",
                            "Kein passender Asset in irgendeinem Release gefunden.\n"
                            f"HUB_ASSET_MATCH: {HUB_ASSET_MATCH}\n"
                            f"Assets in {latest_tag}: {names}"
                        )
                        return

                # d) Asset ist im neuesten Release vorhanden → Update anbieten
                if messagebox.askyesno(
                    "Update verfügbar",
                    f"Neue Version {latest_tag} gefunden.\nAsset: {asset.get('name','')}\n\nJetzt herunterladen und installieren?"
                ):
                    url = asset["browser_download_url"]
                    exe_dir = os.path.abspath(os.path.dirname(
                        sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
                    ))
                    target = os.path.join(exe_dir, asset["name"])
                    self._download_update(url, target)

            except RepoNotFoundOrPrivate:
                messagebox.showerror("Update", "Repo nicht gefunden oder privat. GITHUB_TOKEN setzen?")
            except Exception as e:
                messagebox.showerror("Update", f"Fehler beim Prüfen: {e}")

        threading.Thread(target=run, daemon=True).start()

    def _download_update(self, url, asset_name, expected_size=None):
        exe_dir = os.path.abspath(os.path.dirname(
            sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
        ))
        tmp_name = f"__update__{int(time.time())}.exe"
        tmp_path = os.path.join(exe_dir, tmp_name)

        prog = ttk.Progressbar(self.right, mode="determinate")
        prog.pack(side="bottom", fill="x")
        self._status_bar("Lade Update…")

        def cb(done, total):
            pct = int(done * 100 / total) if total else 0
            prog.config(maximum=100, value=pct)
            self._status_bar(f"Lade Update… {pct}%")

        def run():
            try:
                stream_download(url, tmp_path, cb)  # lädt nach tmp_path + ".part" und ersetzt atomar
                if expected_size is not None:
                    actual = os.path.getsize(tmp_path)
                    if actual != expected_size:
                        raise RuntimeError(f"Downloadgröße stimmt nicht (erwartet {expected_size}, erhalten {actual}).")
                self._install_update(tmp_path, asset_name)
            except Exception as e:
                messagebox.showerror("Update", f"Download-Fehler: {e}")
                try:
                    if os.path.exists(tmp_path): os.remove(tmp_path)
                except: pass
            finally:
                try: prog.destroy()
                except: pass

        threading.Thread(target=run, daemon=True).start()

    def _install_update(self, tmp_path, asset_name):
        is_frozen = getattr(sys, "frozen", False)
        current_path = sys.executable if is_frozen else os.path.abspath(sys.argv[0])
        current_dir  = os.path.dirname(current_path)
        current_name = os.path.basename(current_path)

        if not is_frozen:
            try:
                final_path = os.path.join(current_dir, asset_name)
                shutil.copy2(tmp_path, final_path)
                subprocess.Popen([final_path], shell=True)
                messagebox.showinfo("Update", "Neue EXE wurde heruntergeladen und gestartet.\n"
                                            "Für Auto-Ersetzen bitte die EXE-Version des Hubs verwenden.")
            except Exception as e:
                messagebox.showerror("Update", f"Installationsfehler: {e}")
            return

        bat_path = os.path.join(current_dir, "bgsi_hub_updater.bat")
        script = f"""@echo off
    title BGSI Hub Updater
    rem kurze Wartezeit + Prozess sicher beenden
    ping 127.0.0.1 -n 2 > nul
    taskkill /PID {os.getpid()} /F > nul 2>&1
    ping 127.0.0.1 -n 2 > nul

    rem falls Temp woanders liegt, erst herkopieren
    if not exist "{os.path.basename(tmp_path)}" copy /Y "{tmp_path}" "{os.path.basename(tmp_path)}" > nul 2>&1

    rem EXE ersetzen (move atomar im selben Laufwerk)
    move /Y "{os.path.basename(tmp_path)}" "{current_name}" > nul 2>&1

    rem Mark-of-the-Web entfernen (falls vorhanden)
    powershell -NoProfile -ExecutionPolicy Bypass -Command "try {{ Unblock-File -Path '%cd%\\{current_name}' }} catch {{}} " > nul 2>&1

    start "" "{current_name}"
    del "%~f0"
    """
        try:
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(script)
            if os.path.dirname(tmp_path) != current_dir:
                shutil.copy2(tmp_path, os.path.join(current_dir, os.path.basename(tmp_path)))
            subprocess.Popen(["cmd", "/c", bat_path], cwd=current_dir, shell=True)
            self.root.after(200, self.root.destroy)
        except Exception as e:
            messagebox.showerror("Update", f"Updater konnte nicht gestartet werden: {e}")

# ======================= Dialog =========================
def simple_input(parent, title, prompt, default=""):
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=PANEL_LIGHT)
    win.resizable(False, False)
    win.transient(parent.winfo_toplevel())
    win.grab_set()

    frm = ttk.Frame(win, style="Card.TFrame", padding=14)
    frm.pack(fill="both", expand=True)
    lbl = tk.Label(frm, text=prompt, bg=PANEL_LIGHT, fg=TXT_MAIN,
                   font=("Segoe UI", 10), justify="left")
    lbl.pack(anchor="w")
    var = tk.StringVar(value=default)
    ent = tk.Entry(frm, textvariable=var, bg="#22262c", fg=TXT_MAIN,
                   insertbackground=TXT_MAIN, relief="flat", font=("Segoe UI", 10))
    ent.pack(fill="x", pady=(8,12)); ent.focus()
    btns = ttk.Frame(frm, style="Card.TFrame"); btns.pack(fill="x")
    ok = PillButton(btns, "OK", command=lambda: (setattr(win, "_value", var.get().strip()), win.destroy()))
    ok.pack(side="right")
    cancel = PillButton(btns, "Abbrechen", command=lambda: (setattr(win, "_value", None), win.destroy()))
    cancel.pack(side="right", padx=(0,8))
    win.bind("<Return>", lambda e: ok.command())
    win.bind("<Escape>", lambda e: cancel.command())
    parent.update_idletasks(); x = parent.winfo_rootx()+60; y = parent.winfo_rooty()+60
    win.geometry(f"+{x}+{y}")
    win.wait_window()
    return getattr(win, "_value", None)

# ======================= main =========================
def main():
    # requests ist notwendig
    try:
        import requests  # noqa
    except ImportError:
        messagebox.showerror("Fehlendes Modul", "Das Paket 'requests' wird benötigt:\n\npip install requests")
        return

    root = tk.Tk()
    style = ttk.Style(root)
    try: style.theme_use("clam")
    except tk.TclError: pass
    style.configure("Card.TFrame", background=PANEL_LIGHT)
    style.configure("Side.TFrame", background=PANEL_DARK)
    HubApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()