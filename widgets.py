"""Reusable Tkinter widgets."""

import tkinter as tk

import config


def center_window(win, width, height, parent=None):
    """Position a Toplevel centred over its parent (or the screen)."""
    win.update_idletasks()
    if parent is not None and parent.winfo_viewable():
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
    else:
        px = py = 0
        pw, ph = win.winfo_screenwidth(), win.winfo_screenheight()
    x = max(0, px + (pw - width) // 2)
    y = max(0, py + (ph - height) // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


class ScrollableFrame(tk.Frame):
    """A vertically scrollable frame. Add children to ``self.body``."""

    def __init__(self, parent, bg=None, **kwargs):
        bg = bg or config.COLORS["bg"]
        super().__init__(parent, bg=bg, **kwargs)

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical",
                                      command=self.canvas.yview)
        self.body = tk.Frame(self.canvas, bg=bg)

        self._win = self.canvas.create_window((0, 0), window=self.body,
                                              anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.body.bind("<Configure>", self._on_body_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Mouse-wheel only while the pointer is over this canvas
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_body_configure(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._win, width=event.width)

    def _bind_wheel(self, _e):
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", self._on_wheel)
        self.canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _e):
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_wheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1, "units")

    def scroll_to_top(self):
        self.canvas.yview_moveto(0)


class HoverButton(tk.Button):
    """A flat button that changes colour on hover."""

    def __init__(self, parent, bg, hover_bg, **kwargs):
        super().__init__(parent, bg=bg, activebackground=hover_bg,
                         bd=0, relief="flat", cursor="hand2", **kwargs)
        self._bg = bg
        self._hover = hover_bg
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))

    def set_colors(self, bg, hover_bg):
        self._bg, self._hover = bg, hover_bg
        self.config(bg=bg, activebackground=hover_bg)
