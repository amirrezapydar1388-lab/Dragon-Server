import os
import sqlite3
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "nine_server.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "CHANGE-ME-IN-RENDER")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER", "").lower() == "true"

OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "nineowner")
OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "ChangeThisPassword123!")
OWNER_MINECRAFT = os.environ.get("OWNER_MINECRAFT", "NineOwner")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        minecraft_username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        bio TEXT DEFAULT '',
        avatar TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS shop_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT DEFAULT '',
        price INTEGER NOT NULL DEFAULT 0,
        icon TEXT DEFAULT '🐉',
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        admin_reply TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    conn.commit()

    owner = conn.execute(
        "SELECT id FROM users WHERE username = ?", (OWNER_USERNAME,)
    ).fetchone()

    if not owner:
        cur = conn.execute(
            """INSERT INTO users
               (username, minecraft_username, password_hash, bio)
               VALUES (?, ?, ?, ?)""",
            (
                OWNER_USERNAME,
                OWNER_MINECRAFT,
                generate_password_hash(OWNER_PASSWORD),
                "مدیر اصلی Nine Server"
            )
        )
        owner_id = cur.lastrowid
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (owner_id,))
    else:
        owner_id = owner["id"]
        conn.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (owner_id,))

    count = conn.execute("SELECT COUNT(*) AS c FROM shop_items").fetchone()["c"]
    if count == 0:
        conn.executemany(
            """INSERT INTO shop_items
               (name, category, description, price, icon)
               VALUES (?, ?, ?, ?, ?)""",
            [
                ("Nine VIP", "رنک", "رنک ویژه سرور", 150, "👑"),
                ("Nine MVP", "رنک", "رنک حرفه‌ای با امکانات بیشتر", 300, "🔥"),
                ("کلید Epic", "کلید", "یک کلید ویژه برای جعبه Epic", 75, "🔑"),
                ("کلید Nine", "کلید", "کلید مخصوص جعبه Nine", 120, "🐉"),
            ],
        )
    conn.commit()
    conn.close()


def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def is_admin(user_id):
    if not user_id:
        return False
    return db().execute(
        "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
    ).fetchone() is not None


