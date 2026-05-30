"""Vegetable / Fruit store billing software — main Tkinter application."""

import os
import sys
import subprocess
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import config
from database import Database
from widgets import ScrollableFrame, HoverButton, center_window
from admin import AdminPanel
from history import HistoryWindow
from report import ReportWindow
from settings_window import SettingsWindow
from customers import CustomersWindow
from payment import PaymentDialog
from quantity_dialog import QuantityDialog, format_qty
import image_utils
import pdf_receipt
import updater
import web_server

C = config.COLORS
F = config.FONTS
CUR = config.CURRENCY


class CartItem:
    def __init__(self, product):
        self.id = product["id"]
        self.name = product["name"]
        self.price = product["price"]
        self.unit = product["unit"]
        self.qty = 1.0

    @property
    def line_total(self):
        return self.price * self.qty


class BillingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.cart = {}            # product_id -> CartItem
        self.active_category = "All Items"
        self.discount_pct = 0.0   # applied coupon percentage

        self.latest_version = None     # set by the updater thread
        self.title(f"{config.STORE_NAME} — Billing  v{config.APP_VERSION}")
        self.configure(bg=C["bg"])
        self.geometry("1180x720")
        self.minsize(960, 600)

        self._build_header()
        self._build_body()
        self._render_tabs()
        self._render_products()
        self._render_cart()
        self._refresh_bill_count()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # auto-update: silent background check, thread-safe UI callback
        self.bind(updater.UPDATE_EVENT, self._on_update_available)
        updater.start_check(self)

        # mobile / remote access web server (price & stock from phone)
        self._remote_seen = 0
        self._start_mobile_server()
        self._poll_remote_changes()

    def _refresh_bill_count(self):
        n = self.db.today_bill_count()
        self.bill_count_lbl.config(text=f"🧾 {n} bill(s) today")

    # ----------------------------------------------------- mobile server
    def _start_mobile_server(self):
        """Start the phone web server when enabled in Settings."""
        enabled = self.db.get_setting("mobile_enabled", "0") == "1"
        if not enabled or not web_server.is_available():
            return
        port = int(self.db.get_setting("mobile_port", config.MOBILE_PORT))
        pin = self.db.get_setting("mobile_pin", config.MOBILE_PIN)
        url, ok = web_server.start(self.db.db_path, port, pin)
        if ok:
            self._remote_seen = web_server.STATE["version"]

    def _poll_remote_changes(self):
        """Refresh tabs + product grid when the phone edits/adds/deletes."""
        try:
            if web_server.STATE["version"] != self._remote_seen:
                self._remote_seen = web_server.STATE["version"]
                self._on_products_changed()   # re-renders tabs and grid
        except Exception:
            pass
        self.after(2500, self._poll_remote_changes)

    # ===================================================================== UI
    def _build_header(self):
        header = tk.Frame(self, bg=C["primary"], height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        self.title_lbl = tk.Label(header, text=f"🥬  {config.STORE_NAME}",
                                   bg=C["primary"], fg=C["text_light"],
                                   font=F["title"])
        self.title_lbl.pack(side="left", padx=(20, 4))
        self.version_lbl = tk.Label(header, text=f"v{config.APP_VERSION}",
                                    bg=C["primary"], fg="#7dd3fc",
                                    font=F["small_bold"])
        self.version_lbl.pack(side="left", padx=(0, 8))

        # date + today's bill counter
        info = tk.Frame(header, bg=C["primary"])
        info.pack(side="left", padx=8)
        tk.Label(info, text=datetime.now().strftime("%a, %d %b %Y"),
                 bg=C["primary"], fg="#aab4d4", font=F["small"]).pack(
                     anchor="w")
        self.bill_count_lbl = tk.Label(info, text="", bg=C["primary"],
                                       fg="#7dd3fc", font=F["small_bold"])
        self.bill_count_lbl.pack(anchor="w")

        HoverButton(header, C["accent"], C["accent_hover"],
                    text="🛠  Manage", fg="white", font=F["body_bold"],
                    padx=12, pady=8, command=self._open_admin
                    ).pack(side="right", padx=(6, 20))
        for text, cmd in (("🧾  History", self._open_history),
                          ("📊  Report", self._open_report),
                          ("👥  Customers", self._open_customers),
                          ("⚙  Settings", self._open_settings)):
            HoverButton(header, C["primary_dark"], "#0b1730", text=text,
                        fg="white", font=F["body_bold"], padx=12, pady=8,
                        command=cmd).pack(side="right", padx=6)

    def _build_body(self):
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)

        # ---- LEFT (products) ---------------------------------------------
        left = tk.Frame(body, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(12, 6),
                  pady=12)

        # search box
        search_row = tk.Frame(left, bg=C["card"], bd=1, relief="solid",
                              highlightbackground=C["card_border"])
        search_row.pack(fill="x", pady=(0, 10))
        tk.Label(search_row, text="🔍", bg=C["card"], fg=C["text_muted"],
                 font=F["body"]).pack(side="left", padx=(10, 0))
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_row, textvariable=self.search_var,
                                font=F["body"], relief="flat", bd=0)
        search_entry.pack(side="left", fill="x", expand=True, padx=8, ipady=7)
        self.search_var.trace_add("write", lambda *_: self._on_search())
        self._search_clear = HoverButton(
            search_row, C["card"], C["bg"], text="✕", fg=C["text_muted"],
            font=F["body"], padx=10, command=lambda: self.search_var.set(""))

        self.tabs_frame = tk.Frame(left, bg=C["bg"])
        self.tabs_frame.pack(fill="x", pady=(0, 10))

        self.product_scroll = ScrollableFrame(left, bg=C["bg"])
        self.product_scroll.pack(fill="both", expand=True)
        self.product_grid = self.product_scroll.body

        # ---- RIGHT (cart) ------------------------------------------------
        right = tk.Frame(body, bg=C["card"], width=380, bd=1, relief="solid",
                         highlightbackground=C["card_border"])
        right.pack(side="right", fill="y", padx=(6, 12), pady=12)
        right.pack_propagate(False)
        self._build_cart_panel(right)

    def _build_cart_panel(self, parent):
        cart_head = tk.Frame(parent, bg=C["primary"], height=50)
        cart_head.pack(fill="x")
        cart_head.pack_propagate(False)
        tk.Label(cart_head, text="🛒  Cart", bg=C["primary"],
                 fg=C["text_light"], font=F["heading"]).pack(side="left",
                                                             padx=16)
        HoverButton(cart_head, C["danger"], C["danger_hover"],
                    text="🗑 Clear All", fg="white", font=F["small_bold"],
                    padx=10, pady=5,
                    command=self._clear_cart).pack(side="right", padx=12)

        # scrollable list of cart items
        self.cart_scroll = ScrollableFrame(parent, bg=C["card"])
        self.cart_scroll.pack(fill="both", expand=True)
        self.cart_body = self.cart_scroll.body

        # ---- footer (totals + coupon + checkout) -------------------------
        footer = tk.Frame(parent, bg=C["card"])
        footer.pack(fill="x", side="bottom")

        tk.Frame(footer, bg=C["card_border"], height=1).pack(fill="x")

        # customer name + phone
        cust = tk.Frame(footer, bg=C["card"])
        cust.pack(fill="x", padx=16, pady=(10, 2))
        tk.Label(cust, text="👤", bg=C["card"], fg=C["text_muted"],
                 font=F["body"]).pack(side="left")
        self.customer_var = tk.StringVar()
        self.customer_entry = tk.Entry(cust, textvariable=self.customer_var,
                                       font=F["body"], relief="solid", bd=1)
        self.customer_entry.pack(side="left", fill="x", expand=True,
                                 padx=(6, 0), ipady=4)
        self._add_placeholder(self.customer_entry, self.customer_var,
                              "Customer name (optional)")

        phone = tk.Frame(footer, bg=C["card"])
        phone.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(phone, text="📞", bg=C["card"], fg=C["text_muted"],
                 font=F["body"]).pack(side="left")
        self.phone_var = tk.StringVar()
        self.phone_entry = tk.Entry(phone, textvariable=self.phone_var,
                                    font=F["body"], relief="solid", bd=1)
        self.phone_entry.pack(side="left", fill="x", expand=True,
                              padx=(6, 0), ipady=4)
        self._add_placeholder(self.phone_entry, self.phone_var,
                              "Phone (optional)")
        self._phone_popup = None
        self.phone_entry.bind("<KeyRelease>", self._on_phone_key)
        self.phone_entry.bind("<FocusOut>",
                              lambda e: self.after(180,
                                                   self._hide_phone_suggestions),
                              add="+")
        self.phone_entry.bind("<Escape>",
                              lambda e: self._hide_phone_suggestions())
        self.phone_entry.bind("<Down>", self._focus_suggestions)

        stats = tk.Frame(footer, bg=C["card"])
        stats.pack(fill="x", padx=16, pady=(6, 4))
        self.lbl_items = tk.Label(stats, text="Total Items: 0", bg=C["card"],
                                  fg=C["text_muted"], font=F["small"])
        self.lbl_items.pack(side="left")
        self.lbl_qty = tk.Label(stats, text="Total Qty: 0", bg=C["card"],
                                fg=C["text_muted"], font=F["small"])
        self.lbl_qty.pack(side="right")

        # coupon row
        coupon = tk.Frame(footer, bg=C["card"])
        coupon.pack(fill="x", padx=16, pady=(4, 6))
        self.coupon_var = tk.StringVar()
        tk.Entry(coupon, textvariable=self.coupon_var, font=F["body"],
                 relief="solid", bd=1,
                 ).pack(side="left", fill="x", expand=True, ipady=5)
        HoverButton(coupon, C["primary"], C["primary_dark"], text="Apply",
                    fg="white", font=F["small"], padx=10,
                    command=self._apply_coupon).pack(side="left", padx=(6, 0))
        self.lbl_coupon = tk.Label(footer, text="", bg=C["card"],
                                   fg=C["success"], font=F["small"])
        self.lbl_coupon.pack(anchor="w", padx=16)

        # subtotal / discount
        self.lbl_subtotal = tk.Label(footer, text="", bg=C["card"],
                                     fg=C["text_muted"], font=F["body"])
        self.lbl_subtotal.pack(anchor="e", padx=16)
        self.lbl_discount = tk.Label(footer, text="", bg=C["card"],
                                     fg=C["danger"], font=F["body"])

        # checkout button
        self.checkout_btn = HoverButton(
            footer, C["accent"], C["accent_hover"],
            text="Checkout", fg="white", font=F["checkout"], pady=14,
            command=self._checkout)
        self.checkout_btn.pack(fill="x", padx=16, pady=14)

    # -------------------------------------------------------- placeholder
    def _add_placeholder(self, entry, var, text):
        """Grey placeholder text shown while the entry is empty/unfocused."""
        entry._placeholder = text
        entry._is_placeholder = False

        def show():
            if not var.get():
                entry._is_placeholder = True
                entry.config(fg=C["text_muted"])
                var.set(text)

        def on_focus_in(_e):
            if entry._is_placeholder:
                entry._is_placeholder = False
                var.set("")
                entry.config(fg=C["text"])

        def on_focus_out(_e):
            if not var.get():
                show()

        entry.config(fg=C["text"])
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        entry._show_placeholder = show
        show()

    def _get_customer_name(self):
        entry_val = self.customer_var.get().strip()
        # ignore placeholder text
        if entry_val == "Customer name (optional)":
            return ""
        return entry_val

    def _get_phone(self):
        val = self.phone_var.get().strip()
        if val == "Phone (optional)":
            return ""
        return val

    # ------------------------------------------------ phone autocomplete
    def _on_phone_key(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        query = self._get_phone()
        if len(query) < 2:
            self._hide_phone_suggestions()
            return
        matches = self.db.suggest_customers(query)
        if matches:
            self._show_phone_suggestions(matches)
        else:
            self._hide_phone_suggestions()

    def _show_phone_suggestions(self, matches):
        if self._phone_popup is None or not self._phone_popup.winfo_exists():
            self._phone_popup = tk.Toplevel(self)
            self._phone_popup.wm_overrideredirect(True)
            self._phone_popup.configure(bg=C["accent"], bd=1)
            self._sugg_list = tk.Listbox(
                self._phone_popup, font=F["body"], height=6,
                activestyle="none", bd=0, highlightthickness=0,
                bg=C["card"], fg=C["text"],
                selectbackground=C["accent"], selectforeground="white")
            self._sugg_list.pack(fill="both", expand=True, padx=1, pady=1)
            self._sugg_list.bind("<<ListboxSelect>>",
                                 lambda e: self._pick_suggestion())
            self._sugg_list.bind("<Return>",
                                 lambda e: self._pick_suggestion())
            self._sugg_list.bind("<Escape>",
                                 lambda e: self._hide_phone_suggestions())

        self._sugg_data = matches
        self._sugg_list.delete(0, "end")
        for c in matches:
            name = c["name"] if c["name"] and c["name"] != "Walk-in" else ""
            label = f"  {c['phone']}" + (f"   —   {name}" if name else "")
            self._sugg_list.insert("end", label)

        self.phone_entry.update_idletasks()
        x = self.phone_entry.winfo_rootx()
        y = self.phone_entry.winfo_rooty() + self.phone_entry.winfo_height()
        w = self.phone_entry.winfo_width()
        h = min(len(matches), 6) * 24 + 4
        self._phone_popup.wm_geometry(f"{w}x{h}+{x}+{y}")
        self._phone_popup.deiconify()
        self._phone_popup.lift()

    def _focus_suggestions(self, _event=None):
        if self._phone_popup and self._phone_popup.winfo_exists():
            self._sugg_list.focus_set()
            self._sugg_list.selection_clear(0, "end")
            self._sugg_list.selection_set(0)
            self._sugg_list.activate(0)

    def _pick_suggestion(self):
        if not (self._phone_popup and self._phone_popup.winfo_exists()):
            return
        sel = self._sugg_list.curselection()
        if not sel:
            return
        cust = self._sugg_data[sel[0]]
        # fill phone
        self.phone_entry._is_placeholder = False
        self.phone_entry.config(fg=C["text"])
        self.phone_var.set(cust["phone"])
        # fill name too when known
        if cust["name"] and cust["name"] != "Walk-in":
            self.customer_entry._is_placeholder = False
            self.customer_entry.config(fg=C["text"])
            self.customer_var.set(cust["name"])
        self._hide_phone_suggestions()
        self.phone_entry.focus_set()
        self.phone_entry.icursor("end")

    def _hide_phone_suggestions(self):
        if self._phone_popup and self._phone_popup.winfo_exists():
            self._phone_popup.withdraw()

    # --------------------------------------------------------------- tabs
    def _render_tabs(self):
        for w in self.tabs_frame.winfo_children():
            w.destroy()
        categories = ["All Items"] + self.db.get_categories()
        self._tab_buttons = {}
        for cat in categories:
            active = cat == self.active_category
            btn = HoverButton(
                self.tabs_frame,
                C["tab_active"] if active else C["card"],
                C["accent_hover"] if active else C["tab_inactive"],
                text=cat,
                fg="white" if active else C["text"],
                font=F["body_bold"], padx=16, pady=9,
                command=lambda c=cat: self._select_category(c))
            btn.pack(side="left", padx=(0, 8))
            self._tab_buttons[cat] = btn

    def _select_category(self, cat):
        self.active_category = cat
        self._render_tabs()
        self._render_products()
        self.product_scroll.scroll_to_top()

    def _on_search(self):
        # show/hide the clear button, then re-render
        if self.search_var.get():
            self._search_clear.pack(side="right", padx=(0, 4))
        else:
            self._search_clear.pack_forget()
        self._render_products()

    # --------------------------------------------------------------- products
    def _render_products(self):
        for w in self.product_grid.winfo_children():
            w.destroy()

        query = self.search_var.get().strip().lower()
        # a search spans all categories; otherwise honour the active tab
        category = None if query else self.active_category
        products = self.db.get_products(category)
        if query:
            products = [p for p in products if query in p["name"].lower()]

        cols = config.GRID_COLUMNS
        for c in range(cols):
            self.product_grid.columnconfigure(c, weight=1, uniform="prod")

        if not products:
            msg = (f"No products match “{self.search_var.get().strip()}”."
                   if query else "No products in this category.")
            tk.Label(self.product_grid, text=msg, bg=C["bg"],
                     fg=C["text_muted"], font=F["body"]
                     ).grid(row=0, column=0, columnspan=cols, pady=40)
            return

        for idx, p in enumerate(products):
            r, c = divmod(idx, cols)
            self._product_card(p, r, c)

    def _product_card(self, product, row, col):
        card = tk.Frame(self.product_grid, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"],
                        highlightthickness=1)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

        photo = image_utils.get_product_image(product["name"],
                                              product.get("image"), size=110,
                                              emoji=product.get("emoji"))
        img_lbl = tk.Label(card, image=photo, bg=C["card"])
        img_lbl.image = photo
        img_lbl.pack(pady=(10, 6))

        tk.Label(card, text=product["name"], bg=C["card"], fg=C["text"],
                 font=F["body_bold"], wraplength=130).pack()
        tk.Label(card, text=f"{CUR} {product['price']:.2f} / {product['unit']}",
                 bg=C["card"], fg=C["accent"], font=F["price"]).pack(
                     pady=(2, 2))

        # stock line (red + warning when low)
        stock = product.get("stock", 0) or 0
        if stock <= 0:
            stock_txt, stock_fg = "Out of stock", C["danger"]
        elif stock < 5:
            stock_txt = f"⚠ Low stock: {stock:g} {product['unit']}"
            stock_fg = C["danger"]
        else:
            stock_txt = f"In stock: {stock:g} {product['unit']}"
            stock_fg = C["text_muted"]
        tk.Label(card, text=stock_txt, bg=C["card"], fg=stock_fg,
                 font=F["small"]).pack(pady=(0, 6))

        add = HoverButton(card, C["primary"], C["primary_dark"],
                          text="+ Add", fg="white", font=F["small"],
                          pady=6, command=lambda: self._add_to_cart(product))
        add.pack(fill="x", padx=10, pady=(0, 10))

        # make whole card clickable too
        for w in (card, img_lbl):
            w.bind("<Button-1>", lambda e, pr=product: self._add_to_cart(pr))

    # --------------------------------------------------------------- cart ops
    def _add_to_cart(self, product):
        item = self.cart.get(product["id"])
        if item:
            item.qty += 1
        else:
            self.cart[product["id"]] = CartItem(product)
        self._render_cart()

    def _change_qty(self, pid, delta):
        item = self.cart.get(pid)
        if not item:
            return
        # weighed items step by 250 g, counted items by 1
        step = 0.25 if item.unit == "kg" else 1.0
        item.qty = round(item.qty + delta * step, 3)
        if item.qty <= 0:
            del self.cart[pid]
        self._render_cart()

    def _set_qty(self, pid):
        item = self.cart.get(pid)
        if not item:
            return
        dlg = QuantityDialog(self, item.name, item.unit, item.price, item.qty)
        self.wait_window(dlg)
        if dlg.result and dlg.result > 0:
            item.qty = dlg.result
            self._render_cart()

    def _remove_item(self, pid):
        self.cart.pop(pid, None)
        self._render_cart()

    def _clear_cart(self):
        if self.cart and messagebox.askyesno("Clear cart",
                                             "Remove all items from the cart?"):
            self.cart.clear()
            self.discount_pct = 0.0
            self.coupon_var.set("")
            self.lbl_coupon.config(text="")
            self._render_cart()

    # --------------------------------------------------------------- cart view
    def _render_cart(self):
        for w in self.cart_body.winfo_children():
            w.destroy()

        if not self.cart:
            tk.Label(self.cart_body, text="\n🛒\n\nYour cart is empty.\n"
                     "Tap a product to add it.", bg=C["card"],
                     fg=C["text_muted"], font=F["body"], justify="center"
                     ).pack(pady=40)

        for item in self.cart.values():
            self._cart_row(item)

        self._update_totals()

    def _cart_row(self, item):
        row = tk.Frame(self.cart_body, bg=C["card"])
        row.pack(fill="x", padx=12, pady=6)

        top = tk.Frame(row, bg=C["card"])
        top.pack(fill="x")
        tk.Label(top, text=item.name, bg=C["card"], fg=C["text"],
                 font=F["body_bold"], anchor="w").pack(side="left")
        tk.Label(top, text=f"{CUR} {item.line_total:.2f}", bg=C["card"],
                 fg=C["accent"], font=F["price"]).pack(side="right")

        bottom = tk.Frame(row, bg=C["card"])
        bottom.pack(fill="x", pady=(4, 0))

        # qty stepper
        stepper = tk.Frame(bottom, bg=C["card"])
        stepper.pack(side="left")
        HoverButton(stepper, C["qty_btn"], "#cbd5e1", text="−",
                    fg=C["text"], font=F["body_bold"], width=2,
                    command=lambda: self._change_qty(item.id, -1)
                    ).pack(side="left")
        qty_lbl = tk.Label(stepper, text=format_qty(item.unit, item.qty),
                           bg=C["card"], fg=C["text"], font=F["body_bold"],
                           width=8, cursor="hand2")
        qty_lbl.pack(side="left", padx=2)
        qty_lbl.bind("<Button-1>", lambda e: self._set_qty(item.id))
        HoverButton(stepper, C["qty_btn"], "#cbd5e1", text="+",
                    fg=C["text"], font=F["body_bold"], width=2,
                    command=lambda: self._change_qty(item.id, +1)
                    ).pack(side="left")

        tk.Label(bottom, text=f"@ {CUR} {item.price:.2f}", bg=C["card"],
                 fg=C["text_muted"], font=F["small"]).pack(side="left",
                                                           padx=8)

        HoverButton(bottom, C["card"], "#fee2e2", text="🗑", fg=C["danger"],
                    font=F["body"], command=lambda: self._remove_item(item.id)
                    ).pack(side="right")

        tk.Frame(row, bg=C["card_border"], height=1).pack(fill="x",
                                                          pady=(6, 0))

    # ------------------------------------------------------------- totals
    def _compute_totals(self):
        subtotal = sum(i.line_total for i in self.cart.values())
        discount = round(subtotal * self.discount_pct / 100.0, 2)
        total = round(subtotal - discount, 2)
        total_items = len(self.cart)
        total_qty = sum(i.qty for i in self.cart.values())
        return subtotal, discount, total, total_items, total_qty

    def _update_totals(self):
        subtotal, discount, total, n_items, qty = self._compute_totals()
        self.lbl_items.config(text=f"Total Items: {n_items}")
        self.lbl_qty.config(text=f"Total Qty: {qty:g}")
        self.lbl_subtotal.config(text=f"Subtotal:  {CUR} {subtotal:.2f}")

        if discount > 0:
            self.lbl_discount.config(
                text=f"Discount ({self.discount_pct:g}%):  - {CUR} "
                     f"{discount:.2f}")
            self.lbl_discount.pack(anchor="e", padx=16)
        else:
            self.lbl_discount.pack_forget()

        self.checkout_btn.config(text=f"Checkout   •   {CUR} {total:.2f}")

    def _apply_coupon(self):
        """Built-in demo coupons: SAVE10, SAVE20, FRESH5."""
        code = self.coupon_var.get().strip().upper()
        coupons = {"SAVE10": 10, "SAVE20": 20, "FRESH5": 5}
        if not code:
            self.discount_pct = 0.0
            self.lbl_coupon.config(text="", fg=C["success"])
        elif code in coupons:
            self.discount_pct = coupons[code]
            self.lbl_coupon.config(
                text=f"✓ Coupon '{code}' applied ({coupons[code]}% off)",
                fg=C["success"])
        else:
            self.discount_pct = 0.0
            self.lbl_coupon.config(text="✗ Invalid coupon code",
                                   fg=C["danger"])
        self._update_totals()

    # ------------------------------------------------------------- checkout
    def _checkout(self):
        if not self.cart:
            messagebox.showinfo("Cart empty",
                                "Add some products before checkout.")
            return

        subtotal, discount, total, _, _ = self._compute_totals()
        customer = self._get_customer_name() or "Walk-in"
        phone = self._get_phone()

        # payment dialog (method, change)
        dlg = PaymentDialog(self, total)
        self.wait_window(dlg)
        if not dlg.result:
            return                       # cancelled — keep the cart intact
        pay = dlg.result

        items = [{
            "product_id": i.id, "name": i.name, "unit": i.unit,
            "quantity": i.qty, "price": i.price,
            "line_total": round(i.line_total, 2),
        } for i in self.cart.values()]

        # save the customer when a phone number was entered
        customer_id = self.db.upsert_customer(customer, phone) if phone else None

        bill_number = self.db.next_bill_number()
        bill_id, created_at = self.db.save_bill(
            bill_number, items, subtotal, discount, total,
            customer_name=customer, customer_id=customer_id,
            payment_method=pay["payment_method"],
            amount_paid=pay["amount_paid"], change_due=pay["change_due"])

        # deduct stock for each sold product
        for i in self.cart.values():
            self.db.deduct_stock(i.id, i.qty)

        try:
            pdf_path = pdf_receipt.generate_receipt(
                bill_number, created_at, items, subtotal, discount, total,
                customer_name=customer, payment=pay,
                customer_phone=phone or None)
            self.db.set_bill_pdf(bill_id, pdf_path)
        except Exception as exc:  # PDF must not block the sale
            pdf_path = None
            messagebox.showwarning(
                "Receipt",
                f"Sale recorded but PDF generation failed:\n{exc}")

        self._show_checkout_success(bill_number, pay["payable"], pdf_path,
                                    pay)

        # reset for next customer
        self.cart.clear()
        self.discount_pct = 0.0
        self.coupon_var.set("")
        self.lbl_coupon.config(text="")
        self.customer_var.set("")
        self.phone_var.set("")
        self.customer_entry._show_placeholder()
        self.phone_entry._show_placeholder()
        self._render_cart()
        self._render_products()       # reflect new stock levels
        self._refresh_bill_count()

    def _show_checkout_success(self, bill_number, total, pdf_path, pay=None):
        win = tk.Toplevel(self)
        win.title("Checkout complete")
        win.configure(bg=C["card"])
        win.transient(self)
        center_window(win, 360, 300, self)
        win.grab_set()

        tk.Label(win, text="✓", bg=C["card"], fg=C["success"],
                 font=(config.FONT_FAMILY, 48, "bold")).pack(pady=(20, 2))
        tk.Label(win, text="Payment Successful", bg=C["card"], fg=C["text"],
                 font=F["heading"]).pack()
        tk.Label(win, text=f"Bill {bill_number}", bg=C["card"],
                 fg=C["text_muted"], font=F["body"]).pack(pady=2)
        tk.Label(win, text=f"{CUR} {total:.2f}", bg=C["card"], fg=C["accent"],
                 font=F["title"]).pack(pady=4)

        if pay:
            line = f"{pay['payment_method']}"
            if pay["payment_method"] == "Cash" and pay.get("change_due", 0):
                line += (f"  •  Paid {CUR} {pay['amount_paid']:.2f}"
                         f"  •  Change {CUR} {pay['change_due']:.2f}")
            tk.Label(win, text=line, bg=C["card"], fg=C["text_muted"],
                     font=F["small"]).pack()

        btns = tk.Frame(win, bg=C["card"])
        btns.pack(pady=12)
        if pdf_path:
            HoverButton(btns, C["accent"], C["accent_hover"],
                        text="Open Receipt", fg="white", font=F["body_bold"],
                        padx=14, pady=8,
                        command=lambda: self._open_file(pdf_path)
                        ).pack(side="left", padx=6)
        HoverButton(btns, C["tab_inactive"], "#94a3b8", text="Close",
                    fg=C["text"], font=F["body_bold"], padx=14, pady=8,
                    command=win.destroy).pack(side="left", padx=6)

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: pylint stdlib on win
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as exc:
            messagebox.showerror("Open", f"Could not open file:\n{exc}")

    # ------------------------------------------------------------- admin
    def _open_admin(self):
        AdminPanel(self, self.db, on_change=self._on_products_changed)

    def _open_history(self):
        HistoryWindow(self, self.db)

    def _open_report(self):
        ReportWindow(self, self.db)

    def _open_customers(self):
        CustomersWindow(self, self.db)

    def _open_settings(self):
        SettingsWindow(self, self.db, on_saved=self._on_settings_saved,
                       on_restored=self._on_restored)

    def _on_settings_saved(self):
        self.title_lbl.config(text=f"🥬  {config.STORE_NAME}")
        self.title(f"{config.STORE_NAME} — Billing  v{config.APP_VERSION}")

    def _on_restored(self):
        """Reload everything after a database file was restored."""
        self.db = Database()
        config.apply_settings(self.db.get_settings())
        self.cart.clear()
        self.active_category = "All Items"
        self.discount_pct = 0.0
        self._on_settings_saved()
        self._render_tabs()
        self._render_products()
        self._render_cart()
        self._refresh_bill_count()

    def _on_products_changed(self):
        # category may have been added/removed; reset if it disappeared
        cats = ["All Items"] + self.db.get_categories()
        if self.active_category not in cats:
            self.active_category = "All Items"
        self._render_tabs()
        self._render_products()

    # ------------------------------------------------------------- updates
    def _on_update_available(self, _event=None):
        """Fired (thread-safe) when the background check finds a newer build."""
        latest = self.latest_version
        if not latest:
            return
        if messagebox.askyesno(
                "Update available",
                f"New update available!  Version {latest}\n\n"
                "Click Yes to update now, or No to skip.",
                parent=self):
            self._download_update(latest)

    def _download_update(self, latest):
        prog = tk.Toplevel(self)
        prog.title("Updating")
        prog.configure(bg=C["card"])
        prog.transient(self)
        center_window(prog, 340, 150, self)
        prog.grab_set()
        prog.protocol("WM_DELETE_WINDOW", lambda: None)  # block close mid-update

        tk.Label(prog, text=f"Downloading version {latest}…", bg=C["card"],
                 fg=C["text"], font=F["body_bold"]).pack(pady=(20, 6))
        bar = ttk.Progressbar(prog, mode="determinate", length=280,
                              maximum=100)
        bar.pack(pady=4)
        status = tk.Label(prog, text="Starting…", bg=C["card"],
                          fg=C["text_muted"], font=F["small"])
        status.pack(pady=4)

        def on_progress(done, total):
            if total:
                pct = done * 100 // total
                self.after(0, lambda: (bar.config(value=pct),
                                       status.config(
                                           text=f"{done // 1024} / "
                                                f"{total // 1024} KB")))
            else:
                self.after(0, lambda: status.config(
                    text=f"{done // 1024} KB"))

        def worker():
            try:
                new_path = updater.download_update(progress=on_progress)
            except Exception as exc:
                self.after(0, lambda: self._update_failed(prog, exc))
                return
            self.after(0, lambda: self._apply_update(prog, new_path))

        threading.Thread(target=worker, daemon=True,
                         name="update-download").start()

    def _update_failed(self, prog, exc):
        prog.destroy()
        messagebox.showerror(
            "Update failed",
            f"Could not download the update:\n{exc}", parent=self)

    def _apply_update(self, prog, new_path):
        try:
            self.db.close()
        except Exception:
            pass
        try:
            # does not return on success (relaunches via helper, exits)
            updater.apply_update_and_restart(new_path)
        except Exception as exc:
            prog.destroy()
            messagebox.showinfo(
                "Update downloaded",
                f"The new version was downloaded to:\n{new_path}\n\n"
                f"({exc})", parent=self)

    def _on_close(self):
        self.db.close()
        self.destroy()


def main():
    app = BillingApp()
    app.mainloop()


if __name__ == "__main__":
    main()
