# SpendSmart — Full-Stack Version (Frontend + Backend)
# Backend: Python Flask + SQLite database
# Run:  pip install -r requirements.txt   ->   python app.py   ->   http://127.0.0.1:5000
#
# What this backend does (everything the old localStorage version faked or kept in the browser):
#   * Real user accounts (register / login / logout) with salted-hash passwords
#   * Cards, Expenses and Bills stored in a SQLite database (data survives browser change)
#   * Dashboard, Insights and Rewards are COMPUTED on the server from real data
#   * Server-side validation on every input

import os
import re
import sqlite3
import hashlib
from datetime import datetime
from functools import wraps

from flask import Flask, request, jsonify, session, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "spendsmart.db")

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="/static")
app.secret_key = os.environ.get("SPENDSMART_SECRET", "spendsmart-dev-secret-change-me")

CATEGORIES = ["Food", "Shopping", "Travel", "Bills", "Education", "Other"]

# ---------------------------------------------------------------- DB helpers
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            pass_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            bank TEXT NOT NULL DEFAULT '',
            name TEXT NOT NULL,
            credit_limit REAL NOT NULL,
            reward TEXT NOT NULL DEFAULT '',
            theme TEXT NOT NULL DEFAULT 'custom'
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            payment TEXT NOT NULL,
            date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            name TEXT NOT NULL,
            amount REAL NOT NULL,
            minimum REAL NOT NULL,
            date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
        );
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------- passwords
def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return digest.hex(), salt


# ---------------------------------------------------------------- seed data
SEED_CARDS = [
    ("HDFC BANK", "Millennia Credit Card", 100000, "5% Cashback", "hdfc"),
    ("SBI CARD", "Cashback Credit Card", 80000, "5% Cashback", "sbi"),
    ("AXIS BANK", "Atlas Credit Card", 150000, "Travel Points", "axis"),
    ("ICICI BANK", "Coral Credit Card", 75000, "Reward Points", "icici"),
    ("AMAZON PAY ICICI", "Amazon Pay Card", 60000, "Amazon Cashback", "amazon"),
    ("KOTAK BANK", "League Credit Card", 90000, "Reward Points", "kotak"),
]
SEED_EXPENSES = [
    ("Swiggy Order", 450, "Food", "Millennia Credit Card", "2026-10-26"),
    ("Amazon Shopping", 2999, "Shopping", "Cashback Credit Card", "2026-10-27"),
    ("Uber Rides", 620, "Travel", "Atlas Credit Card", "2026-10-28"),
    ("Electricity Bill", 1450, "Bills", "Coral Credit Card", "2026-10-28"),
    ("Course Books", 899, "Education", "Cash", "2026-10-29"),
    ("Movie Tickets", 550, "Other", "Millennia Credit Card", "2026-10-29"),
]
SEED_BILLS = [
    ("Millennia Card Bill", 12500, 600, "2026-11-05", "Pending"),
    ("SBI Cashback Bill", 8300, 450, "2026-10-28", "Paid"),
]


def seed_user(conn, user_id):
    conn.executemany(
        "INSERT INTO cards (user_id, bank, name, credit_limit, reward, theme) VALUES (?,?,?,?,?,?)",
        [(user_id, b, n, lim, r, t) for b, n, lim, r, t in SEED_CARDS],
    )
    conn.executemany(
        "INSERT INTO expenses (user_id, name, amount, category, payment, date) VALUES (?,?,?,?,?,?)",
        [(user_id, n, a, c, p, d) for n, a, c, p, d in SEED_EXPENSES],
    )
    conn.executemany(
        "INSERT INTO bills (user_id, name, amount, minimum, date, status) VALUES (?,?,?,?,?,?)",
        [(user_id, n, a, m, d, s) for n, a, m, d, s in SEED_BILLS],
    )


# ---------------------------------------------------------------- auth guard
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Login required"}), 401
        return fn(*args, **kwargs)

    return wrapper


