"""SQLite data-access layer for the vegetable/fruit store billing app."""

import sqlite3
from datetime import datetime

import config


class Database:
    """Thin wrapper around the SQLite store database."""

    def __init__(self, db_path=config.DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        # wait instead of failing when the mobile web server writes concurrently
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self._create_tables()
        self._migrate()
        self._seed_if_empty()
        self._seed_categories()

    # ------------------------------------------------------------------ setup
    def _create_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT    NOT NULL,
                price     REAL    NOT NULL,
                unit      TEXT    NOT NULL DEFAULT 'kg',
                category  TEXT    NOT NULL,
                image     TEXT,
                emoji     TEXT,
                stock     REAL    NOT NULL DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bills (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_number   TEXT    NOT NULL UNIQUE,
                customer_name TEXT    NOT NULL DEFAULT 'Walk-in',
                created_at    TEXT    NOT NULL,
                subtotal      REAL    NOT NULL,
                discount      REAL    NOT NULL DEFAULT 0,
                total         REAL    NOT NULL,
                total_items   INTEGER NOT NULL,
                total_qty     REAL    NOT NULL,
                pdf_path      TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT    NOT NULL UNIQUE
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                phone      TEXT UNIQUE,
                points     REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bill_items (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_id      INTEGER NOT NULL,
                product_id   INTEGER,
                product_name TEXT    NOT NULL,
                unit         TEXT    NOT NULL,
                quantity     REAL    NOT NULL,
                price        REAL    NOT NULL,
                line_total   REAL    NOT NULL,
                FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
            )
            """
        )
        self.conn.commit()

    def _migrate(self):
        """Add columns to databases created by older versions."""
        self._ensure_column("products", "emoji", "emoji TEXT")
        self._ensure_column("products", "stock", "stock REAL NOT NULL DEFAULT 0")
        self._ensure_column("bills", "customer_name",
                            "customer_name TEXT NOT NULL DEFAULT 'Walk-in'")
        self._ensure_column("bills", "customer_id", "customer_id INTEGER")
        self._ensure_column("bills", "payment_method",
                            "payment_method TEXT DEFAULT 'Cash'")
        self._ensure_column("bills", "amount_paid", "amount_paid REAL DEFAULT 0")
        self._ensure_column("bills", "change_due", "change_due REAL DEFAULT 0")
        self._ensure_column("bills", "points_earned",
                            "points_earned REAL DEFAULT 0")
        self._ensure_column("bills", "points_redeemed",
                            "points_redeemed REAL DEFAULT 0")
        self._ensure_column("bill_items", "product_id", "product_id INTEGER")

    def _ensure_column(self, table, column, ddl):
        cur = self.conn.cursor()
        cols = [r["name"] for r in cur.execute(f"PRAGMA table_info({table})")]
        if column not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            self.conn.commit()

    def _seed_if_empty(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM products")
        if cur.fetchone()["c"] > 0:
            return
        sample = [
            # name, price, unit, category, emoji, stock
            ("Onion", 3.50, "kg", "Bulb Vegetables", "🧅", 40),
            ("Garlic", 9.00, "kg", "Bulb Vegetables", "🧄", 25),
            ("Shallot", 6.50, "kg", "Bulb Vegetables", "🧅", 18),
            ("Spring Onion", 4.00, "kg", "Bulb Vegetables", "🧅", 12),
            ("Leek", 5.00, "kg", "Bulb Vegetables", "🥬", 8),
            ("Broccoli", 8.00, "kg", "Flower Vegetables", "🥦", 15),
            ("Cauliflower", 5.50, "kg", "Flower Vegetables", "🥦", 20),
            ("Artichoke", 12.00, "piece", "Flower Vegetables", "🌿", 6),
            ("Cabbage", 3.00, "kg", "Flower Vegetables", "🥬", 30),
            ("Tomato", 4.50, "kg", "Fruit Vegetables", "🍅", 50),
            ("Cucumber", 3.50, "kg", "Fruit Vegetables", "🥒", 35),
            ("Bell Pepper", 7.00, "kg", "Fruit Vegetables", "🫑", 22),
            ("Eggplant", 4.00, "kg", "Fruit Vegetables", "🍆", 16),
            ("Zucchini", 5.00, "kg", "Fruit Vegetables", "🥒", 14),
            ("Pumpkin", 3.50, "kg", "Fruit Vegetables", "🎃", 10),
            ("Green Chilli", 8.50, "kg", "Fruit Vegetables", "🌶", 9),
        ]
        cur.executemany(
            "INSERT INTO products (name, price, unit, category, image, emoji, "
            "stock) VALUES (?, ?, ?, ?, NULL, ?, ?)",
            sample,
        )
        self.conn.commit()

    # --------------------------------------------------------------- products
    def get_products(self, category=None):
        cur = self.conn.cursor()
        if category and category != "All Items":
            cur.execute(
                "SELECT * FROM products WHERE category = ? ORDER BY name",
                (category,),
            )
        else:
            cur.execute("SELECT * FROM products ORDER BY category, name")
        return [dict(r) for r in cur.fetchall()]

    def get_product(self, product_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def add_product(self, name, price, unit, category, image=None,
                    emoji=None, stock=0):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO products (name, price, unit, category, image, emoji, "
            "stock) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, price, unit, category, image, emoji or None, stock),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_product(self, product_id, name, price, unit, category,
                       image=None, emoji=None, stock=0):
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE products SET name=?, price=?, unit=?, category=?, image=?, "
            "emoji=?, stock=? WHERE id=?",
            (name, price, unit, category, image, emoji or None, stock,
             product_id),
        )
        self.conn.commit()

    def delete_product(self, product_id):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def deduct_stock(self, product_id, qty):
        """Reduce stock for a product, never below zero."""
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?",
            (qty, product_id),
        )
        self.conn.commit()

    def _seed_categories(self):
        """Make sure the default categories always exist."""
        cur = self.conn.cursor()
        for c in config.CATEGORIES:
            cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)",
                        (c,))
        self.conn.commit()

    def get_categories(self):
        """All known categories: the saved list plus any used by products."""
        cur = self.conn.cursor()
        cats = {r["name"] for r in cur.execute("SELECT name FROM categories")}
        cats.update(r["category"] for r in
                    cur.execute("SELECT DISTINCT category FROM products"))
        return sorted(cats)

    def add_category(self, name):
        name = (name or "").strip()
        if not name:
            return False
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (name,))
        self.conn.commit()
        return True

    def delete_category(self, name):
        """Remove a category. Products keep their category text untouched."""
        cur = self.conn.cursor()
        cur.execute("DELETE FROM categories WHERE name=?", (name,))
        self.conn.commit()

    # ------------------------------------------------------------------ bills
    def next_bill_number(self):
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM bills")
        n = cur.fetchone()["c"] + 1
        return f"INV-{datetime.now():%Y%m%d}-{n:04d}"

    def save_bill(self, bill_number, items, subtotal, discount, total,
                  customer_name="Walk-in", pdf_path=None, customer_id=None,
                  payment_method="Cash", amount_paid=0, change_due=0,
                  points_earned=0, points_redeemed=0):
        """items: dicts with name, unit, quantity, price, line_total and
        optionally product_id."""
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_items = len(items)
        total_qty = sum(i["quantity"] for i in items)
        customer_name = (customer_name or "Walk-in").strip() or "Walk-in"
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO bills (bill_number, customer_name, customer_id, "
            "created_at, subtotal, discount, total, total_items, total_qty, "
            "payment_method, amount_paid, change_due, points_earned, "
            "points_redeemed, pdf_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (bill_number, customer_name, customer_id, created_at, subtotal,
             discount, total, total_items, total_qty, payment_method,
             amount_paid, change_due, points_earned, points_redeemed,
             pdf_path),
        )
        bill_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO bill_items (bill_id, product_id, product_name, unit, "
            "quantity, price, line_total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(bill_id, i.get("product_id"), i["name"], i["unit"],
              i["quantity"], i["price"], i["line_total"]) for i in items],
        )
        self.conn.commit()
        return bill_id, created_at

    def set_bill_pdf(self, bill_id, pdf_path):
        cur = self.conn.cursor()
        cur.execute("UPDATE bills SET pdf_path=? WHERE id=?",
                    (pdf_path, bill_id))
        self.conn.commit()

    def search_bills(self, customer_query=None, month=None):
        """Return bills, newest first.

        customer_query : substring match on customer name.
        month          : 'YYYY-MM' string to limit to one calendar month.
        """
        clauses, params = [], []
        if customer_query:
            clauses.append("customer_name LIKE ?")
            params.append(f"%{customer_query.strip()}%")
        if month:
            clauses.append("substr(created_at, 1, 7) = ?")
            params.append(month)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        cur = self.conn.cursor()
        cur.execute(f"SELECT * FROM bills{where} ORDER BY id DESC", params)
        return [dict(r) for r in cur.fetchall()]

    def get_bill_months(self):
        """Distinct months that have bills, newest first ('YYYY-MM')."""
        cur = self.conn.cursor()
        cur.execute("SELECT DISTINCT substr(created_at, 1, 7) AS ym "
                    "FROM bills ORDER BY ym DESC")
        return [r["ym"] for r in cur.fetchall()]

    def get_bill(self, bill_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM bills WHERE id=?", (bill_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_bill_items(self, bill_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT product_name AS name, unit, quantity, price, line_total "
            "FROM bill_items WHERE bill_id=? ORDER BY id", (bill_id,))
        return [dict(r) for r in cur.fetchall()]

    # --------------------------------------------------------------- reports
    def today_bill_count(self, date=None):
        date = date or datetime.now().strftime("%Y-%m-%d")
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM bills WHERE created_at LIKE ?",
                    (f"{date}%",))
        return cur.fetchone()["c"]

    def daily_report(self, date=None):
        """Return today's totals and top selling products."""
        date = date or datetime.now().strftime("%Y-%m-%d")
        like = f"{date}%"
        cur = self.conn.cursor()
        cur.execute(
            "SELECT COUNT(*) AS bills, "
            "COALESCE(SUM(total), 0) AS sales, "
            "COALESCE(SUM(discount), 0) AS discount, "
            "COALESCE(SUM(total_qty), 0) AS qty "
            "FROM bills WHERE created_at LIKE ?", (like,))
        summary = dict(cur.fetchone())

        cur.execute(
            "SELECT bi.product_name AS name, "
            "SUM(bi.quantity) AS qty, SUM(bi.line_total) AS revenue "
            "FROM bill_items bi JOIN bills b ON bi.bill_id = b.id "
            "WHERE b.created_at LIKE ? "
            "GROUP BY bi.product_name "
            "ORDER BY revenue DESC LIMIT 5", (like,))
        top = [dict(r) for r in cur.fetchall()]
        summary["top"] = top
        summary["date"] = date
        return summary

    # --------------------------------------------------------------- settings
    def get_settings(self):
        cur = self.conn.cursor()
        return {r["key"]: r["value"]
                for r in cur.execute("SELECT key, value FROM settings")}

    def get_setting(self, key, default=None):
        cur = self.conn.cursor()
        row = cur.execute("SELECT value FROM settings WHERE key=?",
                          (key,)).fetchone()
        return row["value"] if row else default

    def set_settings(self, values):
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            [(k, str(v)) for k, v in values.items()])
        self.conn.commit()

    # -------------------------------------------------------------- customers
    def find_customer_by_phone(self, phone):
        phone = (phone or "").strip()
        if not phone:
            return None
        cur = self.conn.cursor()
        row = cur.execute("SELECT * FROM customers WHERE phone=?",
                          (phone,)).fetchone()
        return dict(row) if row else None

    def get_customer(self, customer_id):
        cur = self.conn.cursor()
        row = cur.execute("SELECT * FROM customers WHERE id=?",
                          (customer_id,)).fetchone()
        return dict(row) if row else None

    def upsert_customer(self, name, phone):
        """Create or fetch a customer by phone; returns the customer id.

        Customers with no phone are not stored (treated as walk-ins)."""
        phone = (phone or "").strip()
        name = (name or "").strip() or "Walk-in"
        if not phone:
            return None
        existing = self.find_customer_by_phone(phone)
        cur = self.conn.cursor()
        if existing:
            if name and name != existing["name"]:
                cur.execute("UPDATE customers SET name=? WHERE id=?",
                            (name, existing["id"]))
                self.conn.commit()
            return existing["id"]
        cur.execute(
            "INSERT INTO customers (name, phone, points, created_at) "
            "VALUES (?, ?, 0, ?)",
            (name, phone, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()
        return cur.lastrowid

    def adjust_points(self, customer_id, delta):
        if not customer_id:
            return
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE customers SET points = MAX(0, points + ?) WHERE id=?",
            (delta, customer_id))
        self.conn.commit()

    def suggest_customers(self, phone_query, limit=8):
        """Customers whose phone matches the typed digits (for autocomplete)."""
        phone_query = (phone_query or "").strip()
        if not phone_query:
            return []
        cur = self.conn.cursor()
        cur.execute(
            "SELECT * FROM customers WHERE phone LIKE ? ORDER BY phone LIMIT ?",
            (f"%{phone_query}%", limit))
        return [dict(r) for r in cur.fetchall()]

    def list_customers(self, query=None):
        cur = self.conn.cursor()
        if query:
            q = f"%{query.strip()}%"
            cur.execute("SELECT * FROM customers WHERE name LIKE ? OR "
                        "phone LIKE ? ORDER BY name", (q, q))
        else:
            cur.execute("SELECT * FROM customers ORDER BY name")
        return [dict(r) for r in cur.fetchall()]

    def customer_bills(self, customer_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM bills WHERE customer_id=? ORDER BY id DESC",
                    (customer_id,))
        return [dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()
