"""Quantity entry dialog with grams / kilograms support and live pricing."""

import tkinter as tk

import config
from widgets import HoverButton, center_window

C = config.COLORS
F = config.FONTS


def format_qty(unit, qty):
    """Human-friendly quantity: weights under 1 kg shown in grams."""
    if unit == "kg":
        if qty < 1:
            return f"{int(round(qty * 1000))} g"
        return f"{qty:g} kg"
    return f"{qty:g} {unit}"


class QuantityDialog(tk.Toplevel):
    """Edit the quantity of a cart item.

    After ``wait_window`` the chosen quantity (always in the product's base
    unit, i.e. kg for weighed items) is in ``self.result`` or ``None``.
    """

    def __init__(self, master, name, unit, price, current_qty):
        super().__init__(master)
        self.unit = unit
        self.price = price
        self.result = None
        self.is_weight = unit == "kg"

        self.title("Set quantity")
        self.configure(bg=C["card"])
        self.resizable(False, False)
        self.transient(master)

        # grams when the current amount is below 1 kg, else kg
        self.mode = tk.StringVar(value="g" if (self.is_weight and
                                               current_qty < 1) else "kg")
        start = (current_qty * 1000 if self.mode.get() == "g"
                 else current_qty)
        self.amount_var = tk.StringVar(value=f"{start:g}")

        self._build(name)
        self.amount_var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

        center_window(self, 340, 250 if self.is_weight else 210, master)
        self.grab_set()
        self.entry.focus_set()
        self.entry.select_range(0, "end")
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------ build
    def _build(self, name):
        tk.Label(self, text=name, bg=C["card"], fg=C["text"],
                 font=F["heading"]).pack(pady=(16, 2))
        tk.Label(self, text=f"{config.CURRENCY} {self.price:.2f} / {self.unit}",
                 bg=C["card"], fg=C["text_muted"], font=F["small"]).pack()

        row = tk.Frame(self, bg=C["card"])
        row.pack(pady=(14, 4), padx=24, fill="x")
        self.entry = tk.Entry(row, textvariable=self.amount_var,
                              font=(config.FONT_FAMILY, 18), relief="solid",
                              bd=1, justify="center")
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)

        if self.is_weight:
            toggle = tk.Frame(self, bg=C["card"])
            toggle.pack(pady=4)
            self.btn_g = HoverButton(toggle, C["accent"], C["accent_hover"],
                                     text="grams (g)", fg="white",
                                     font=F["body_bold"], padx=14, pady=6,
                                     command=lambda: self._set_mode("g"))
            self.btn_g.pack(side="left", padx=4)
            self.btn_kg = HoverButton(toggle, C["tab_inactive"], "#94a3b8",
                                      text="kilograms (kg)", fg=C["text"],
                                      font=F["body_bold"], padx=14, pady=6,
                                      command=lambda: self._set_mode("kg"))
            self.btn_kg.pack(side="left", padx=4)
            self._refresh_toggle()

        self.preview = tk.Label(self, text="", bg=C["card"], fg=C["accent"],
                                font=F["subhead"])
        self.preview.pack(pady=(8, 4))

        actions = tk.Frame(self, bg=C["card"])
        actions.pack(side="bottom", fill="x", padx=24, pady=14)
        HoverButton(actions, C["success"], "#15803d", text="✓ OK", fg="white",
                    font=F["body_bold"], pady=8, command=self._ok).pack(
                        side="left", fill="x", expand=True, padx=(0, 4))
        HoverButton(actions, C["tab_inactive"], "#94a3b8", text="Cancel",
                    fg=C["text"], font=F["body_bold"], pady=8,
                    command=self.destroy).pack(side="left", fill="x",
                                               expand=True, padx=(4, 0))

    # ------------------------------------------------------------------ logic
    def _set_mode(self, mode):
        if mode == self.mode.get():
            return
        # convert the current displayed value to the new unit
        qty_kg = self._to_kg()
        self.mode.set(mode)
        new_val = qty_kg * 1000 if mode == "g" else qty_kg
        self.amount_var.set(f"{new_val:g}")
        self._refresh_toggle()
        self._update_preview()

    def _refresh_toggle(self):
        if not self.is_weight:
            return
        g_active = self.mode.get() == "g"
        self.btn_g.set_colors(C["accent"] if g_active else C["tab_inactive"],
                              C["accent_hover"] if g_active else "#94a3b8")
        self.btn_g.config(fg="white" if g_active else C["text"])
        self.btn_kg.set_colors(C["tab_inactive"] if g_active else C["accent"],
                               "#94a3b8" if g_active else C["accent_hover"])
        self.btn_kg.config(fg=C["text"] if g_active else "white")

    def _amount(self):
        try:
            return float(self.amount_var.get())
        except ValueError:
            return None

    def _to_kg(self):
        n = self._amount()
        if n is None or n <= 0:
            return 0.0
        if self.is_weight and self.mode.get() == "g":
            return n / 1000.0
        return n

    def _update_preview(self):
        n = self._amount()
        if n is None or n <= 0:
            self.preview.config(text="Enter a valid amount", fg=C["danger"])
            return
        qty_kg = self._to_kg()
        total = qty_kg * self.price
        if self.is_weight:
            unit_txt = f"{n:g} {self.mode.get()}"
        else:
            unit_txt = f"{n:g} {self.unit}"
        self.preview.config(
            text=f"{unit_txt}  =  {config.CURRENCY} {total:.2f}",
            fg=C["accent"])

    def _ok(self):
        qty_kg = self._to_kg()
        if qty_kg <= 0:
            self._update_preview()
            return
        # round to gram precision for weights, whole-ish for counts
        self.result = round(qty_kg, 3)
        self.destroy()
