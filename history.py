"""Invoice History window: browse / search past bills, reprint PDFs."""

import os
import sys
import subprocess
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import config
from widgets import HoverButton, center_window
import pdf_receipt

C = config.COLORS
F = config.FONTS
CUR = config.CURRENCY


class HistoryWindow(tk.Toplevel):
    def __init__(self, master, db):
        super().__init__(master)
        self.db = db

        self.title("Invoice History")
        self.configure(bg=C["bg"])
        self.transient(master)

        self._build()
        self._reload()
        center_window(self, 860, 560, master)
        self.grab_set()

    # ------------------------------------------------------------------ build
    def _build(self):
        header = tk.Frame(self, bg=C["primary"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🧾  Invoice History", bg=C["primary"],
                 fg=C["text_light"], font=F["heading"]).pack(side="left",
                                                             padx=20)

        # search bar
        bar = tk.Frame(self, bg=C["bg"])
        bar.pack(fill="x", padx=14, pady=(12, 6))

        tk.Label(bar, text="Month:", bg=C["bg"], fg=C["text"],
                 font=F["body"]).pack(side="left")
        self.month_var = tk.StringVar(value="All Months")
        self._month_map = {}                  # pretty label -> 'YYYY-MM'
        self.month_combo = ttk.Combobox(bar, textvariable=self.month_var,
                                        state="readonly", width=14)
        self.month_combo.pack(side="left", padx=(6, 16))
        self.month_combo.bind("<<ComboboxSelected>>", lambda e: self._reload())
        self._load_months()

        tk.Label(bar, text="Customer:", bg=C["bg"], fg=C["text"],
                 font=F["body"]).pack(side="left")
        self.search_var = tk.StringVar()
        entry = tk.Entry(bar, textvariable=self.search_var, font=F["body"],
                         relief="solid", bd=1, width=22)
        entry.pack(side="left", padx=8, ipady=4)
        entry.bind("<Return>", lambda e: self._reload())
        HoverButton(bar, C["accent"], C["accent_hover"], text="Search",
                    fg="white", font=F["body_bold"], padx=14, pady=6,
                    command=self._reload).pack(side="left")
        HoverButton(bar, C["tab_inactive"], "#94a3b8", text="Show All",
                    fg=C["text"], font=F["body_bold"], padx=14, pady=6,
                    command=self._clear_search).pack(side="left", padx=6)

        # table
        wrap = tk.Frame(self, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"])
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        cols = ("bill", "customer", "date", "items", "qty", "total")
        headings = ("Bill No.", "Customer", "Date / Time", "Items", "Qty",
                    f"Total ({CUR})")
        widths = (150, 150, 160, 60, 70, 110)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, h, w in zip(cols, headings, widths):
            self.tree.heading(c, text=h)
            anchor = "e" if c in ("items", "qty", "total") else "w"
            self.tree.column(c, width=w, anchor=anchor)
        vsb = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self._reprint())

        # footer
        footer = tk.Frame(self, bg=C["bg"])
        footer.pack(fill="x", padx=14, pady=(0, 12))
        self.count_lbl = tk.Label(footer, text="", bg=C["bg"],
                                  fg=C["text_muted"], font=F["small"])
        self.count_lbl.pack(side="left")
        HoverButton(footer, C["primary"], C["primary_dark"],
                    text="📂 Open PDF", fg="white", font=F["body_bold"],
                    padx=14, pady=8, command=self._open_pdf
                    ).pack(side="right", padx=6)
        HoverButton(footer, C["accent"], C["accent_hover"],
                    text="🖨 Reprint PDF", fg="white", font=F["body_bold"],
                    padx=14, pady=8, command=self._reprint
                    ).pack(side="right")

    # --------------------------------------------------------------- months
    def _load_months(self):
        """Populate the month dropdown from months that actually have bills."""
        self._month_map = {}
        labels = ["All Months"]
        for ym in self.db.get_bill_months():
            try:
                pretty = datetime.strptime(ym, "%Y-%m").strftime("%B %Y")
            except ValueError:
                pretty = ym
            self._month_map[pretty] = ym
            labels.append(pretty)
        self.month_combo["values"] = labels
        if self.month_var.get() not in labels:
            self.month_var.set("All Months")

    def _selected_month(self):
        return self._month_map.get(self.month_var.get())   # None for "All"

    # --------------------------------------------------------------- actions
    def _reload(self):
        query = self.search_var.get().strip()
        month = self._selected_month()
        bills = self.db.search_bills(query or None, month=month)
        self.tree.delete(*self.tree.get_children())
        total = 0.0
        for b in bills:
            total += b["total"]
            self.tree.insert(
                "", "end", iid=str(b["id"]),
                values=(b["bill_number"], b["customer_name"], b["created_at"],
                        b["total_items"], f"{b['total_qty']:g}",
                        f"{b['total']:.2f}"))
        scope = self.month_var.get() if month else "all time"
        self.count_lbl.config(
            text=f"{len(bills)} bill(s) · {scope} · "
                 f"total {CUR} {total:.2f}")

    def _clear_search(self):
        self.search_var.set("")
        self.month_var.set("All Months")
        self._reload()

    def _selected_bill_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a bill first.", parent=self)
            return None
        return int(sel[0])

    def _reprint(self):
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = self.db.get_bill(bill_id)
        items = self.db.get_bill_items(bill_id)
        if not bill or not items:
            messagebox.showerror("Reprint", "Bill data not found.",
                                 parent=self)
            return
        try:
            pdf_path = pdf_receipt.generate_receipt(
                bill["bill_number"], bill["created_at"], items,
                bill["subtotal"], bill["discount"], bill["total"],
                customer_name=bill["customer_name"])
            self.db.set_bill_pdf(bill_id, pdf_path)
            self._open_file(pdf_path)
        except Exception as exc:
            messagebox.showerror("Reprint",
                                 f"Could not regenerate PDF:\n{exc}",
                                 parent=self)

    def _open_pdf(self):
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = self.db.get_bill(bill_id)
        path = bill.get("pdf_path") if bill else None
        if path and os.path.exists(path):
            self._open_file(path)
        else:
            if messagebox.askyesno(
                    "Open PDF",
                    "No saved PDF for this bill. Regenerate it now?",
                    parent=self):
                self._reprint()

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as exc:
            messagebox.showerror("Open", f"Could not open file:\n{exc}")
