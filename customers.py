"""Customers window: list customers, loyalty points and purchase history."""

import tkinter as tk
from tkinter import ttk

import config
from widgets import center_window

C = config.COLORS
F = config.FONTS
CUR = config.CURRENCY


class CustomersWindow(tk.Toplevel):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db

        self.title("Customers")
        self.configure(bg=C["bg"])
        self.transient(master)

        self._build()
        self._reload()
        center_window(self, 820, 560, master)
        self.grab_set()

    def _build(self):
        header = tk.Frame(self, bg=C["primary"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="👥  Customers", bg=C["primary"],
                 fg=C["text_light"], font=F["heading"]).pack(side="left",
                                                             padx=20)

        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(bar, text="Search:", bg=C["bg"], fg=C["text"],
                 font=F["body"]).pack(side="left")
        self.search_var = tk.StringVar()
        e = tk.Entry(bar, textvariable=self.search_var, font=F["body"],
                     relief="solid", bd=1, width=28)
        e.pack(side="left", padx=8, ipady=4)
        e.bind("<KeyRelease>", lambda ev: self._reload())

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # left: customer list
        left = tk.Frame(body, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        cols = ("name", "phone", "bills")
        self.tree = ttk.Treeview(left, columns=cols, show="headings")
        for c, h, w, a in (("name", "Name", 200, "w"),
                           ("phone", "Phone", 140, "w"),
                           ("bills", "Bills", 60, "e")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor=a)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_history())

        # right: detail / history
        right = tk.Frame(body, bg=C["card"], bd=1, relief="solid",
                         highlightbackground=C["card_border"], width=320)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self.detail_lbl = tk.Label(right, text="Select a customer",
                                   bg=C["card"], fg=C["text"],
                                   font=F["subhead"], anchor="w",
                                   justify="left")
        self.detail_lbl.pack(fill="x", padx=14, pady=(12, 8))

        tk.Label(right, text="Purchase history", bg=C["card"],
                 fg=C["text_muted"], font=F["small_bold"]).pack(
                     anchor="w", padx=14, pady=(8, 2))
        hcols = ("bill", "date", "total")
        self.htree = ttk.Treeview(right, columns=hcols, show="headings",
                                  height=14)
        for c, h, w, a in (("bill", "Bill", 110, "w"),
                           ("date", "Date", 110, "w"),
                           ("total", CUR, 70, "e")):
            self.htree.heading(c, text=h)
            self.htree.column(c, width=w, anchor=a)
        self.htree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _reload(self):
        self.tree.delete(*self.tree.get_children())
        for c in self.db.list_customers(self.search_var.get().strip() or None):
            n_bills = len(self.db.customer_bills(c["id"]))
            self.tree.insert("", "end", iid=str(c["id"]),
                             values=(c["name"], c["phone"] or "", n_bills))

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _show_history(self):
        cid = self._selected_id()
        if cid is None:
            return
        cust = self.db.get_customer(cid)
        bills = self.db.customer_bills(cid)
        spent = sum(b["total"] for b in bills)
        self.detail_lbl.config(
            text=f"{cust['name']}\n📞 {cust['phone'] or '—'}\n"
                 f"🧾 {len(bills)} bills  •  {CUR} {spent:.2f} spent")
        self.htree.delete(*self.htree.get_children())
        for b in bills:
            self.htree.insert("", "end",
                              values=(b["bill_number"],
                                      b["created_at"][:10],
                                      f"{b['total']:.2f}"))