def valid_date(value):
    try:
        datetime.strptime(value or "", "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def money(value):
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- auth APIs
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters"}), 400
    pass_hash, salt = hash_password(password)
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO users (username, pass_hash, salt, created_at) VALUES (?,?,?,?)",
            (username, pass_hash, salt, datetime.now().isoformat(timespec="seconds")),
        )
        user_id = cur.lastrowid
        seed_user(conn, user_id)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Username already exists — please login"}), 409
    conn.close()
    session["user_id"] = user_id
    session["username"] = username
    return jsonify({"ok": True, "username": username}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "User not found — please register first"}), 404
    digest, _ = hash_password(password, row["salt"])
    if digest != row["pass_hash"]:
        return jsonify({"error": "Wrong password"}), 401
    session["user_id"] = row["id"]
    session["username"] = row["username"]
    return jsonify({"ok": True, "username": row["username"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me")
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "username": session["username"]})


# ---------------------------------------------------------------- cards APIs
@app.route("/api/cards", methods=["GET"])
@login_required
def list_cards():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM cards WHERE user_id = ? ORDER BY id", (session["user_id"],)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/cards", methods=["POST"])
@login_required
def add_card():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    reward = (data.get("reward") or "").strip()
    limit = money(data.get("limit"))
    if not name or limit is None or limit <= 0 or not reward:
        return jsonify({"error": "Please fill all card details with a valid credit limit"}), 400
    conn = db()
    cur = conn.execute(
        "INSERT INTO cards (user_id, bank, name, credit_limit, reward, theme) VALUES (?,?,?,?,?,?)",
        (session["user_id"], (data.get("bank") or "").strip().upper(), name, limit, reward, "custom"),
    )
    conn.commit()
    card_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": card_id}), 201