@app.context_processor
def inject_globals():
    user = current_user()
    return {"current_user": user, "current_is_admin": is_admin(user["id"]) if user else False}


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("ابتدا وارد حساب خود شوید.", "error")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user or not is_admin(user["id"]):
            flash("دسترسی ادمین لازم است.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    items = db().execute(
        "SELECT * FROM shop_items WHERE active = 1 ORDER BY id DESC"
    ).fetchall()
    return render_template("index.html", items=items)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        mc = request.form.get("minecraft_username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(mc) < 3 or len(password) < 8:
            flash("نام کاربری و نام Minecraft باید حداقل ۳ کاراکتر و رمز حداقل ۸ کاراکتر باشد.", "error")
            return render_template("register.html")

        try:
            db().execute(
                """INSERT INTO users
                   (username, minecraft_username, password_hash)
                   VALUES (?, ?, ?)""",
                (username, mc, generate_password_hash(password)),
            )
            db().commit()
            flash("حساب ساخته شد. حالا وارد شوید.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("این نام کاربری یا Minecraft قبلاً ثبت شده است.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            flash("با موفقیت وارد شدید.", "success")
            return redirect(url_for("profile"))

        flash("نام کاربری یا رمز سایت اشتباه است.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("از حساب خارج شدید.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        bio = request.form.get("bio", "").strip()[:500]
        avatar = request.form.get("avatar", "").strip()[:500]
        db().execute(
            "UPDATE users SET bio = ?, avatar = ? WHERE id = ?",
            (bio, avatar, user["id"])
        )
        db().commit()
        flash("پروفایل ذخیره شد.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


@app.route("/support", methods=["GET", "POST"])
@login_required
def support():
    user = current_user()
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()[:100]
        message = request.form.get("message", "").strip()[:2000]
        if not subject or not message:
            flash("موضوع و متن تیکت را کامل کنید.", "error")
        else:
            db().execute(
                "INSERT INTO tickets (user_id, subject, message) VALUES (?, ?, ?)",
                (user["id"], subject, message)
            )
            db().commit()
            flash("تیکت شما ثبت شد.", "success")
            return redirect(url_for("support"))

    tickets = db().execute(
        "SELECT * FROM tickets WHERE user_id = ? ORDER BY id DESC",
        (user["id"],)
    ).fetchall()
    return render_template("support.html", tickets=tickets)


@app.route("/admin")
@admin_required
def admin():
    conn = db()
    tickets = conn.execute(
        """SELECT tickets.*, users.username, users.minecraft_username
           FROM tickets JOIN users ON users.id = tickets.user_id
           ORDER BY tickets.id DESC"""
    ).fetchall()
    users = conn.execute(
        "SELECT id, username, minecraft_username FROM users ORDER BY id DESC"
    ).fetchall()
    items = conn.execute("SELECT * FROM shop_items ORDER BY id DESC").fetchall()
    admins = conn.execute(
        """SELECT users.id, users.username, users.minecraft_username
           FROM admins JOIN users ON users.id = admins.user_id
           ORDER BY users.username"""
    ).fetchall()
    return render_template(
        "admin.html", tickets=tickets, users=users, items=items, admins=admins
    )


@app.post("/admin/ticket/<int:ticket_id>")
@admin_required
def reply_ticket(ticket_id):
    reply = request.form.get("reply", "").strip()[:3000]
    status = request.form.get("status", "open")
    if status not in {"open", "closed"}:
        status = "open"
    db().execute(
        "UPDATE tickets SET admin_reply = ?, status = ? WHERE id = ?",
        (reply, status, ticket_id)
    )
    db().commit()
    flash("تیکت بروزرسانی شد.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/shop/add")
@admin_required
def add_shop_item():
    name = request.form.get("name", "").strip()[:80]
    category = request.form.get("category", "سایر").strip()[:40]
    description = request.form.get("description", "").strip()[:300]
    icon = request.form.get("icon", "🐉").strip()[:10]
    try:
        price = max(0, int(request.form.get("price", "0")))
    except ValueError:
        price = 0

    if not name:
        flash("نام آیتم را وارد کنید.", "error")
    else:
        db().execute(
            """INSERT INTO shop_items
               (name, category, description, price, icon)
               VALUES (?, ?, ?, ?, ?)""",
            (name, category, description, price, icon)
        )
        db().commit()
        flash("آیتم شاپ اضافه شد.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/shop/<int:item_id>/delete")
@admin_required
def delete_shop_item(item_id):
    db().execute("DELETE FROM shop_items WHERE id = ?", (item_id,))
    db().commit()
    flash("آیتم حذف شد.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/shop/<int:item_id>/toggle")
@admin_required
def toggle_shop_item(item_id):
    db().execute(
        "UPDATE shop_items SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END WHERE id = ?",
        (item_id,)
    )
    db().commit()
    flash("وضعیت آیتم تغییر کرد.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/add-admin")
@admin_required
def add_admin():
    minecraft_username = request.form.get("minecraft_username", "").strip()
    user = db().execute(
        "SELECT id FROM users WHERE minecraft_username = ?",
        (minecraft_username,)
    ).fetchone()

    if not user:
        flash("کاربری با این Minecraft username پیدا نشد.", "error")
    else:
        db().execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
            (user["id"],)
        )
        db().commit()
        flash("ادمین اضافه شد.", "success")
    return redirect(url_for("admin"))


@app.post("/admin/remove-admin/<int:user_id>")
@admin_required
def remove_admin(user_id):
    # مالک اصلی را نمی‌توان از ادمینی حذف کرد.
    owner = db().execute(
        "SELECT id FROM users WHERE username = ?", (OWNER_USERNAME,)
    ).fetchone()
    if owner and owner["id"] == user_id:
        flash("ادمین اصلی قابل حذف نیست.", "error")
    else:
        db().execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        db().commit()
        flash("دسترسی ادمین حذف شد.", "success")
    return redirect(url_for("admin"))


@app.route("/health")
def health():
    return {"status": "ok", "service": "Nine Server"}


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
