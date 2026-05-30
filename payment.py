"""Checkout payment dialog: payment method and cash change."""

import tkinter as tk

import config
from widgets import HoverButton, center_window

C = config.COLORS
F = config.FONTS


class PaymentDialog(tk.Toplevel):
    """Modal payment dialog.

    After ``wait_window`` the result is in ``self.result`` (or ``None`` if the
    user cancelled). Result keys: payment_method, amount_paid, change_due,
    payable.
    """

    METHODS = ("Cash", "Card", "UPI")

    def __init__(self, master, total, customer=None):
        super().__init__(master)
        self.total = round(float(total), 2)
        self.result = None

        self.title("Payment")
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.transient(master)

        self.method_var = tk.StringVar(value="Cash")
        self.received_var = tk.StringVar(value=f"{self.total:.2f}")

        self._build()
        self._recalc()
        center_window(self, 380, 430, master)
        self.grab_set()
        self.received_entry.focus_set()
        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------ build
    def _build(self):
        tk.Label(self, text="Payment", bg=C["card"], fg=C["text"],
                 font=F["heading"]).pack(pady=(16, 2))
        self.payable_lbl = tk.Label(self, text="", bg=C["card"],
                                    fg=C["accent"],
                                    font=(config.FONT_FAMILY, 22, "bold"))
        self.payable_lbl.pack(pady=(0, 10))

        # payment method buttons
        mframe = tk.Frame(self, bg=C["card"])
        mframe.pack(pady=4)
        self.method_btns = {}
        for m in self.METHODS:
            b = HoverButton(mframe, C["tab_inactive"], "#94a3b8", text=m,
                            fg=C["text"], font=F["body_bold"], padx=18, pady=8,
                            command=lambda mm=m: self._set_method(mm))
            b.pack(side="left", padx=4)
            self.method_btns[m] = b

        # cash received
        cf = tk.Frame(self, bg=C["card"])
        cf.pack(fill="x", padx=24, pady=(14, 0))
        self.received_lbl = tk.Label(cf, text="Amount received", bg=C["card"],
                                     fg=C["text"], font=F["body"])
        self.received_lbl.pack(anchor="w")
        self.received_entry = tk.Entry(cf, textvariable=self.received_var,
                                       font=(config.FONT_FAMILY, 14),
                                       relief="solid", bd=1)
        self.received_entry.pack(fill="x", ipady=5)
        self.received_var.trace_add("write", lambda *_: self._recalc())

        # quick cash buttons
        qf = tk.Frame(self, bg=C["card"])
        qf.pack(fill="x", padx=24, pady=6)
        for amt in self._quick_amounts():
            HoverButton(qf, C["qty_btn"], "#cbd5e1", text=f"{amt:g}",
                        fg=C["text"], font=F["small"], padx=8, pady=4,
                        command=lambda a=amt: self.received_var.set(f"{a:.2f}")
                        ).pack(side="left", padx=3)

        # change / status
        self.change_lbl = tk.Label(self, text="", bg=C["card"],
                                   font=(config.FONT_FAMILY, 14, "bold"))
        self.change_lbl.pack(pady=12)

        # actions
        af = tk.Frame(self, bg=C["card"])
        af.pack(side="bottom", fill="x", padx=24, pady=16)
        self.confirm_btn = HoverButton(af, C["success"], "#15803d",
                                       text="✓ Confirm Sale", fg="white",
                                       font=F["checkout"], pady=11,
                                       command=self._confirm)
        self.confirm_btn.pack(fill="x")
        HoverButton(af, C["tab_inactive"], "#94a3b8", text="Cancel",
                    fg=C["text"], font=F["body_bold"], pady=8,
                    command=self.destroy).pack(fill="x", pady=(8, 0))

        self._set_method("Cash")

    def _quick_amounts(self):
        base = self.total
        opts = [base]
        for r in (50, 100, 500, 1000):
            up = ((int(base) // r) + 1) * r
            if up > base and up not in opts:
                opts.append(up)
        return sorted(set(opts))[:4]

    # --------------------------------------------------------------- logic
    def _set_method(self, method):
        self.method_var.set(method)
        for m, b in self.method_btns.items():
            if m == method:
                b.set_colors(C["accent"], C["accent_hover"])
                b.config(fg="white")
            else:
                b.set_colors(C["tab_inactive"], "#94a3b8")
                b.config(fg=C["text"])
        is_cash = method == "Cash"
        self.received_entry.config(state="normal" if is_cash else "disabled")
        self.received_lbl.config(
            fg=C["text"] if is_cash else C["text_muted"])
        self._recalc()

    def _recalc(self):
        cur = config.CURRENCY
        payable = self.total
        self.payable_lbl.config(text=f"{cur} {payable:.2f}")

        if self.method_var.get() == "Cash":
            try:
                received = float(self.received_var.get() or 0)
            except ValueError:
                received = 0
            change = round(received - payable, 2)
            if received < payable:
                self.change_lbl.config(
                    text=f"Short by {cur} {payable - received:.2f}",
                    fg=C["danger"])
                self.confirm_btn.config(state="disabled")
            else:
                self.change_lbl.config(text=f"Change: {cur} {change:.2f}",
                                       fg=C["success"])
                self.confirm_btn.config(state="normal")
        else:
            self.change_lbl.config(
                text=f"{self.method_var.get()} payment", fg=C["text_muted"])
            self.confirm_btn.config(state="normal")

    def _confirm(self):
        if str(self.confirm_btn["state"]) == "disabled":
            return
        payable = self.total
        method = self.method_var.get()
        if method == "Cash":
            try:
                received = float(self.received_var.get() or 0)
            except ValueError:
                received = payable
            change = round(received - payable, 2)
        else:
            received = payable
            change = 0.0
        self.result = {
            "payment_method": method,
            "amount_paid": received,
            "change_due": change,
            "payable": payable,
        }
        self.destroy()
