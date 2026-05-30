"""Admin panel: add / edit / delete products."""

import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

import config
from widgets import HoverButton, center_window
import image_utils

C = config.COLORS
F = config.FONTS


class AdminPanel(tk.Toplevel):
    def __init__(self, master, db, on_change=None):
        super().__init__(master)
        self.db = db
        self.on_change = on_change
        self.selected_id = None
        self._image_src = None  # path chosen this session

        self.title("Product Management")
        self.configure(bg=C["bg"])
        self.minsize(820, 600)
        self.transient(master)

        self._build()
        self._reload_list()
        center_window(self, 820, 640, master)
        self.grab_set()

    # ------------------------------------------------------------------ build
    def _build(self):
        header = tk.Frame(self, bg=C["primary"], height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🛠  Product Management", bg=C["primary"],
                 fg=C["text_light"], font=F["heading"]).pack(side="left",
                                                             padx=20)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=14, pady=14)

        # ---- left: product list -------------------------------------------
        left = tk.Frame(body, bg=C["card"], bd=1, relief="solid",
                        highlightbackground=C["card_border"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Products", bg=C["card"], fg=C["text"],
                 font=F["subhead"]).pack(anchor="w", padx=12, pady=(10, 4))

        cols = ("name", "price", "unit", "category", "stock")
        self.tree = ttk.Treeview(left, columns=cols, show="headings",
                                 height=18)
        for c, w in zip(cols, (140, 65, 55, 130, 55)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        self.tree.tag_configure("low", foreground=C["danger"])
        self.tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # ---- right: form --------------------------------------------------
        right = tk.Frame(body, bg=C["card"], bd=1, relief="solid",
                         highlightbackground=C["card_border"], width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Product Details", bg=C["card"], fg=C["text"],
                 font=F["subhead"]).pack(anchor="w", padx=16, pady=(12, 8))

        # Action buttons — packed at the bottom FIRST so they always stay
        # visible even when the form above is tall.
        btns = tk.Frame(right, bg=C["card"])
        btns.pack(fill="x", padx=16, pady=16, side="bottom")
        HoverButton(btns, C["success"], "#15803d", text="💾  Save",
                    fg="white", font=F["body_bold"], pady=9,
                    command=self._save).pack(fill="x", pady=(0, 6))
        HoverButton(btns, C["danger"], C["danger_hover"], text="🗑  Delete",
                    fg="white", font=F["body_bold"], pady=9,
                    command=self._delete).pack(fill="x", pady=(0, 6))
        HoverButton(btns, C["tab_inactive"], "#94a3b8", text="＋  Clear / New",
                    fg=C["text"], font=F["body_bold"], pady=9,
                    command=self._clear).pack(fill="x")
        tk.Frame(right, bg=C["card_border"], height=1).pack(
            fill="x", side="bottom", padx=12, pady=(4, 0))

        self.var_name = tk.StringVar()
        self.var_price = tk.StringVar()
        self.var_unit = tk.StringVar(value="kg")
        self.var_cat = tk.StringVar(value=config.CATEGORIES[0])
        self.var_emoji = tk.StringVar()
        self.var_stock = tk.StringVar(value="0")

        self._field(right, "Name", self.var_name)
        # live-preview the auto emoji as the name is typed
        self.var_name.trace_add(
            "write", lambda *_: self._show_image(self.var_name.get() or "?",
                                                 self._image_src))

        # price + stock side by side
        row2 = tk.Frame(right, bg=C["card"])
        row2.pack(fill="x", padx=16, pady=(10, 0))
        col_a = tk.Frame(row2, bg=C["card"])
        col_a.pack(side="left", fill="x", expand=True, padx=(0, 6))
        col_b = tk.Frame(row2, bg=C["card"])
        col_b.pack(side="left", fill="x", expand=True)
        tk.Label(col_a, text=f"Price ({config.CURRENCY})", bg=C["card"],
                 fg=C["text_muted"], font=F["small"]).pack(anchor="w")
        tk.Entry(col_a, textvariable=self.var_price, font=F["body"],
                 relief="solid", bd=1).pack(fill="x", ipady=4)
        tk.Label(col_b, text="Stock", bg=C["card"], fg=C["text_muted"],
                 font=F["small"]).pack(anchor="w")
        tk.Entry(col_b, textvariable=self.var_stock, font=F["body"],
                 relief="solid", bd=1).pack(fill="x", ipady=4)

        self._label(right, "Unit")
        ttk.Combobox(right, textvariable=self.var_unit,
                     values=["kg", "piece", "bunch", "pack"],
                     state="readonly").pack(fill="x", padx=16)

        self._label(right, "Category")
        crow = tk.Frame(right, bg=C["card"])
        crow.pack(fill="x", padx=16)
        self.cat_combo = ttk.Combobox(crow, textvariable=self.var_cat,
                                      values=self.db.get_categories())
        self.cat_combo.pack(side="left", fill="x", expand=True)
        HoverButton(crow, C["primary"], C["primary_dark"], text="＋ New",
                    fg="white", font=F["small"], padx=10,
                    command=self._new_category).pack(side="left", padx=(6, 0))
        HoverButton(crow, C["danger"], C["danger_hover"], text="🗑",
                    fg="white", font=F["small"], padx=8,
                    command=self._delete_category).pack(side="left",
                                                        padx=(4, 0))

        self._label(right, "Emoji / icon (optional)")
        erow = tk.Frame(right, bg=C["card"])
        erow.pack(fill="x", padx=16)
        tk.Entry(erow, textvariable=self.var_emoji, font=F["body"],
                 relief="solid", bd=1, width=6).pack(side="left", ipady=4)
        tk.Label(erow, text="e.g. 🍅 🥦 🧅 (leave blank for auto)",
                 bg=C["card"], fg=C["text_muted"], font=F["small"]).pack(
                     side="left", padx=6)
        self.var_emoji.trace_add(
            "write", lambda *_: self._show_image(self.var_name.get() or "?",
                                                 self._image_src))

        # image picker
        self._label(right, "Image (optional)")
        img_row = tk.Frame(right, bg=C["card"])
        img_row.pack(fill="x", padx=16)
        self.img_label = tk.Label(img_row, text="No image", bg=C["bg"],
                                  fg=C["text_muted"], width=10, height=5)
        self.img_label.pack(side="left")
        HoverButton(img_row, C["accent"], C["accent_hover"], text="Browse…",
                    fg="white", font=F["small"], padx=10, pady=6,
                    command=self._choose_image).pack(side="left", padx=8)

    def _label(self, parent, text):
        tk.Label(parent, text=text, bg=C["card"], fg=C["text_muted"],
                 font=F["small"]).pack(anchor="w", padx=16, pady=(10, 2))

    def _field(self, parent, label, var):
        self._label(parent, label)
        tk.Entry(parent, textvariable=var, font=F["body"], relief="solid",
                 bd=1).pack(fill="x", padx=16, ipady=4)

    # ------------------------------------------------------------ categories
    def _new_category(self):
        name = simpledialog.askstring(
            "New Category", "Enter the new category name:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        self.db.add_category(name)
        self.cat_combo["values"] = self.db.get_categories()
        self.var_cat.set(name)
        if self.on_change:          # refresh the tabs in the main window
            self.on_change()

    def _delete_category(self):
        name = self.var_cat.get().strip()
        if not name:
            return
        products = [p for p in self.db.get_products() if p["category"] == name]
        if products:
            messagebox.showwarning(
                "Category in use",
                f"'{name}' still has {len(products)} product(s).\n"
                "Move or delete those products first.", parent=self)
            return
        if messagebox.askyesno("Delete category",
                               f"Delete the category '{name}'?", parent=self):
            self.db.delete_category(name)
            cats = self.db.get_categories()
            self.cat_combo["values"] = cats
            self.var_cat.set(cats[0] if cats else "")
            if self.on_change:
                self.on_change()

    # --------------------------------------------------------------- actions
    def _reload_list(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.db.get_products():
            stock = p.get("stock", 0) or 0
            tags = ("low",) if stock < 5 else ()
            self.tree.insert("", "end", iid=str(p["id"]), tags=tags,
                             values=(p["name"], f"{p['price']:.2f}",
                                     p["unit"], p["category"], f"{stock:g}"))
        self.cat_combo["values"] = self.db.get_categories()

    def _on_select(self, _e):
        sel = self.tree.selection()
        if not sel:
            return
        self.selected_id = int(sel[0])
        p = self.db.get_product(self.selected_id)
        if not p:
            return
        self.var_name.set(p["name"])
        self.var_price.set(f"{p['price']:.2f}")
        self.var_unit.set(p["unit"])
        self.var_cat.set(p["category"])
        self.var_emoji.set(p.get("emoji") or "")
        self.var_stock.set(f"{(p.get('stock') or 0):g}")
        self._image_src = p["image"]
        self._show_image(p["name"], p["image"])

    def _choose_image(self):
        path = filedialog.askopenfilename(
            title="Choose product image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if path:
            self._image_src = path
            self._show_image(self.var_name.get() or "?", path)

    def _show_image(self, name, path):
        emoji = self.var_emoji.get().strip() or None
        # mirror save behaviour: no image + no emoji -> auto-assigned emoji
        if not path and not emoji:
            emoji = image_utils.guess_emoji(name)
        photo = image_utils.get_product_image(name, path, size=70,
                                              emoji=emoji)
        self.img_label.config(image=photo, text="")
        self.img_label.image = photo

    def _persist_image(self, name):
        """Copy a freshly-chosen image into product_images, return filename."""
        src = self._image_src
        if not src:
            return None
        # already stored relative filename → keep as-is
        if not os.path.isabs(src):
            return src
        ext = os.path.splitext(src)[1].lower()
        safe = "".join(c for c in name if c.isalnum() or c in " _-").strip()
        dest_name = f"{safe or 'product'}_{abs(hash(src)) % 10000}{ext}"
        dest = os.path.join(config.IMAGES_DIR, dest_name)
        try:
            shutil.copyfile(src, dest)
            return dest_name
        except Exception:
            return None

    def _validate(self):
        name = self.var_name.get().strip()
        if not name:
            messagebox.showerror("Invalid", "Name is required.", parent=self)
            return None
        try:
            price = float(self.var_price.get())
            if price < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Enter a valid price.",
                                 parent=self)
            return None
        try:
            stock = float(self.var_stock.get() or 0)
            if stock < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid", "Enter a valid stock quantity.",
                                 parent=self)
            return None
        cat = self.var_cat.get().strip() or config.CATEGORIES[0]
        emoji = self.var_emoji.get().strip() or None
        return name, price, self.var_unit.get(), cat, emoji, stock

    def _save(self):
        data = self._validate()
        if not data:
            return
        name, price, unit, cat, emoji, stock = data
        image = self._persist_image(name)
        # no image and no emoji typed → auto-assign a matching emoji
        if not image and not emoji:
            emoji = image_utils.guess_emoji(name)
        if self.selected_id:
            self.db.update_product(self.selected_id, name, price, unit, cat,
                                   image, emoji, stock)
        else:
            self.db.add_product(name, price, unit, cat, image, emoji, stock)
        self._reload_list()
        self._clear()
        if self.on_change:
            self.on_change()

    def _delete(self):
        if not self.selected_id:
            messagebox.showinfo("Delete", "Select a product first.",
                                parent=self)
            return
        if messagebox.askyesno("Delete",
                               "Delete the selected product?", parent=self):
            self.db.delete_product(self.selected_id)
            self._reload_list()
            self._clear()
            if self.on_change:
                self.on_change()

    def _clear(self):
        self.selected_id = None
        self._image_src = None
        self.var_name.set("")
        self.var_price.set("")
        self.var_unit.set("kg")
        self.var_cat.set(config.CATEGORIES[0])
        self.var_emoji.set("")
        self.var_stock.set("0")
        self.img_label.config(image="", text="No image")
        self.img_label.image = None
        if self.tree.selection():
            self.tree.selection_remove(self.tree.selection())
