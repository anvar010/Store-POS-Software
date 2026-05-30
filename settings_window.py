"""Settings & branding window, including database backup / restore."""

import os
import shutil
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, filedialog

import config
import web_server
from widgets import HoverButton, ScrollableFrame, center_window

C = config.COLORS
F = config.FONTS


class SettingsWindow(tk.Toplevel):
    def __init__(self, master, db, on_saved=None, on_restored=None):
        super().__init__(master)
        self.db = db
        self.on_saved = on_saved
        self.on_restored = on_restored
        self._logo_src = config.LOGO_PATH or ""

        self.title("Settings")
        self.configure(bg=C["bg"])
        self.minsize(520, 600)
        self.transient(master)

        self._build()
        center_window(self, 560, 680, master)
        self.grab_set()

    # ------------------------------------------------------------------ build
    def _build(self):
        header = tk.Frame(self, bg=C["primary"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="⚙  Settings", bg=C["primary"],
                 fg=C["text_light"], font=F["heading"]).pack(side="left",
                                                             padx=20)

        # action bar pinned to bottom
        actions = tk.Frame(self, bg=C["bg"])
        actions.pack(fill="x", side="bottom", padx=16, pady=12)
        HoverButton(actions, C["success"], "#15803d", text="💾  Save Settings",
                    fg="white", font=F["body_bold"], padx=16, pady=9,
                    command=self._save).pack(side="right")
        HoverButton(actions, C["tab_inactive"], "#94a3b8", text="Close",
                    fg=C["text"], font=F["body_bold"], padx=16, pady=9,
                    command=self.destroy).pack(side="right", padx=8)

        scroll = ScrollableFrame(self, bg=C["bg"])
        scroll.pack(fill="both", expand=True)
        body = scroll.body

        # --- Store details -------------------------------------------------
        self.vars = {}
        sec = self._section(body, "🏪  Store Details")
        self._row(sec, "store_name", "Store name", config.STORE_NAME)
        self._row(sec, "store_tagline", "Tagline", config.STORE_TAGLINE)
        self._row(sec, "store_address", "Address", config.STORE_ADDRESS)
        self._row(sec, "store_phone", "Phone", config.STORE_PHONE)
        self._row(sec, "store_trn", "Tax / TRN / GSTIN no.", config.STORE_TRN)
        self._row(sec, "currency", "Currency symbol", config.CURRENCY)

        # logo
        logo_row = tk.Frame(sec, bg=C["card"])
        logo_row.pack(fill="x", padx=14, pady=(8, 4))
        tk.Label(logo_row, text="Logo", bg=C["card"], fg=C["text_muted"],
                 font=F["small"], width=18, anchor="w").pack(side="left")
        self.logo_lbl = tk.Label(logo_row, bg=C["card"], fg=C["text_muted"],
                                 font=F["small"])
        self.logo_lbl.pack(side="left", padx=6)
        HoverButton(logo_row, C["accent"], C["accent_hover"], text="Browse…",
                    fg="white", font=F["small"], padx=10, pady=4,
                    command=self._choose_logo).pack(side="left")
        HoverButton(logo_row, C["tab_inactive"], "#94a3b8", text="Clear",
                    fg=C["text"], font=F["small"], padx=10, pady=4,
                    command=self._clear_logo).pack(side="left", padx=4)
        self._refresh_logo_label()

        # --- Receipt -------------------------------------------------------
        sec2 = self._section(body, "🧾  Receipt")
        self._row(sec2, "receipt_footer", "Footer message",
                  config.RECEIPT_FOOTER)

        # --- Mobile / remote access ---------------------------------------
        self._build_mobile_section(body)

        # --- Data / backup -------------------------------------------------
        sec4 = self._section(body, "💾  Data Backup")
        brow = tk.Frame(sec4, bg=C["card"])
        brow.pack(fill="x", padx=14, pady=10)
        HoverButton(brow, C["primary"], C["primary_dark"],
                    text="⬇  Backup Database", fg="white", font=F["body_bold"],
                    padx=14, pady=8, command=self._backup).pack(side="left")
        HoverButton(brow, C["danger"], C["danger_hover"],
                    text="⬆  Restore Database", fg="white", font=F["body_bold"],
                    padx=14, pady=8, command=self._restore).pack(side="left",
                                                                 padx=8)
        tk.Label(sec4, text="Backups are timestamped copies of store.db. "
                 "Restoring replaces all current data.", bg=C["card"],
                 fg=C["text_muted"], font=F["small"], wraplength=480,
                 justify="left").pack(anchor="w", padx=14, pady=(0, 10))

    def _build_mobile_section(self, body):
        sec = self._section(body, "📱  Mobile / Remote Access")
        enabled = self.db.get_setting("mobile_enabled", "0") == "1"
        port = self.db.get_setting("mobile_port", str(config.MOBILE_PORT))
        pin = self.db.get_setting("mobile_pin", config.MOBILE_PIN)

        self.mobile_enabled = tk.BooleanVar(value=enabled)
        chk = tk.Checkbutton(
            sec, text="Enable mobile access (edit price & stock from a phone)",
            variable=self.mobile_enabled, bg=C["card"], fg=C["text"],
            activebackground=C["card"], font=F["body"], anchor="w")
        chk.pack(fill="x", padx=12, pady=(8, 2))

        self._row(sec, "mobile_port", "Port", port)
        self._row(sec, "mobile_pin", "Access PIN", pin)

        if not web_server.is_available():
            tk.Label(sec, text="⚠ Install the 'requests' & 'flask' packages to "
                     "use this feature.", bg=C["card"], fg=C["danger"],
                     font=F["small"], wraplength=480, justify="left").pack(
                         anchor="w", padx=14, pady=(2, 6))

        url = web_server.STATE.get("url") or \
            f"http://{web_server.get_lan_ip()}:{port}/"
        status = ("● Running" if web_server.STATE.get("running")
                  else "○ Off (enable, then restart the app)")
        info = (f"On your phone (same WiFi) open:\n   {url}\n"
                f"Login: any username, password = the PIN above.\n"
                f"Status: {status}\n\n"
                "To use it from OUTSIDE the shop, run a free Cloudflare Tunnel "
                "to this port — see README.")
        tk.Label(sec, text=info, bg=C["card"], fg=C["text_muted"],
                 font=F["small"], justify="left", wraplength=480).pack(
                     anchor="w", padx=14, pady=(2, 12))

    # --------------------------------------------------------------- helpers
    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=C["bg"], fg=C["text"],
                 font=F["subhead"]).pack(anchor="w", padx=16, pady=(14, 4))
        card = tk.Frame(parent, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"])
        card.pack(fill="x", padx=16)
        return card

    def _row(self, parent, key, label, value):
        row = tk.Frame(parent, bg=C["card"])
        row.pack(fill="x", padx=14, pady=5)
        tk.Label(row, text=label, bg=C["card"], fg=C["text_muted"],
                 font=F["small"], width=18, anchor="w").pack(side="left")
        var = tk.StringVar(value=value)
        tk.Entry(row, textvariable=var, font=F["body"], relief="solid",
                 bd=1).pack(side="left", fill="x", expand=True, ipady=3)
        self.vars[key] = var

    def _refresh_logo_label(self):
        name = os.path.basename(self._logo_src) if self._logo_src else "None"
        self.logo_lbl.config(text=name)

    def _choose_logo(self):
        path = filedialog.askopenfilename(
            title="Choose logo image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if path:
            self._logo_src = path
            self._refresh_logo_label()

    def _clear_logo(self):
        self._logo_src = ""
        self._refresh_logo_label()

    # --------------------------------------------------------------- actions
    def _persist_logo(self):
        if not self._logo_src:
            return ""
        if not os.path.isabs(self._logo_src):
            return self._logo_src
        ext = os.path.splitext(self._logo_src)[1].lower()
        dest = os.path.join(config.IMAGES_DIR, f"store_logo{ext}")
        try:
            shutil.copyfile(self._logo_src, dest)
            return os.path.basename(dest)
        except Exception:
            return self._logo_src

    def _save(self):
        values = {k: v.get().strip() for k, v in self.vars.items()}
        values["currency"] = values["currency"] or "Rs."
        values["logo_path"] = self._persist_logo()
        # mobile access settings
        values["mobile_enabled"] = "1" if self.mobile_enabled.get() else "0"
        values["mobile_port"] = values.get("mobile_port") or "8080"
        values["mobile_pin"] = values.get("mobile_pin") or "1234"

        self.db.set_settings(values)
        config.apply_settings(values)
        if self.on_saved:
            self.on_saved()
        messagebox.showinfo(
            "Saved",
            "Settings saved.\n\nCurrency and Mobile-access changes take full "
            "effect after restarting the app.", parent=self)

    def _backup(self):
        default = f"store_{datetime.now():%Y%m%d_%H%M%S}.db"
        path = filedialog.asksaveasfilename(
            title="Save backup as", initialdir=config.BACKUPS_DIR,
            initialfile=default, defaultextension=".db",
            filetypes=[("SQLite database", "*.db")])
        if not path:
            return
        try:
            # commit any pending work, then copy the file
            self.db.conn.commit()
            shutil.copyfile(config.DB_PATH, path)
            messagebox.showinfo("Backup",
                                f"Backup saved:\n{path}", parent=self)
        except Exception as exc:
            messagebox.showerror("Backup", f"Backup failed:\n{exc}",
                                 parent=self)

    def _restore(self):
        path = filedialog.askopenfilename(
            title="Choose a backup to restore", initialdir=config.BACKUPS_DIR,
            filetypes=[("SQLite database", "*.db")])
        if not path:
            return
        if not messagebox.askyesno(
                "Restore",
                "This will REPLACE all current data with the selected "
                "backup. Continue?", parent=self):
            return
        try:
            # safety copy of the current db first
            safety = os.path.join(
                config.BACKUPS_DIR,
                f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.db")
            self.db.conn.commit()
            shutil.copyfile(config.DB_PATH, safety)

            self.db.close()
            shutil.copyfile(path, config.DB_PATH)
        except Exception as exc:
            messagebox.showerror("Restore", f"Restore failed:\n{exc}",
                                 parent=self)
            return
        messagebox.showinfo("Restore",
                            "Database restored. The app will refresh.",
                            parent=self)
        if self.on_restored:
            self.on_restored()
        self.destroy()
