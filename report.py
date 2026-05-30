"""Daily Sales Report popup."""

from datetime import datetime
import tkinter as tk
from tkinter import ttk

import config
from widgets import HoverButton, center_window

C = config.COLORS
F = config.FONTS
CUR = config.CURRENCY


class ReportWindow(tk.Toplevel):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db

        self.title("Daily Sales Report")
        self.configure(bg=C["bg"])
        self.transient(master)

        data = db.daily_report()
        self._build(data)
        center_window(self, 460, 520, master)
        self.grab_set()

    def _build(self, data):
        header = tk.Frame(self, bg=C["primary"], height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="📊  Daily Sales Report", bg=C["primary"],
                 fg=C["text_light"], font=F["heading"]).pack(side="left",
                                                             padx=20)
        pretty = datetime.strptime(data["date"], "%Y-%m-%d").strftime(
            "%d %b %Y")
        tk.Label(header, text=pretty, bg=C["primary"], fg="#aab4d4",
                 font=F["body"]).pack(side="right", padx=20)

        # stat cards
        stats = tk.Frame(self, bg=C["bg"])
        stats.pack(fill="x", padx=16, pady=16)
        self._stat_card(stats, "Total Sales", f"{CUR} {data['sales']:.2f}",
                        C["accent"], 0)
        self._stat_card(stats, "Bills", f"{data['bills']}", C["success"], 1)
        self._stat_card(stats, "Items Sold", f"{data['qty']:g}",
                        C["warning"], 2)
        for i in range(3):
            stats.columnconfigure(i, weight=1, uniform="s")

        if data["discount"]:
            tk.Label(self, text=f"Discounts given today:  "
                     f"{CUR} {data['discount']:.2f}", bg=C["bg"],
                     fg=C["text_muted"], font=F["body"]).pack(anchor="w",
                                                              padx=20)

        # top products
        tk.Label(self, text="🏆  Top Selling Products", bg=C["bg"],
                 fg=C["text"], font=F["subhead"]).pack(anchor="w", padx=20,
                                                       pady=(14, 6))

        wrap = tk.Frame(self, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"])
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        if data["top"]:
            cols = ("rank", "name", "qty", "revenue")
            tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                height=8)
            for c, h, w, a in (("rank", "#", 40, "center"),
                               ("name", "Product", 180, "w"),
                               ("qty", "Qty Sold", 90, "e"),
                               ("revenue", f"Revenue ({CUR})", 110, "e")):
                tree.heading(c, text=h)
                tree.column(c, width=w, anchor=a)
            for rank, p in enumerate(data["top"], start=1):
                tree.insert("", "end", values=(
                    rank, p["name"], f"{p['qty']:g}", f"{p['revenue']:.2f}"))
            tree.pack(fill="both", expand=True, padx=8, pady=8)
        else:
            tk.Label(wrap, text="\nNo sales recorded today yet.\n",
                     bg=C["card"], fg=C["text_muted"], font=F["body"]).pack(
                         pady=30)

        HoverButton(self, C["accent"], C["accent_hover"], text="Close",
                    fg="white", font=F["body_bold"], padx=20, pady=8,
                    command=self.destroy).pack(pady=(0, 14))

    def _stat_card(self, parent, label, value, color, col):
        card = tk.Frame(parent, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"])
        card.grid(row=0, column=col, padx=4, sticky="nsew")
        tk.Label(card, text=value, bg=C["card"], fg=color,
                 font=(config.FONT_FAMILY, 15, "bold")).pack(pady=(14, 2),
                                                             padx=8)
        tk.Label(card, text=label, bg=C["card"], fg=C["text_muted"],
                 font=F["small"]).pack(pady=(0, 12))
