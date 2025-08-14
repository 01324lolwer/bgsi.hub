import tkinter as tk
from tkinter import messagebox, Toplevel
from PIL import Image, ImageTk, ImageGrab
import threading
import time
import cv2
import numpy as np
import pyautogui
import json
pyautogui.FAILSAFE = False

MYTHIC_PATH = "mythic.png"
REROLL_PATHS = ["reroll.png", "reroll2.png", "reroll3.png"]
THRESHOLD = 0.85

mythic_img = cv2.imread(MYTHIC_PATH)
reroll_imgs = [cv2.imread(path) for path in REROLL_PATHS]

bereich_links = None
bereich_rechts = None
is_running = False
SAVE_FILE = "saved_areas.json"

def screenshot_cv(region):
    x, y, w, h = region
    pyautogui.moveTo(900, 650)
    time.sleep(0.01)
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

def position_gefunden(template, region):
    screenshot = screenshot_cv(region)
    if (screenshot.shape[0] < template.shape[0] or screenshot.shape[1] < template.shape[1]):
        return None
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= THRESHOLD:
        return max_loc
    return None

def mythic_gefunden(region):
    return position_gefunden(mythic_img, region) is not None

def reroll_until_mythic(region, status_label):
    global is_running
    versuche = 0
    while is_running:
        if mythic_gefunden(region):
            status_label.config(text="✅ Mythic gefunden")
            break
        reroll_pos = None
        reroll_img_used = None
        for img in reroll_imgs:
            pos = position_gefunden(img, region)
            if pos:
                reroll_pos = pos
                reroll_img_used = img
                break
        if reroll_pos:
            x, y, w, h = region
            click_x = x + reroll_pos[0] + reroll_img_used.shape[1] // 2
            click_y = y + reroll_pos[1] + reroll_img_used.shape[0] // 2
            status_label.config(text="🔁 Reroll erkannt – klicke")
            pyautogui.click(click_x, click_y)
            time.sleep(0.05)
        else:
            status_label.config(text="⏳ Kein Reroll sichtbar")
            time.sleep(0.3)
        versuche += 1
        if versuche > 30:
            status_label.config(text="⛔️ Abbruch nach 30 Versuchen")
            break

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("🔍 Exakter Reroll-Klick auf Erkennung")

        self.label = tk.Label(root)
        self.label.pack()

        self.status_label = tk.Label(root, text="Bereit")
        self.status_label.pack()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="🟦 Bereich Links wählen", command=lambda: self.wähle_bereich("links")).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="🟥 Bereich Rechts wählen", command=lambda: self.wähle_bereich("rechts")).grid(row=0, column=1, padx=5)

        tk.Button(btn_frame, text="💾 Links speichern", command=lambda: self.speichern_bereich("links")).grid(row=1, column=0, padx=5)
        tk.Button(btn_frame, text="💾 Rechts speichern", command=lambda: self.speichern_bereich("rechts")).grid(row=1, column=1, padx=5)

        tk.Button(btn_frame, text="▶️ Start Links", command=self.start_links).grid(row=2, column=0, padx=5)
        tk.Button(btn_frame, text="▶️ Start Rechts", command=self.start_rechts).grid(row=2, column=1, padx=5)

        self.toggle_btn = tk.Button(root, text="🟢 Start (manuell)", width=20, command=self.toggle)
        self.toggle_btn.pack(pady=5)

        tk.Button(root, text="📌 Extra Fenster öffnen", command=self.erstelle_topfenster).pack(pady=10)

        self.screenshot = None
        self.selection_start = None
        self.aktueller_bereich = None

        self.label.bind("<Button-1>", self.start_select)
        self.label.bind("<ButtonRelease-1>", self.end_select)

        self.update_loop()
        self.lade_gespeicherte_bereiche()

    def wähle_bereich(self, name):
        self.video_active = False
        self.aktueller_bereich = name
        self.screenshot = ImageGrab.grab()
        img = self.screenshot.resize((960, 540))
        self.display_img = img
        self.tk_img = ImageTk.PhotoImage(img)
        self.label.config(image=self.tk_img)

    def start_select(self, event):
        if self.screenshot:
            self.selection_start = (event.x, event.y)

    def end_select(self, event):
        global bereich_links, bereich_rechts
        if not self.selection_start:
            return
        x0, y0 = self.selection_start
        x1, y1 = event.x, event.y
        x, y = min(x0, x1), min(y0, y1)
        w, h = abs(x1 - x0), abs(y1 - y0)
        scale_x = self.screenshot.width / 960
        scale_y = self.screenshot.height / 540
        x_real = int(x * scale_x)
        y_real = int(y * scale_y)
        w_real = int(w * scale_x)
        h_real = int(h * scale_y)
        if self.aktueller_bereich == "links":
            bereich_links = (x_real, y_real, w_real, h_real)
            self.status_label.config(text=f"📌 Links gesetzt: {bereich_links}")
        elif self.aktueller_bereich == "rechts":
            bereich_rechts = (x_real, y_real, w_real, h_real)
            self.status_label.config(text=f"📌 Rechts gesetzt: {bereich_rechts}")
        self.selection_start = None

    def speichern_bereich(self, name):
        data = {}
        if name == "links" and bereich_links:
            data["links"] = bereich_links
        elif name == "rechts" and bereich_rechts:
            data["rechts"] = bereich_rechts

        try:
            with open(SAVE_FILE, "r") as f:
                existing = json.load(f)
        except:
            existing = {}
        existing.update(data)

        with open(SAVE_FILE, "w") as f:
            json.dump(existing, f)

        self.status_label.config(text=f"💾 Bereich '{name}' gespeichert")

    def lade_gespeicherte_bereiche(self):
        global bereich_links, bereich_rechts
        try:
            with open(SAVE_FILE, "r") as f:
                data = json.load(f)
                if "links" in data:
                    bereich_links = tuple(data["links"])
                    self.status_label.config(text=f"✅ Bereich Links geladen: {bereich_links}")
                if "rechts" in data:
                    bereich_rechts = tuple(data["rechts"])
                    self.status_label.config(text=f"✅ Bereich Rechts geladen: {bereich_rechts}")
        except Exception:
            pass

    def start_links(self):
        global is_running
        if not bereich_links:
            messagebox.showerror("Fehlt", "Bitte Bereich wählen oder laden.")
            return
        is_running = True
        threading.Thread(target=reroll_until_mythic, args=(bereich_links, self.status_label), daemon=True).start()

    def start_rechts(self):
        global is_running
        if not bereich_rechts:
            messagebox.showerror("Fehlt", "Bitte Bereich wählen oder laden.")
            return
        is_running = True
        threading.Thread(target=reroll_until_mythic, args=(bereich_rechts, self.status_label), daemon=True).start()

    def toggle(self):
        global is_running
        if not bereich_links and not bereich_rechts:
            messagebox.showerror("Fehlt", "Bitte mindestens einen Bereich wählen.")
            return
        is_running = not is_running
        self.toggle_btn.config(text="🟥 Stop" if is_running else "🟢 Start")
        if is_running:
            if bereich_links:
                threading.Thread(target=reroll_until_mythic, args=(bereich_links, self.status_label), daemon=True).start()
            if bereich_rechts:
                threading.Thread(target=reroll_until_mythic, args=(bereich_rechts, self.status_label), daemon=True).start()

    def erstelle_topfenster(self):
        top = Toplevel(self.root)
        top.title("📌 Schnellauswahl")
        top.attributes("-topmost", True)
        tk.Button(top, text="▶️ Start Links", width=15, command=self.start_links).pack(pady=5)
        tk.Button(top, text="▶️ Start Rechts", width=15, command=self.start_rechts).pack(pady=5)

    def update_loop(self):
        self.root.after(100, self.update_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()