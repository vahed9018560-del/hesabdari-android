from flask import Flask, request, redirect, url_for, session, render_template_string, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path
from functools import wraps
from datetime import date
import sqlite3
import os
import secrets

BASE = Path(__file__).resolve().parent
DB = Path(os.environ.get("HESABDARI_DB", str(BASE / "hesabdari.db")))

app = Flask(__name__)
app.secret_key = os.environ.get("HESABDARI_SECRET") or secrets.token_hex(32)


def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY,
          username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS customers(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          phone TEXT DEFAULT '',
          address TEXT DEFAULT '',
          notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS suppliers(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          phone TEXT DEFAULT '',
          address TEXT DEFAULT '',
          notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          code TEXT DEFAULT '',
          unit TEXT DEFAULT 'عدد',
          purchase_price INTEGER NOT NULL DEFAULT 0,
          sale_price INTEGER NOT NULL DEFAULT 0,
          stock REAL NOT NULL DEFAULT 0,
          notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS invoices(
          id INTEGER PRIMARY KEY,
          invoice_type TEXT NOT NULL,
          party_type TEXT NOT NULL,
          party_id INTEGER,
          invoice_date TEXT NOT NULL,
          total INTEGER NOT NULL DEFAULT 0,
          discount INTEGER NOT NULL DEFAULT 0,
          paid INTEGER NOT NULL DEFAULT 0,
          notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS invoice_items(
          id INTEGER PRIMARY KEY,
          invoice_id INTEGER NOT NULL REFERENCES invoices(id),
          product_id INTEGER NOT NULL REFERENCES products(id),
          quantity REAL NOT NULL,
          unit_price INTEGER NOT NULL,
          discount INTEGER NOT NULL DEFAULT 0,
          line_total INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transactions(
          id INTEGER PRIMARY KEY,
          party_type TEXT NOT NULL,
          party_id INTEGER NOT NULL,
          transaction_type TEXT NOT NULL,
          amount INTEGER NOT NULL,
          transaction_date TEXT NOT NULL,
          description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS expenses(
          id INTEGER PRIMARY KEY,
          title TEXT NOT NULL,
          amount INTEGER NOT NULL,
          expense_date TEXT NOT NULL,
          notes TEXT DEFAULT ''
        );
        """)


        # سازگاری با دیتابیس‌های قدیمی
        for table, old_col, new_col in (
            ("invoices", "kind", "invoice_type"),
            ("transactions", "kind", "transaction_type"),
        ):
            cols = [row[1] for row in c.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()]
            if old_col in cols and new_col not in cols:
                c.execute(
                    f"ALTER TABLE {table} RENAME COLUMN {old_col} TO {new_col}"
                )

        if not c.execute("SELECT id FROM users LIMIT 1").fetchone():
            c.execute(
                "INSERT INTO users(username,password_hash) VALUES(?,?)",
                ("admin", generate_password_hash("ChangeMe123!"))
            )


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


def money(v):
    try:
        return f"{int(v or 0):,}"
    except (ValueError, TypeError):
        return "0"


app.jinja_env.filters["money"] = money

STYLE = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#f2f5fa;color:#243247;font-family:Tahoma,Arial,sans-serif}
header{background:#173b67;color:white;padding:18px}
header h1{margin:0 0 8px;font-size:23px}
nav{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
nav a{color:white;text-decoration:none;background:#ffffff20;padding:9px 12px;border-radius:8px}
main{max-width:1100px;margin:20px auto;padding:0 12px}
.card{background:white;border-radius:13px;padding:16px;margin-bottom:14px;box-shadow:0 2px 10px #152b4510}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat{font-size:25px;font-weight:bold;color:#173b67;margin-top:10px}
input,select,textarea{width:100%;padding:11px;margin:5px 0 12px;border:1px solid #ccd5e1;border-radius:8px;font:inherit}
button,.btn{display:inline-block;border:0;border-radius:8px;padding:10px 14px;background:#1769aa;color:white;text-decoration:none;font:inherit;cursor:pointer}
.danger{background:#b93232}
table{width:100%;border-collapse:collapse;background:white}
th,td{text-align:right;padding:10px;border-bottom:1px solid #e3e8ef}
th{background:#eaf0f7}
.tablewrap{overflow-x:auto}
label{font-size:14px}
.notice{padding:12px;border-radius:8px;background:#e7f6eb;margin:10px 0}
.error{background:#ffe9e9}
small{color:#65758b}
footer{text-align:center;padding:20px;color:#7b8797}
</style>
"""

PAGE = """
<!doctype html><html lang="fa" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} - تُندر</title>
""" + STYLE + """

<style id="tonder-brand-css">
:root{--tg:#063f35;--tg2:#0b6652;--gold:#d9b45b}
body{font-family:Tahoma,Arial,sans-serif!important}
header{background:linear-gradient(120deg,var(--tg),var(--tg2))!important;color:#fff!important;border-bottom:3px solid var(--gold)}
header h1{color:#f5d88a!important}
a,button,input[type=submit]{accent-color:var(--tg2)}
button,input[type=submit]{border-radius:9px}
.tonder-symbol{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border:1px solid #d9b45b;border-radius:10px;color:#d9b45b;font-weight:900;font-size:23px;margin-left:8px}
#tonder-splash{position:fixed;inset:0;z-index:999999;background:radial-gradient(circle at top,#12634f,#063f35 60%,#032a24);color:white;display:flex;align-items:center;justify-content:center;text-align:center;padding:20px;box-sizing:border-box;transition:opacity .7s ease}
#tonder-splash.hide{opacity:0;pointer-events:none}
.ts-box{max-width:360px;animation:tsrise .8s ease}
.ts-logo{width:100px;height:100px;margin:auto;border:2px solid #d9b45b;border-radius:28px;display:flex;align-items:center;justify-content:center;color:#f5d88a;font-size:65px;font-weight:900;background:#0b6652;box-shadow:0 0 0 9px #ffffff0a}
.ts-box h2{font-size:36px;color:#f5d88a;margin:17px 0 3px}
.ts-en{letter-spacing:4px;font-size:12px;color:#d9b45b}
.ts-desc{line-height:2;font-size:14px;margin-top:22px;color:#e5eee9}
.ts-maker{line-height:2;margin-top:18px;color:#f5d88a;font-size:13px}
.ts-email{direction:ltr;font-size:12px;color:#e5eee9;margin-top:4px}
.ts-line{height:2px;width:140px;background:#d9b45b;margin:20px auto;animation:tsline 1.3s infinite alternate}
@keyframes tsrise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@keyframes tsline{from{opacity:.3;transform:scaleX(.5)}to{opacity:1;transform:scaleX(1)}}
</style>
</head><body>
<div id="tonder-splash">
 <div class="ts-box">
  <div class="ts-logo">T</div>
  <h2>تُندر</h2><div class="ts-en">TONDER STUDIO</div>
  <div class="ts-line"></div>
  <div class="ts-desc">دفتر حسابداری فروشگاه شما<br>مشتریان • خرید و فروش • بدهی‌ها • گزارش‌ها</div>
  <div class="ts-maker">طراحی و توسعه: عبدالواحد جهانگیری<br>استودیوی تُندر</div>
  <div class="ts-email">vahed9018560@gmail.com</div>
 </div>
</div>
<script>
(function(){
 var s=document.getElementById('tonder-splash');
 if(!s)return;
 setTimeout(function(){s.classList.add('hide');setTimeout(function(){s.remove()},750)},3500);
})();
</script>

<header><h1><span class="tonder-symbol">T</span> تُندر</h1>
<div>مدیریت فروشگاه، مشتریان و حساب‌ها</div>
{% if session.get('user_id') %}
<nav>
<a href="{{url_for('home')}}">🏠 خانه</a>
<a href="{{url_for('people',kind='customers')}}">👥 مشتریان</a>
<a href="{{url_for('people',kind='suppliers')}}">🏭 فروشندگان</a>
<a href="{{url_for('products')}}">📦 کالاها</a>
<a href="{{url_for('new_invoice',kind='sale')}}">🧾 فروش</a>
<a href="{{url_for('new_invoice',kind='purchase')}}">🛒 خرید</a>
<a href="{{url_for('invoices')}}">📚 فاکتورها</a>
<a href="{{url_for('transactions')}}">💰 دریافت و پرداخت</a>
<a href="{{url_for('expenses')}}">💸 هزینه‌ها</a>
<a href="{{url_for('reports')}}">📊 گزارش‌ها</a>
<a href="{{url_for('change_password')}}">🔐 رمز عبور</a>
<a href="{{url_for('logout')}}">خروج</a>
</nav>{% endif %}</header>
<main>
{% with messages=get_flashed_messages() %}{% for m in messages %}
<div class="notice">{{m}}</div>{% endfor %}{% endwith %}
{{body|safe}}
</main><footer>تُندر | تُندر | اطلاعات در پایگاه داده محلی ذخیره می‌شود</footer>
</body></html>
"""


def page(title, body, **kwargs):
    rendered_body = render_template_string(body, **kwargs)
    return render_template_string(PAGE, title=title, body=rendered_body)


def val_int(name, default=0):
    try:
        return int(float(request.form.get(name, default) or default))
    except (ValueError, TypeError):
        return default


def val_float(name, default=0):
    try:
        return float(request.form.get(name, default) or default)
    except (ValueError, TypeError):
        return default


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        with connect() as c:
            u = c.execute("SELECT * FROM users WHERE username=?",
                          (request.form.get("username", ""),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = u["id"]
            session["username"] = u["username"]
            return redirect(url_for("home"))
        flash("نام کاربری یا رمز عبور اشتباه است.")
    body = """
    <div class="card"><h2>ورود به حسابداری</h2>
    <form method="post"><label>نام کاربری</label><input name="username" required>
    <label>رمز عبور</label><input name="password" type="password" required>
    <button>ورود</button></form>
    <p><small>ورود اولیه: admin / ChangeMe123!</small></p>
    <p class="error">پس از ورود، حتماً رمز اولیه را تغییر بده.</p></div>
    """
    return page("ورود", body)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old = request.form.get("old", "")
        new = request.form.get("new", "")
        if len(new) < 8:
            flash("رمز جدید باید حداقل ۸ نویسه باشد.")
        else:
            with connect() as c:
                u = c.execute("SELECT * FROM users WHERE id=?",
                              (session["user_id"],)).fetchone()
                if u and check_password_hash(u["password_hash"], old):
                    c.execute("UPDATE users SET password_hash=? WHERE id=?",
                              (generate_password_hash(new), u["id"]))
                    flash("رمز عبور تغییر کرد.")
                    return redirect(url_for("home"))
                flash("رمز فعلی اشتباه است.")
    body = """
    <div class="card"><h2>تغییر رمز عبور</h2><form method="post">
    <label>رمز فعلی</label><input name="old" type="password" required>
    <label>رمز جدید (حداقل ۸ نویسه)</label><input name="new" type="password" minlength="8" required>
    <button>ذخیره رمز جدید</button></form></div>
    """
    return page("تغییر رمز", body)


@app.route("/")
@login_required
def home():
    with connect() as c:
        stats = {
            "customers": c.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            "suppliers": c.execute("SELECT COUNT(*) FROM suppliers").fetchone()[0],
            "products": c.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "sales": c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE invoice_type='sale'").fetchone()[0],
            "purchases": c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE invoice_type='purchase'").fetchone()[0],
            "expenses": c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0],
            "receipts": c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE transaction_type='receipt'").fetchone()[0],
            "payments": c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE transaction_type='payment'").fetchone()[0],
        }
        low = c.execute("SELECT name,stock,unit FROM products WHERE stock<=2 ORDER BY stock").fetchall()
    body = """
    <div class="notice">برنامه آماده است. برای شروع، کالاها و مشتریان یا فروشندگان را ثبت کن.</div>
    <div class="grid">
    {% for label,key in [('مشتریان','customers'),('فروشندگان','suppliers'),('کالاها','products')] %}
    <div class="card"><h3>{{label}}</h3><div class="stat">{{s[key]}}</div></div>{% endfor %}
    <div class="card"><h3>کل فروش</h3><div class="stat">{{s.sales|money}}</div></div>
    <div class="card"><h3>کل خرید</h3><div class="stat">{{s.purchases|money}}</div></div>
    <div class="card"><h3>هزینه‌ها</h3><div class="stat">{{s.expenses|money}}</div></div>
    <div class="card"><h3>دریافت‌ها</h3><div class="stat">{{s.receipts|money}}</div></div>
    <div class="card"><h3>پرداخت‌ها</h3><div class="stat">{{s.payments|money}}</div></div>
    </div>
    <div class="card"><h3>⚠️ کالاهای کم‌موجود</h3>
    {% if low %}<ul>{% for p in low %}<li>{{p.name}} — {{p.stock}} {{p.unit}}</li>{% endfor %}</ul>
    {% else %}کالای کم‌موجودی ثبت نشده است.{% endif %}</div>
    <div class="card"><b>راهنما:</b> قیمت‌ها را به تومان وارد کن. بعد از ثبت فاکتور، موجودی و مانده حساب محاسبه می‌شود.</div>
    """
    return page("خانه", body, s=stats, low=low)


@app.route("/people/<kind>", methods=["GET", "POST"])
@login_required
def people(kind):
    if kind not in ("customers", "suppliers"):
        return redirect(url_for("home"))
    label = "مشتری" if kind == "customers" else "فروشنده"
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("نام را وارد کن.")
        else:
            with connect() as c:
                c.execute(f"INSERT INTO {kind}(name,phone,address,notes) VALUES(?,?,?,?)",
                          (name, request.form.get("phone", "").strip(),
                           request.form.get("address", "").strip(),
                           request.form.get("notes", "").strip()))
            flash(f"{label} ثبت شد.")
        return redirect(url_for("people", kind=kind))
    with connect() as c:
        rows = c.execute(f"SELECT * FROM {kind} ORDER BY id DESC").fetchall()
    body = """
    <div class="card"><h2>ثبت {{label}} جدید</h2>
    <form method="post"><label>نام کامل</label><input name="name" required>
    <label>شماره تماس</label><input name="phone">
    <label>آدرس</label><input name="address">
    <label>توضیحات</label><textarea name="notes"></textarea><button>ثبت {{label}}</button></form></div>
    <div class="card"><h2>فهرست {{label}}ها</h2><div class="tablewrap"><table>
    <tr><th>نام</th><th>تلفن</th><th>آدرس</th><th>عملیات</th></tr>
    {% for r in rows %}<tr><td>{{r.name}}</td><td>{{r.phone}}</td><td>{{r.address}}</td>
    <td><a href="{{url_for('person_detail',kind=kind,pid=r.id)}}">پرونده</a></td></tr>{% endfor %}
    </table></div></div>
    """
    return page(label, body, label=label, rows=rows, kind=kind)


@app.route("/people/<kind>/<int:pid>")
@login_required
def person_detail(kind, pid):
    if kind not in ("customers", "suppliers"):
        return redirect(url_for("home"))
    with connect() as c:
        person = c.execute(f"SELECT * FROM {kind} WHERE id=?", (pid,)).fetchone()
        if not person:
            flash("مورد پیدا نشد.")
            return redirect(url_for("people", kind=kind))
        party_type = "customer" if kind == "customers" else "supplier"
        invkind = "sale" if kind == "customers" else "purchase"
        invs = c.execute("""SELECT * FROM invoices WHERE party_type=? AND party_id=?
                            ORDER BY id DESC""", (party_type, pid)).fetchall()
        txs = c.execute("""SELECT * FROM transactions WHERE party_type=? AND party_id=?
                           ORDER BY id DESC""", (party_type, pid)).fetchall()
        total = sum(x["total"] for x in invs)
        paid = sum(x["paid"] for x in invs)
        receipts = sum(x["amount"] for x in txs if x["transaction_type"] == "receipt")
        payments = sum(x["amount"] for x in txs if x["transaction_type"] == "payment")
    balance = total - paid - receipts + payments if party_type == "customer" else total - paid - payments + receipts
    body = """
    <div class="card"><h2>{{p.name}}</h2><p>تلفن: {{p.phone}} | آدرس: {{p.address}}</p>
    <p>توضیحات: {{p.notes}}</p><p>جمع فاکتورها: {{total|money}} تومان</p>
    <p>پرداخت هنگام فاکتور: {{paid|money}} تومان</p>
    <p>مانده تقریبی حساب: {{balance|money}} تومان</p></div>
    <div class="card"><h3>فاکتورها</h3><table><tr><th>شماره</th><th>نوع</th><th>تاریخ</th><th>مبلغ</th><th></th></tr>
    {% for i in invs %}<tr><td>{{i.id}}</td><td>{{'فروش' if i.invoice_type=='sale' else 'خرید'}}</td>
    <td>{{i.invoice_date}}</td><td>{{i.total|money}}</td><td><a href="{{url_for('invoice_detail',iid=i.id)}}">مشاهده</a></td></tr>{% endfor %}
    </table></div>
    """
    return page("پرونده", body, p=person, invs=invs, total=total, paid=paid, balance=balance)


@app.route("/products", methods=["GET", "POST"])
@login_required
def products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("نام کالا الزامی است.")
        else:
            with connect() as c:
                c.execute("""INSERT INTO products(name,unit,purchase_price,sale_price,stock)
                    VALUES(?,?,?,?,?)""",
                    (name, request.form.get("unit", "عدد").strip() or "عدد",
                     max(0, val_int("purchase_price")), max(0, val_int("sale_price")),
                     val_float("stock")))
            flash("کالا ثبت شد.")
        return redirect(url_for("products"))
    with connect() as c:
        rows = c.execute("SELECT * FROM products ORDER BY id DESC").fetchall()
    body = """
    <div class="card"><h2>ثبت کالا</h2><form method="post">
    <label>نام کالا</label><input name="name" required>
    <label>کد کالا</label><input name="code">
    <label>واحد (عدد، کیلو، جین و...)</label><input name="unit" value="عدد">
    <label>قیمت خرید (تومان)</label><input name="purchase_price" type="number" min="0" value="0">
    <label>قیمت فروش (تومان)</label><input name="sale_price" type="number" min="0" value="0">
    <label>موجودی اولیه</label><input name="stock" type="number" step="0.01" value="0">
    <label>توضیحات</label><textarea name="notes"></textarea><button>ثبت کالا</button></form></div>
    <div class="card"><h2>موجودی کالاها</h2><div class="tablewrap"><table>
    <tr><th>نام</th><th>واحد</th><th>خرید</th><th>فروش</th><th>موجودی</th></tr>
    {% for p in rows %}<tr><td>{{p.name}}</td><td>{{p.unit}}</td>
    <td>{{p.purchase_price|money}}</td><td>{{p.sale_price|money}}</td><td>{{p.stock}}</td></tr>{% endfor %}
    </table></div></div>
    """
    return page("کالاها", body, rows=rows)


@app.route("/invoice/new/<kind>", methods=["GET", "POST"])
@login_required
def new_invoice(kind):
    if kind not in ("sale", "purchase"):
        return redirect(url_for("home"))
    is_sale = kind == "sale"
    people_table = "customers" if is_sale else "suppliers"
    party_type = "customer" if is_sale else "supplier"
    label = "فروش" if is_sale else "خرید"
    with connect() as c:
        people_rows = c.execute(f"SELECT id,name FROM {people_table} ORDER BY name").fetchall()
        products_rows = c.execute("SELECT * FROM products ORDER BY name").fetchall()
    if request.method == "POST":
        pid = val_int("party_id", -1)
        pids = request.form.getlist("product_id")
        qtys = request.form.getlist("quantity")
        prices = request.form.getlist("unit_price")
        discounts = request.form.getlist("item_discount")
        if pid < 1 or not pids:
            flash("شخص و دست‌کم یک کالا را انتخاب کن.")
            return redirect(url_for("new_invoice", kind=kind))
        items = []
        subtotal = 0
        try:
            for i, product_id in enumerate(pids):
                if not product_id:
                    continue
                q = float(qtys[i])
                price = int(float(prices[i]))
                disc = int(float(discounts[i] or 0))
                if q <= 0 or price < 0 or disc < 0:
                    raise ValueError()
                line = max(0, round(q * price) - disc)
                items.append((int(product_id), q, price, disc, line))
                subtotal += line
        except (ValueError, IndexError):
            flash("تعداد، قیمت یا تخفیف نامعتبر است.")
            return redirect(url_for("new_invoice", kind=kind))
        discount = max(0, val_int("discount"))
        paid = max(0, val_int("paid"))
        total = max(0, subtotal - discount)
        if paid > total:
            flash("مبلغ پرداختی نمی‌تواند از مبلغ فاکتور بیشتر باشد.")
            return redirect(url_for("new_invoice", kind=kind))
        with connect() as c:
            for product_id, q, price, disc, line in items:
                product = c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
                if not product:
                    flash("کالا پیدا نشد.")
                    return redirect(url_for("new_invoice", kind=kind))
                if is_sale and product["stock"] < q:
                    flash("موجودی کافی نیست: " + product["name"])
                    return redirect(url_for("new_invoice", kind=kind))
            cur = c.execute("""INSERT INTO invoices(invoice_type,party_type,party_id,invoice_date,total,discount,paid,notes)
                VALUES(?,?,?,?,?,?,?,?)""",
                (kind, party_type, pid, request.form.get("invoice_date") or date.today().isoformat(),
                 total, discount, paid, request.form.get("notes", "").strip()))
            iid = cur.lastrowid
            for product_id, q, price, disc, line in items:
                c.execute("""INSERT INTO invoice_items(invoice_id,product_id,quantity,unit_price,discount,line_total)
                             VALUES(?,?,?,?,?,?)""", (iid, product_id, q, price, disc, line))
                if is_sale:
                    c.execute("UPDATE products SET stock=stock-? WHERE id=?", (q, product_id))
                else:
                    c.execute("UPDATE products SET stock=stock+? WHERE id=?", (q, product_id))
            if paid:
                c.execute("""INSERT INTO transactions(party_type,party_id,transaction_type,amount,transaction_date,description)
                    VALUES(?,?,?,?,?,?)""",
                    (party_type, pid, "receipt" if is_sale else "payment", paid,
                     request.form.get("invoice_date") or date.today().isoformat(),
                     f"پرداخت فاکتور شماره {iid}"))
        flash(f"فاکتور {label} شماره {iid} ثبت شد.")
        return redirect(url_for("invoice_detail", iid=iid))
    body = """
    <div class="card"><h2>ثبت فاکتور {{label}}</h2>
    {% if not people_rows or not products_rows %}
    <p class="error">ابتدا دست‌کم یک {{'مشتری' if is_sale else 'فروشنده'}} و یک کالا ثبت کن.</p>
    {% endif %}
    <form method="post">
    <label>{{'مشتری' if is_sale else 'فروشنده'}}</label>
    <select name="party_id" required><option value="">انتخاب کن</option>
    {% for p in people_rows %}<option value="{{p.id}}">{{p.name}}</option>{% endfor %}</select>
    <label>تاریخ فاکتور</label><input name="invoice_date" type="date" value="{{today}}" required>
    <h3>اقلام فاکتور</h3>
    {% for n in range(5) %}
    <div class="card"><label>کالا</label><select name="product_id">
    <option value="">بدون کالا</option>{% for p in products_rows %}
    <option value="{{p.id}}">{{p.name}} (موجودی: {{p.stock}} {{p.unit}})</option>{% endfor %}</select>
    <label>تعداد</label><input name="quantity" type="number" min="0.01" step="0.01" value="{{1 if n==0 else 0}}">
    <label>قیمت واحد (تومان)</label><input name="unit_price" type="number" min="0" value="0">
    <label>تخفیف این ردیف (تومان)</label><input name="item_discount" type="number" min="0" value="0"></div>
    {% endfor %}
    <label>تخفیف کل فاکتور (تومان)</label><input name="discount" type="number" min="0" value="0">
    <label>مبلغ پرداخت‌شده هنگام ثبت (تومان)</label><input name="paid" type="number" min="0" value="0">
    <label>توضیحات</label><textarea name="notes"></textarea><button>ثبت فاکتور</button></form>
    <small>مبلغ هر ردیف برابر تعداد × قیمت، منهای تخفیف ردیف است.</small></div>
    """
    return page("فاکتور", body, label=label, people_rows=people_rows,
                products_rows=products_rows, is_sale=is_sale, today=date.today().isoformat())


@app.route("/invoices")
@login_required
def invoices():
    with connect() as c:
        rows = c.execute("""SELECT i.*, 
          CASE WHEN i.party_type='customer' THEN (SELECT name FROM customers WHERE id=i.party_id)
               ELSE (SELECT name FROM suppliers WHERE id=i.party_id) END AS party_name
          FROM invoices i ORDER BY i.id DESC""").fetchall()
    body = """
    <div class="card"><h2>فاکتورها</h2><div class="tablewrap"><table>
    <tr><th>شماره</th><th>نوع</th><th>طرف حساب</th><th>تاریخ</th><th>مبلغ</th><th>پرداخت</th><th>مانده</th><th></th></tr>
    {% for i in rows %}<tr><td>{{i.id}}</td><td>{{'فروش' if i.invoice_type=='sale' else 'خرید'}}</td>
    <td>{{i.party_name or 'حذف‌شده'}}</td><td>{{i.invoice_date}}</td><td>{{i.total|money}}</td>
    <td>{{i.paid|money}}</td><td>{{(i.total-i.paid)|money}}</td>
    <td><a href="{{url_for('invoice_detail',iid=i.id)}}">جزئیات</a></td></tr>{% endfor %}
    </table></div></div>
    """
    return page("فاکتورها", body, rows=rows)


@app.route("/invoice/<int:iid>")
@login_required
def invoice_detail(iid):
    with connect() as c:
        inv = c.execute("SELECT * FROM invoices WHERE id=?", (iid,)).fetchone()
        if not inv:
            flash("فاکتور پیدا نشد.")
            return redirect(url_for("invoices"))
        party_table = "customers" if inv["party_type"] == "customer" else "suppliers"
        party = c.execute(f"SELECT name FROM {party_table} WHERE id=?", (inv["party_id"],)).fetchone()
        items = c.execute("""SELECT ii.*,p.name,p.unit FROM invoice_items ii
                             JOIN products p ON p.id=ii.product_id WHERE ii.invoice_id=?""", (iid,)).fetchall()
    body = """
    <div class="card"><h2>فاکتور شماره {{i.id}}</h2>
    <p>نوع: {{'فروش' if i.invoice_type=='sale' else 'خرید'}} | طرف حساب: {{party.name if party else '—'}}</p>
    <p>تاریخ: {{i.invoice_date}} | توضیحات: {{i.notes}}</p>
    <div class="tablewrap"><table><tr><th>کالا</th><th>تعداد</th><th>قیمت واحد</th><th>تخفیف</th><th>مبلغ</th></tr>
    {% for x in items %}<tr><td>{{x.name}}</td><td>{{x.quantity}} {{x.unit}}</td>
    <td>{{x.unit_price|money}}</td><td>{{x.discount|money}}</td><td>{{x.line_total|money}}</td></tr>{% endfor %}
    </table></div>
    <h3>مبلغ نهایی: {{i.total|money}} تومان</h3>
    <p>پرداخت‌شده: {{i.paid|money}} تومان</p>
    <p>مانده فاکتور: {{(i.total-i.paid)|money}} تومان</p>
    <button onclick="window.print()">چاپ فاکتور</button>
    <a class="btn" href="{{url_for('invoices')}}">بازگشت</a></div>
    """
    return page("جزئیات فاکتور", body, i=inv, party=party, items=items)


@app.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    if request.method == "POST":
        party_type = request.form.get("party_type")
        kind = request.form.get("kind")
        pid = val_int("party_id", -1)
        amount = val_int("amount", -1)
        if party_type not in ("customer", "supplier") or kind not in ("receipt", "payment") or pid < 1 or amount <= 0:
            flash("اطلاعات تراکنش معتبر نیست.")
            return redirect(url_for("transactions"))
        with connect() as c:
            table = "customers" if party_type == "customer" else "suppliers"
            if not c.execute(f"SELECT id FROM {table} WHERE id=?", (pid,)).fetchone():
                flash("طرف حساب پیدا نشد.")
                return redirect(url_for("transactions"))
            c.execute("""INSERT INTO transactions(party_type,party_id,transaction_type,amount,transaction_date,description)
                         VALUES(?,?,?,?,?,?)""",
                (party_type, pid, kind, amount, request.form.get("transaction_date") or date.today().isoformat(),
                 request.form.get("description", "").strip()))
        flash("تراکنش ثبت شد.")
        return redirect(url_for("transactions"))
    with connect() as c:
        customers = c.execute("SELECT id,name FROM customers ORDER BY name").fetchall()
        suppliers = c.execute("SELECT id,name FROM suppliers ORDER BY name").fetchall()
        rows = c.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 100").fetchall()
    body = """
    <div class="card"><h2>ثبت دریافت یا پرداخت</h2>
    <form method="post"><label>نوع طرف حساب</label><select name="party_type" id="ptype" onchange="changeParty()" required>
    <option value="customer">مشتری</option><option value="supplier">فروشنده</option></select>
    <label>طرف حساب</label><select name="party_id" id="party" required>
    {% for p in customers %}<option data-type="customer" value="{{p.id}}">{{p.name}}</option>{% endfor %}
    {% for p in suppliers %}<option data-type="supplier" value="{{p.id}}">{{p.name}}</option>{% endfor %}
    </select>
    <label>نوع عملیات</label><select name="kind"><option value="receipt">دریافت وجه</option><option value="payment">پرداخت وجه</option></select>
    <label>مبلغ (تومان)</label><input name="amount" type="number" min="1" required>
    <label>تاریخ</label><input name="transaction_date" type="date" value="{{today}}">
    <label>توضیحات</label><input name="description"><button>ثبت</button></form></div>
    <div class="card"><h2>آخرین تراکنش‌ها</h2><table><tr><th>طرف حساب</th><th>نوع</th><th>مبلغ</th><th>تاریخ</th><th>توضیح</th></tr>
    {% for t in rows %}<tr><td>{{t.party_type}} #{{t.party_id}}</td>
    <td>{{'دریافت' if t.transaction_type=='receipt' else 'پرداخت'}}</td><td>{{t.amount|money}}</td><td>{{t.transaction_date}}</td><td>{{t.description}}</td></tr>{% endfor %}
    </table></div>
    <script>function changeParty(){let t=document.getElementById('ptype').value;
    let s=document.getElementById('party');let first=null;
    for(let o of s.options){o.hidden=o.dataset.type!==t;if(!o.hidden&&!first)first=o}
    if(first)s.value=first.value;}</script>
    """
    return page("دریافت و پرداخت", body, customers=customers, suppliers=suppliers,
                rows=rows, today=date.today().isoformat())


@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount = val_int("amount", 0)
        if not title or amount <= 0:
            flash("عنوان و مبلغ معتبر وارد کن.")
        else:
            with connect() as c:
                c.execute("INSERT INTO expenses(title,amount,expense_date,notes) VALUES(?,?,?,?)",
                          (title, amount, request.form.get("expense_date") or date.today().isoformat(),
                           request.form.get("notes", "").strip()))
            flash("هزینه ثبت شد.")
        return redirect(url_for("expenses"))
    with connect() as c:
        rows = c.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
        total = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
    body = """
    <div class="card"><h2>ثبت هزینه</h2><form method="post">
    <label>عنوان هزینه</label><input name="title" required>
    <label>مبلغ (تومان)</label><input name="amount" type="number" min="1" required>
    <label>تاریخ</label><input name="expense_date" type="date" value="{{today}}">
    <label>توضیحات</label><textarea name="notes"></textarea><button>ثبت هزینه</button></form></div>
    <div class="card"><h2>هزینه‌ها — مجموع {{total|money}} تومان</h2>
    <table><tr><th>عنوان</th><th>مبلغ</th><th>تاریخ</th><th>توضیح</th></tr>
    {% for x in rows %}<tr><td>{{x.title}}</td><td>{{x.amount|money}}</td><td>{{x.expense_date}}</td><td>{{x.notes}}</td></tr>{% endfor %}
    </table></div>
    """
    return page("هزینه‌ها", body, rows=rows, total=total, today=date.today().isoformat())


@app.route("/reports")
@login_required
def reports():
    with connect() as c:
        sales = c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE invoice_type='sale'").fetchone()[0]
        purchases = c.execute("SELECT COALESCE(SUM(total),0) FROM invoices WHERE invoice_type='purchase'").fetchone()[0]
        expenses_total = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
        stock = c.execute("SELECT * FROM products ORDER BY name").fetchall()
        low = c.execute("SELECT COUNT(*) FROM products WHERE stock<=2").fetchone()[0]
        receipts = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE transaction_type='receipt'").fetchone()[0]
        payments = c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE transaction_type='payment'").fetchone()[0]
    # این رقم سود خالص تخمینی است؛ برای محاسبه دقیق سود باید بهای تمام‌شده هر کالا مشخص باشد.
    estimate = sales - purchases - expenses_total
    body = """
    <div class="grid">
    {% for label,value in [('فروش کل',sales),('خرید کل',purchases),('هزینه‌ها',expenses_total),
       ('دریافت‌ها',receipts),('پرداخت‌ها',payments),('سود/زیان تخمینی',estimate)] %}
    <div class="card"><h3>{{label}}</h3><div class="stat">{{value|money}}</div><small>تومان</small></div>{% endfor %}
    </div>
    <div class="card"><h2>موجودی انبار</h2><p>تعداد کالاهای کم‌موجود: {{low}}</p>
    <table><tr><th>کالا</th><th>واحد</th><th>موجودی</th><th>قیمت خرید</th><th>قیمت فروش</th></tr>
    {% for p in stock %}<tr><td>{{p.name}}</td><td>{{p.unit}}</td><td>{{p.stock}}</td>
    <td>{{p.purchase_price|money}}</td><td>{{p.sale_price|money}}</td></tr>{% endfor %}
    </table><p><small>سود/زیان تخمینی برابر فروش منهای خرید و هزینه‌هاست و لزوماً سود حسابداری دقیق نیست.</small></p></div>
    """
    return page("گزارش‌ها", body, sales=sales, purchases=purchases,
                expenses_total=expenses_total, receipts=receipts, payments=payments,
                estimate=estimate, stock=stock, low=low)


@app.route("/backup")
@login_required
def backup():
    from flask import send_file
    return send_file(DB, as_attachment=True, download_name="hesabdari-backup.db")


@app.route("/health")
def health():
    return {"status": "ok"}


init_db()

if __name__ == "__main__":
    print("برنامه حسابداری آماده اجراست.")
    print("در مرورگر باز کن: http://127.0.0.1:5000")
    print("ورود اولیه: admin")
    print("رمز اولیه: ChangeMe123!  (پس از ورود تغییر بده)")
    app.run(host="127.0.0.1", port=5000, debug=False)

# TONDER_BRAND_V1
