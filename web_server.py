"""Built-in mobile web server: edit product price & stock from a phone.

Runs in a background daemon thread inside the desktop app and reads/writes the
SAME store.db, so there is a single source of truth (no sync conflicts). On a
shared WiFi the phone just opens http://<pc-ip>:<port>/. For access from
outside the shop, point a free Cloudflare Tunnel / ngrok at the same port.
"""

import socket
import sqlite3
import threading
import logging

try:
    from flask import (Flask, request, Response, jsonify,
                       render_template_string)
    _FLASK_OK = True
except Exception:                       # Flask not installed
    _FLASK_OK = False

import config

# Shared state so the desktop app can detect remote edits and refresh.
STATE = {"version": 0, "running": False, "url": ""}
_DB_PATH = config.DB_PATH
_PIN = "1234"
_started = False


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def get_lan_ip():
    """Best-effort primary LAN IP of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _open():
    con = sqlite3.connect(_DB_PATH, timeout=5)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def _categories(con):
    cats = {r["name"] for r in con.execute("SELECT name FROM categories")}
    cats.update(r["category"] for r in
                con.execute("SELECT DISTINCT category FROM products"))
    return sorted(cats)


def _ensure_category(con, name):
    name = (name or "").strip()
    if name:
        con.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)",
                    (name,))


def _guess_emoji(name):
    try:
        import image_utils
        return image_utils.guess_emoji(name)
    except Exception:
        return None


def is_available():
    return _FLASK_OK


# --------------------------------------------------------------------------
# Flask app
# --------------------------------------------------------------------------
if _FLASK_OK:
    app = Flask(__name__)

    _UNITS = ["kg", "piece", "bunch", "pack"]

    _PAGE = """<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{store}} — Products</title>
