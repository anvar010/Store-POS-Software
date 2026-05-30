"""Application-wide configuration and theme constants (GoBill-style dark-blue / white)."""

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "store.db")
IMAGES_DIR = os.path.join(BASE_DIR, "product_images")
RECEIPTS_DIR = os.path.join(BASE_DIR, "receipts")
BACKUPS_DIR = os.path.join(BASE_DIR, "backups")

for _d in (IMAGES_DIR, RECEIPTS_DIR, BACKUPS_DIR):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------------
# Store / branding defaults (overridable in the in-app Settings screen)
# ---------------------------------------------------------------------------
CURRENCY = "Rs."          # change to "AED" if preferred
STORE_NAME = "Fresh Mart"
STORE_TAGLINE = "Fresh Vegetables & Fruits"

# ---------------------------------------------------------------------------
# Auto-update  (edit these URLs to point at your own GitHub repo)
# ---------------------------------------------------------------------------
APP_VERSION = "1.0"
GITHUB_USER = "yourusername"
GITHUB_REPO = "freshmart-billing"
UPDATE_VERSION_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}"
    "/main/version.txt"
)
UPDATE_EXE_URL = (
    f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
    "/releases/latest/download/FreshMart_Billing.exe"
)

# ---------------------------------------------------------------------------
# Mobile / remote access (built-in web server) — overridable in Settings
# ---------------------------------------------------------------------------
MOBILE_ENABLED = False
MOBILE_PORT = 8080
MOBILE_PIN = "1234"
STORE_ADDRESS = ""
STORE_PHONE = ""
STORE_TRN = ""            # tax / GST / TRN registration number
RECEIPT_FOOTER = "Thank you for shopping with us!"
LOGO_PATH = ""            # absolute path or filename in product_images/

# Keys persisted in the settings table and their runtime attribute names
SETTING_KEYS = {
    "currency": "CURRENCY",
    "store_name": "STORE_NAME",
    "store_tagline": "STORE_TAGLINE",
    "store_address": "STORE_ADDRESS",
    "store_phone": "STORE_PHONE",
    "store_trn": "STORE_TRN",
    "receipt_footer": "RECEIPT_FOOTER",
    "logo_path": "LOGO_PATH",
}


def apply_settings(values):
    """Overwrite runtime branding values from a {key: value} dict."""
    g = globals()
    for key, attr in SETTING_KEYS.items():
        if key in values and values[key] not in (None, ""):
            g[attr] = values[key]


def _load_overrides():
    """Best-effort load of saved settings at import time (before UI caches)."""
    import sqlite3
    if not os.path.exists(DB_PATH):
        return
    try:
        con = sqlite3.connect(DB_PATH)
        rows = con.execute("SELECT key, value FROM settings").fetchall()
        con.close()
    except Exception:
        return
    apply_settings(dict(rows))


_load_overrides()

# ---------------------------------------------------------------------------
# Colour theme  (dark-blue & white, GoBill style)
# ---------------------------------------------------------------------------
COLORS = {
    "primary":        "#1a2b5c",   # deep navy (sidebars / headers)
    "primary_dark":   "#11203f",
    "accent":         "#2563eb",   # bright blue (checkout button, highlights)
    "accent_hover":   "#1d4ed8",
    "bg":             "#f4f6fb",   # main background
    "card":           "#ffffff",   # cards / panels
    "card_border":    "#e2e8f0",
    "text":           "#1e293b",   # primary text
    "text_muted":     "#64748b",   # secondary text
    "text_light":     "#ffffff",
    "success":        "#16a34a",
    "danger":         "#dc2626",
    "danger_hover":   "#b91c1c",
    "warning":        "#f59e0b",
    "tab_active":     "#2563eb",
    "tab_inactive":   "#cbd5e1",
    "qty_btn":        "#e2e8f0",
}

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_FAMILY = "Segoe UI"
FONTS = {
    "title":    (FONT_FAMILY, 20, "bold"),
    "heading":  (FONT_FAMILY, 14, "bold"),
    "subhead":  (FONT_FAMILY, 12, "bold"),
    "body":     (FONT_FAMILY, 10),
    "body_bold": (FONT_FAMILY, 10, "bold"),
    "small":    (FONT_FAMILY, 9),
    "small_bold": (FONT_FAMILY, 9, "bold"),
    "price":    (FONT_FAMILY, 11, "bold"),
    "checkout": (FONT_FAMILY, 14, "bold"),
}

# Default product categories
CATEGORIES = [
    "Bulb Vegetables",
    "Flower Vegetables",
    "Fruit Vegetables",
]

CARD_WIDTH = 150
CARD_HEIGHT = 180
GRID_COLUMNS = 4
