# Fresh Mart — Vegetable & Fruit Store Billing Software

A desktop point-of-sale / billing app built with Python **Tkinter**, **SQLite**,
**Pillow** and **ReportLab**, in a clean GoBill-style dark-blue & white theme.

## Features

- **Split-screen layout** — product grid on the left, live cart on the right.
- **Category tabs**: All Items, Bulb Vegetables, Flower Vegetables, Fruit Vegetables.
- **Product cards** in a scrollable grid with icon, name, price (per kg/piece)
  and a **stock line** that turns **red** when stock is low (< 5) or out.
- **Cart**: per-line name × quantity and price, `+` / `−` steppers, click the
  quantity to type a decimal value (e.g. `1.5 kg`), a remove (🗑) button, and a
  **🗑 Clear All** button at the top of the cart panel.
- **Customer name** field in the cart — stored with each bill.
- **Totals**: Total Items, Total Quantity, subtotal, discount and a big blue
  **Checkout** button showing the grand total.
- **Coupons**: type a code and press *Apply*. Built-in demo codes:
  `SAVE10` (10%), `SAVE20` (20%), `FRESH5` (5%).
- **Admin panel** (🛠 Manage): add / **edit** / delete products — name, price,
  unit, category, **stock quantity**, an optional image **and a custom emoji**.
  Low-stock rows are highlighted red.
- **Categories**: use **＋ New** next to the Category box to create a category
  (it appears as a tab immediately, even before it has products), or **🗑** to
  remove an empty one. You can also just type a new name in the Category box
  when saving a product. The 3 default categories are always kept.
- **Stock / inventory tracking**: stock is deducted automatically on checkout.
- **Billing**: checkout generates a **PDF receipt** (bill number, date,
  customer, itemized list, totals) saved in `receipts/`, and records the bill.
- **🧾 Invoice History** window: browse all past bills, **filter by month**,
  **search by customer name** (combinable), see the bill count and total for the
  current filter, and **🖨 Reprint PDF** for any past bill (or open its PDF).
- **📊 Daily Report** window: today's total sales, number of bills, items sold,
  discounts given, and the **top 5 selling products**.
- **Top bar** shows the date and a live **count of bills made today**.
- **🔍 Product search**: live type-to-filter search across all products.
- **💳 Payment dialog** at checkout: choose **Cash / Card / UPI**; for cash,
  enter amount received → **auto change**; quick-cash buttons. Payment method,
  amount paid and change are stored on the bill and printed on the receipt.
- **👥 Customers**: enter a phone at checkout to save the customer (name +
  phone). When you start typing a phone next time, a **suggestion dropdown**
  shows matching saved numbers — pick one to auto-fill the phone and name. The
  Customers window lists everyone with their bill count, total spent and full
  purchase history.
- **⚙ Settings & branding**: edit store name, tagline, address, phone, TRN/GSTIN,
  logo, currency and receipt footer in-app (logo & details appear on the PDF
  receipt).
- **💾 Backup & restore**: one-click timestamped backup of the database, and
  restore from any backup (a safety copy of the current data is made first).
- **📱 Mobile price/stock control**: a built-in web server lets you edit any
  product's **price and stock from your phone's browser** — changes save to the
  same `store.db` and the desktop grid refreshes automatically within a couple
  of seconds. See *Mobile access* below.
- **SQLite** storage in `store.db` (auto-created and seeded on first run;
  older databases are migrated automatically).

## Requirements

- Python 3.10+ (tested on 3.12)
- Packages: `Pillow`, `reportlab` (tkinter & sqlite3 ship with Python)

## Run

### Easiest (Windows)
Double-click **`run.bat`**. It installs dependencies and launches the app.

### Manual
```powershell
# from this folder
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pip install -r requirements.txt
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" app.py
```
> Python is installed at the path above but **not on PATH**, so use the full
> path (or add it to PATH and just run `python app.py`).

## Project layout

| File | Purpose |
|------|---------|
| `app.py`         | Main Tkinter application (UI, cart, checkout) |
| `admin.py`       | Product management dialog (add/edit/delete, stock, emoji) |
| `history.py`     | Invoice History window (month filter, search, reprint) |
| `report.py`      | Daily Sales Report popup |
| `payment.py`     | Checkout payment dialog (method, cash change) |
| `customers.py`   | Customers window (saved phones + purchase history) |
| `settings_window.py` | Settings, branding, mobile access & backup/restore |
| `quantity_dialog.py` | Quantity entry with grams/kg toggle + live pricing |
| `web_server.py`  | Built-in mobile web server (edit price/stock by phone) |
| `updater.py`     | Auto-update: GitHub version check, download & restart |
| `database.py`    | SQLite layer (products, bills, bill_items) + seed data |
| `pdf_receipt.py` | ReportLab PDF receipt generation |
| `image_utils.py` | Product image loading + coloured initial placeholders |
| `widgets.py`     | Reusable scrollable frame & hover button |
| `config.py`      | Theme, colours, fonts, paths, currency |
| `store.db`       | SQLite database (auto-created) |
| `product_images/`| Uploaded product images |
| `receipts/`      | Generated PDF receipts |

## Mobile access (edit price & stock from your phone)

The app can run a small web server so you can change product **price and stock**
from a phone. It writes to the same `store.db`, so there is a single source of
truth — no syncing, no extra account, no monthly fee.

**On the shop WiFi (works out of the box):**
1. Open **⚙ Settings → 📱 Mobile / Remote Access**, tick **Enable mobile
   access**, set a **PIN**, Save, and **restart the app**.
2. Settings shows a URL like `http://192.168.0.128:8080/`. On your phone
   (connected to the same WiFi) open that URL.
3. Log in — username can be anything, password is the **PIN**.
4. Edit any product's price/stock and tap **Save**. The shop PC updates within
   ~2–3 seconds.

**From outside the shop (optional):** point a free tunnel at the same port so
the URL works from anywhere over HTTPS. Easiest is **Cloudflare Tunnel**:
1. Install `cloudflared` (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
2. Run: `cloudflared tunnel --url http://localhost:8080`
3. It prints a public `https://….trycloudflare.com` link — open that on your
   phone from anywhere. (For a permanent address, set up a named tunnel.)

> Security: the PIN protects edits. On the local network it is plain HTTP; over
> a Cloudflare/ngrok tunnel it is HTTPS-encrypted. Keep the PC on and online for
> the phone to reach it. This feature requires the `flask` package
> (`pip install -r requirements.txt`).

## Notes

- Change the currency by editing `CURRENCY` in `config.py` (`"AED"` → `"Rs."`).
- Products without an uploaded image show an auto-generated coloured tile with
  their initials, so the grid always looks complete.
- Quantity step is `0.5` for `kg` items and `1` for piece/bunch/pack items;
  click the quantity number to enter any decimal value.