<style>
 :root{--navy:#1a2b5c;--accent:#2563eb;--bg:#f4f6fb;--card:#fff;
       --muted:#64748b;--ok:#16a34a;--danger:#dc2626;}
 *{box-sizing:border-box;font-family:-apple-system,Segoe UI,Roboto,sans-serif;}
 body{margin:0;background:var(--bg);color:#1e293b;}
 header{background:var(--navy);color:#fff;padding:14px 16px;position:sticky;
        top:0;z-index:10;}
 header h1{margin:0;font-size:18px;} header p{margin:2px 0 0;font-size:12px;
        color:#aab4d4;}
 .search{width:100%;padding:12px;border:0;font-size:16px;}
 .wrap{padding:10px;max-width:680px;margin:0 auto;}
 .card{background:var(--card);border-radius:12px;padding:12px;margin:10px 0;
       box-shadow:0 1px 4px rgba(0,0,0,.06);}
 .addcard{border:2px dashed var(--accent);}
 .name{font-weight:600;font-size:16px;margin-bottom:6px;}
 .row{display:flex;gap:10px;margin-top:8px;}
 .fld{flex:1;} .fld label{display:block;font-size:12px;color:var(--muted);}
 .fld input,.fld select{width:100%;padding:10px;font-size:16px;
            border:1px solid #cbd5e1;border-radius:8px;background:#fff;}
 .btns{display:flex;gap:8px;margin-top:10px;}
 button{border:0;border-radius:8px;font-size:15px;font-weight:600;padding:12px;}
 .save{flex:3;background:var(--accent);color:#fff;} .save:active{background:#1d4ed8;}
 .del{flex:1;background:#fee2e2;color:var(--danger);}
 .add{width:100%;background:var(--ok);color:#fff;}
 h2{font-size:14px;color:var(--muted);margin:14px 4px 0;}
 .toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);
        background:var(--ok);color:#fff;padding:10px 18px;border-radius:20px;
        font-size:14px;opacity:0;transition:.3s;pointer-events:none;z-index:20;}
 .toast.show{opacity:1;}
</style></head><body>
<header><h1>🥬 {{store}}</h1><p>Manage products — changes appear in the shop
 software automatically</p></header>
<input class="search" id="q" placeholder="🔍 Search product…" oninput="filter()">
<datalist id="cats">{% for c in cats %}<option value="{{c}}">{% endfor %}</datalist>
<div class="wrap">

 <h2>➕ ADD NEW PRODUCT</h2>
 <div class="card addcard">
   <div class="fld"><label>Name</label><input id="n_name" placeholder="e.g. Spinach"></div>
   <div class="row">
     <div class="fld"><label>Price ({{cur}})</label><input id="n_price" type="number" step="0.01" value="0"></div>
     <div class="fld"><label>Stock</label><input id="n_stock" type="number" step="0.001" value="0"></div>
   </div>
   <div class="row">
     <div class="fld"><label>Unit</label><select id="n_unit">
       {% for u in units %}<option value="{{u}}">{{u}}</option>{% endfor %}</select></div>
     <div class="fld"><label>Category</label><input id="n_cat" list="cats" placeholder="type or pick"></div>
   </div>
   <div class="fld"><label>Emoji (optional, auto if blank)</label><input id="n_emoji" placeholder="🥬"></div>
   <div class="btns"><button class="add" onclick="addP()">＋ Add product</button></div>
 </div>

 <h2>📦 EXISTING PRODUCTS</h2>
 <div id="list">
 {% for p in products %}
 <div class="card" data-name="{{p['name']|lower}}">
   <div class="name">{{p['emoji'] or ''}} {{p['name']}}</div>
   <div class="fld"><label>Name</label><input id="name{{p['id']}}" value="{{p['name']}}"></div>
   <div class="row">
     <div class="fld"><label>Price ({{cur}})</label>
       <input type="number" step="0.01" id="price{{p['id']}}" value="{{'%.2f'|format(p['price'])}}"></div>
     <div class="fld"><label>Stock</label>
       <input type="number" step="0.001" id="stock{{p['id']}}" value="{{p['stock']|round(3)}}"></div>
   </div>
   <div class="row">
     <div class="fld"><label>Unit</label><select id="unit{{p['id']}}">
       {% for u in units %}<option value="{{u}}" {{'selected' if u==p['unit'] else ''}}>{{u}}</option>{% endfor %}</select></div>
     <div class="fld"><label>Category</label>
       <input id="cat{{p['id']}}" list="cats" value="{{p['category']}}"></div>
   </div>
   <div class="fld"><label>Emoji</label><input id="emoji{{p['id']}}" value="{{p['emoji'] or ''}}"></div>
   <div class="btns">
     <button class="save" onclick="save({{p['id']}})">Save</button>
     <button class="del" onclick="del({{p['id']}},'{{p['name']}}')">🗑</button>
   </div>
 </div>
 {% endfor %}
 </div>
</div>
<div class="toast" id="toast"></div>
<script>
function v(id){return document.getElementById(id).value;}
function filter(){var q=document.getElementById('q').value.toLowerCase();
 document.querySelectorAll('#list .card').forEach(function(c){
  c.style.display=c.dataset.name.indexOf(q)>-1?'':'none';});}
function toast(m,ok){var t=document.getElementById('toast');t.textContent=m;
 t.style.background=ok?'#16a34a':'#dc2626';t.className='toast show';
 setTimeout(function(){t.className='toast';},1600);}
function post(url,body,after){
 fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify(body)}).then(function(r){return r.json();})
 .then(function(d){toast(d.ok?'Saved ✓':'Error: '+d.error,d.ok);
  if(d.ok&&after)setTimeout(after,600);})
 .catch(function(){toast('Network error',false);});}
function save(id){post('update',{id:id,name:v('name'+id),price:v('price'+id),
 stock:v('stock'+id),unit:v('unit'+id),category:v('cat'+id),emoji:v('emoji'+id)});}
function del(id,nm){if(confirm('Delete '+nm+'?'))
 post('delete',{id:id},function(){location.reload();});}
function addP(){post('add',{name:v('n_name'),price:v('n_price'),stock:v('n_stock'),
 unit:v('n_unit'),category:v('n_cat'),emoji:v('n_emoji')},
 function(){location.reload();});}
</script></body></html>"""

    @app.before_request
    def _require_pin():
        auth = request.authorization
        if not auth or auth.password != _PIN:
            return Response(
                "Login required", 401,
                {"WWW-Authenticate": 'Basic realm="Shop POS"'})

    @app.get("/")
    def index():
        con = _open()
        rows = con.execute(
            "SELECT id, name, price, unit, category, emoji, stock "
            "FROM products ORDER BY category, name").fetchall()
        cats = _categories(con)
        con.close()
        return render_template_string(
            _PAGE, products=rows, cats=cats, units=_UNITS,
            store=config.STORE_NAME, cur=config.CURRENCY)

    def _read_fields(data, require_name):
        name = str(data.get("name", "")).strip()
        if require_name and not name:
            raise ValueError("name is required")
        price = float(data["price"])
        stock = float(data["stock"])
        if price < 0 or stock < 0:
            raise ValueError("negative value")
        unit = str(data.get("unit") or "kg").strip()
        category = str(data.get("category") or "").strip()
        emoji = str(data.get("emoji") or "").strip() or None
        return name, price, stock, unit, category, emoji

    @app.post("/update")
    def update():
        data = request.get_json(silent=True) or {}
        try:
            pid = int(data["id"])
            name, price, stock, unit, cat, emoji = _read_fields(data, True)
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify(ok=False, error=str(exc)), 400
        con = _open()
        _ensure_category(con, cat)
        con.execute(
            "UPDATE products SET name=?, price=?, stock=?, unit=?, "
            "category=?, emoji=? WHERE id=?",
            (name, price, stock, unit, cat or "Uncategorized",
             emoji, pid))
        con.commit()
        con.close()
        STATE["version"] += 1
        return jsonify(ok=True)

    @app.post("/add")
    def add():
        data = request.get_json(silent=True) or {}
        try:
            name, price, stock, unit, cat, emoji = _read_fields(data, True)
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify(ok=False, error=str(exc)), 400
        if not emoji:
            emoji = _guess_emoji(name)
        cat = cat or "Uncategorized"
        con = _open()
        _ensure_category(con, cat)
        con.execute(
            "INSERT INTO products (name, price, unit, category, image, "
            "emoji, stock) VALUES (?, ?, ?, ?, NULL, ?, ?)",
            (name, price, unit, cat, emoji, stock))
        con.commit()
        con.close()
        STATE["version"] += 1
        return jsonify(ok=True)

    @app.post("/delete")
    def delete():
        data = request.get_json(silent=True) or {}
        try:
            pid = int(data["id"])
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify(ok=False, error=str(exc)), 400
        con = _open()
        con.execute("DELETE FROM products WHERE id=?", (pid,))
        con.commit()
        con.close()
        STATE["version"] += 1
        return jsonify(ok=True)


# --------------------------------------------------------------------------
# Lifecycle
# --------------------------------------------------------------------------
def start(db_path=None, port=None, pin=None):
    """Start the server in a daemon thread. Returns (url, ok)."""
    global _DB_PATH, _PIN, _started
    if not _FLASK_OK:
        return "", False
    if _started:
        return STATE["url"], True
    _DB_PATH = db_path or config.DB_PATH
    _PIN = str(pin if pin is not None else config.MOBILE_PIN)
    port = int(port or config.MOBILE_PORT)

    # quieten Flask/werkzeug console output
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    def run():
        try:
            app.run(host="0.0.0.0", port=port, threaded=True,
                    use_reloader=False, debug=False)
        except Exception:
            STATE["running"] = False

    threading.Thread(target=run, daemon=True, name="mobile-web").start()
    _started = True
    STATE["running"] = True
    STATE["url"] = f"http://{get_lan_ip()}:{port}/"
    return STATE["url"], True
