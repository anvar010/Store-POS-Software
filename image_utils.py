"""Image loading and placeholder generation using Pillow."""

import os
import hashlib

from PIL import Image, ImageDraw, ImageFont, ImageTk

import config

# cache of PhotoImage objects so Tk doesn't garbage-collect them
_CACHE = {}

_PALETTE = [
    "#16a34a", "#ea580c", "#dc2626", "#7c3aed", "#0891b2",
    "#ca8a04", "#db2777", "#2563eb", "#65a30d", "#9333ea",
]

# Soft tinted background for icon tiles
_TILE_BG = "#eef2fb"

# Map product names (and keywords) to a representative emoji icon.
_EMOJI = {
    "onion": "🧅", "shallot": "🧅", "spring onion": "🧅",
    "garlic": "🧄",
    "leek": "🥬", "cabbage": "🥬", "lettuce": "🥬", "spinach": "🥬",
    "broccoli": "🥦",
    "cauliflower": "🥦",
    "artichoke": "🌿",
    "tomato": "🍅",
    "cucumber": "🥒", "zucchini": "🥒",
    "bell pepper": "🫑", "pepper": "🫑", "capsicum": "🫑",
    "eggplant": "🍆", "brinjal": "🍆", "aubergine": "🍆",
    "pumpkin": "🎃", "squash": "🎃",
    "chilli": "🌶", "chili": "🌶", "green chilli": "🌶",
    "carrot": "🥕", "potato": "🥔", "corn": "🌽", "mushroom": "🍄",
    "avocado": "🥑", "beans": "🫛", "peas": "🫛", "ginger": "🫚",
    # fruits
    "apple": "🍎", "banana": "🍌", "grapes": "🍇", "orange": "🍊",
    "lemon": "🍋", "mango": "🥭", "strawberry": "🍓", "watermelon": "🍉",
    "pineapple": "🍍", "peach": "🍑", "pear": "🍐", "cherry": "🍒",
    "kiwi": "🥝", "coconut": "🥥", "melon": "🍈",
}


def _font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _emoji_font(size):
    """Windows colour-emoji font; returns None if unavailable."""
    try:
        return ImageFont.truetype("seguiemj.ttf", size)
    except OSError:
        return None


def _lookup_emoji(name):
    key = name.strip().lower()
    if key in _EMOJI:
        return _EMOJI[key]
    # keyword match (e.g. "Red Onion" -> onion)
    for word, emj in _EMOJI.items():
        if word in key:
            return emj
    return None


def guess_emoji(name, default="🥗"):
    """Public helper: best-matching emoji for a product name.

    Falls back to a generic produce emoji when nothing matches so a new
    product always gets *some* icon. Pass default=None to skip the fallback.
    """
    return _lookup_emoji(name) or default


def _placeholder(name, size, emoji=None):
    """An icon tile: a matching emoji on a soft background, or initials."""
    emoji = emoji or _lookup_emoji(name)
    font = _emoji_font(int(size * 0.66)) if emoji else None

    if emoji and font is not None:
        img = Image.new("RGB", (size, size), _TILE_BG)
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), emoji, font=font, embedded_color=True)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1])
        draw.text(pos, emoji, font=font, embedded_color=True)
        return img

    # fallback: coloured tile with initials
    idx = int(hashlib.md5(name.encode()).hexdigest(), 16) % len(_PALETTE)
    img = Image.new("RGB", (size, size), _PALETTE[idx])
    draw = ImageDraw.Draw(img)
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    tfont = _font(int(size * 0.42))
    bbox = draw.textbbox((0, 0), initials, font=tfont)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
              initials, fill="white", font=tfont)
    return img


def get_product_image(name, image_path=None, size=110, emoji=None):
    """Return a Tk PhotoImage for a product, falling back to a placeholder."""
    key = f"{name}|{image_path}|{size}|{emoji}"
    if key in _CACHE:
        return _CACHE[key]

    img = None
    if image_path:
        full = image_path
        if not os.path.isabs(full):
            full = os.path.join(config.IMAGES_DIR, image_path)
        if os.path.exists(full):
            try:
                img = Image.open(full).convert("RGB")
                img = _fit_square(img, size)
            except Exception:
                img = None

    if img is None:
        img = _placeholder(name, size, emoji)

    photo = ImageTk.PhotoImage(img)
    _CACHE[key] = photo
    return photo


def _fit_square(img, size):
    """Center-crop to a square then resize."""
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    return img.resize((size, size), Image.LANCZOS)