@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
@login_required
def delete_card(card_id):
    conn = db()
    cur = conn.execute(
        "DELETE FROM cards WHERE id = ? AND user_id = ?", (card_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Card not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------- expenses APIs
@app.route("/api/expenses", methods=["GET"])
@login_required
def list_expenses():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC, id DESC",
        (session["user_id"],),
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/expenses", methods=["POST"])
@login_required
def add_expense():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    amount = money(data.get("amount"))
    category = data.get("category") or ""
    payment = (data.get("payment") or "").strip()
    date = data.get("date") or ""
    if not name or amount is None or amount <= 0 or not valid_date(date):
        return jsonify({"error": "Please enter valid expense details"}), 400
    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400
    if not payment:
        return jsonify({"error": "Please choose a payment method"}), 400
    conn = db()
    cur = conn.execute(
        "INSERT INTO expenses (user_id, name, amount, category, payment, date) VALUES (?,?,?,?,?,?)",
        (session["user_id"], name, amount, category, payment, date),
    )
    conn.commit()
    exp_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": exp_id}), 201


@app.route("/api/expenses/<int:exp_id>", methods=["DELETE"])
@login_required
def delete_expense(exp_id):
    conn = db()
    cur = conn.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?", (exp_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Expense not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------- bills APIs
@app.route("/api/bills", methods=["GET"])
@login_required
def list_bills():
    conn = db()
    rows = conn.execute(
        "SELECT * FROM bills WHERE user_id = ? ORDER BY date, id", (session["user_id"],)
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/bills", methods=["POST"])
@login_required
def add_bill():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    amount = money(data.get("amount"))
    minimum = money(data.get("minimum"))
    date = data.get("date") or ""
    if not name or amount is None or amount <= 0 or minimum is None or minimum < 0 or not valid_date(date):
        return jsonify({"error": "Please enter valid bill details"}), 400
    if minimum > amount:
        return jsonify({"error": "Minimum payable cannot be greater than total amount"}), 400
    conn = db()
    cur = conn.execute(
        "INSERT INTO bills (user_id, name, amount, minimum, date, status) VALUES (?,?,?,?,?, 'Pending')",
        (session["user_id"], name, amount, minimum, date),
    )
    conn.commit()
    bill_id = cur.lastrowid
    conn.close()
    return jsonify({"ok": True, "id": bill_id}), 201


@app.route("/api/bills/<int:bill_id>/toggle", methods=["PATCH"])
@login_required
def toggle_bill(bill_id):
    conn = db()
    row = conn.execute(
        "SELECT status FROM bills WHERE id = ? AND user_id = ?", (bill_id, session["user_id"])
    ).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "Bill not found"}), 404
    new_status = "Paid" if row["status"] == "Pending" else "Pending"
    conn.execute(
        "UPDATE bills SET status = ? WHERE id = ? AND user_id = ?",
        (new_status, bill_id, session["user_id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": new_status})


@app.route("/api/bills/<int:bill_id>", methods=["DELETE"])
@login_required
def delete_bill(bill_id):
    conn = db()
    cur = conn.execute(
        "DELETE FROM bills WHERE id = ? AND user_id = ?", (bill_id, session["user_id"])
    )
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "Bill not found"}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------- computed APIs
def user_totals(conn, user_id):
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return row["total"], row["n"]


def reward_points(total_expenses):
    # Rule: 1 reward point for every Rs 100 spent
    return int(total_expenses // 100)


def estimated_cashback(conn, user_id):
    # Rule: for expenses paid with a card whose reward text names a cashback %,
    # cashback = that % of the expense. The % is read from the card's own reward text.
    cards = {
        r["name"]: r["reward"]
        for r in conn.execute("SELECT name, reward FROM cards WHERE user_id = ?", (user_id,)).fetchall()
    }
    total = 0.0
    for exp in conn.execute(
        "SELECT amount, payment FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchall():
        reward_text = cards.get(exp["payment"], "")
        if "cashback" in reward_text.lower():
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", reward_text)
            if m:
                total += exp["amount"] * float(m.group(1)) / 100.0
    return round(total, 2)


@app.route("/api/dashboard")
@login_required
def dashboard():
    conn = db()
    uid = session["user_id"]
    total, _ = user_totals(conn, uid)
    total_cards = conn.execute(
        "SELECT COUNT(*) AS n FROM cards WHERE user_id = ?", (uid,)
    ).fetchone()["n"]
    pending = conn.execute(
        "SELECT COUNT(*) AS n FROM bills WHERE user_id = ? AND status = 'Pending'", (uid,)
    ).fetchone()["n"]
    conn.close()
    return jsonify(
        {
            "total_expenses": total,
            "total_cards": total_cards,
            "reward_points": reward_points(total),
            "pending_bills": pending,
        }
    )


@app.route("/api/insights")
@login_required
def insights():
    conn = db()
    uid = session["user_id"]
    sums = {
        r["category"]: r["s"]
        for r in conn.execute(
            "SELECT category, COALESCE(SUM(amount), 0) AS s FROM expenses WHERE user_id = ? GROUP BY category",
            (uid,),
        ).fetchall()
    }
    total, _ = user_totals(conn, uid)
    conn.close()
    food = sums.get("Food", 0)
    shopping = sums.get("Shopping", 0)
    travel = sums.get("Travel", 0)
    return jsonify(
        {
            "food": food,
            "shopping": shopping,
            "travel": travel,
            "other": round(total - food - shopping - travel, 2),
            "by_category": sums,
            "total": total,
        }
    )


@app.route("/api/rewards")
@login_required
def rewards():
    conn = db()
    uid = session["user_id"]
    total, _ = user_totals(conn, uid)
    cashback = estimated_cashback(conn, uid)
    travel = conn.execute(
        "SELECT COUNT(*) AS n FROM cards WHERE user_id = ? AND LOWER(reward) LIKE '%travel%'",
        (uid,),
    ).fetchone()["n"]
    conn.close()
    return jsonify(
        {
            "points": reward_points(total),
            "cashback": cashback,
            "travel_benefits": "Available" if travel > 0 else "Not Available",
        }
    )


# ---------------------------------------------------------------- pages
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
