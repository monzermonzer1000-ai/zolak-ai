
import os
import sqlite3
from functools import wraps

from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-in-production")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
)

DB = os.getenv("DATABASE_PATH", "zolak.db")


def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = db()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            credits INTEGER DEFAULT 10,
            is_admin INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    defaults = [
        ("site_name", "زولك AI 🇸🇩"),
        ("free_credits", "10"),
        ("welcome", "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة."),
    ]

    for key, value in defaults:
        c.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
            (key, value)
        )

    admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "")

    if admin_email and admin_password:
        existing = c.execute(
            "SELECT id FROM users WHERE email = ?", (admin_email,)
        ).fetchone()

        if not existing:
            c.execute(
                """INSERT INTO users(name, email, password, credits, is_admin)
                   VALUES(?, ?, ?, ?, 1)""",
                (
                    os.getenv("ADMIN_NAME", "مدير زولك"),
                    admin_email,
                    generate_password_hash(admin_password),
                    999999
                )
            )

    c.commit()
    c.close()


def setting(key, default=""):
    c = db()
    result = c.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    c.close()
    return result["value"] if result else default


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return jsonify(error="لازم تسجل دخول أولاً."), 401
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper


def verify_password(stored_password, entered_password):
    try:
        if check_password_hash(stored_password, entered_password):
            return True, False
    except (ValueError, TypeError):
        pass

    if stored_password == entered_password:
        return True, True

    return False, False


init_db()


@app.get("/")
def home():
    return render_template("index.html", site_name=setting("site_name"))


@app.get("/login")
def login():
    return render_template("login.html")


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or len(password) < 4:
        return jsonify(
            error="أدخل البيانات كاملة، وكلمة المرور 4 أحرف على الأقل."
        ), 400

    try:
        credits = max(0, int(setting("free_credits", "10")))
    except ValueError:
        credits = 10

    c = db()
    try:
        c.execute(
            """INSERT INTO users(name, email, password, credits)
               VALUES(?, ?, ?, ?)""",
            (name, email, generate_password_hash(password), credits)
        )
        c.commit()
        user = c.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    except sqlite3.IntegrityError:
        c.close()
        return jsonify(error="الإيميل مستخدم قبل كده."), 409

    c.close()
    session.clear()
    session.update(
        uid=user["id"],
        name=user["name"],
        admin=bool(user["is_admin"])
    )
    return jsonify(ok=True)


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    c = db()
    user = c.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()

    if not user:
        c.close()
        return jsonify(error="الإيميل أو كلمة المرور غلط."), 401

    valid, legacy_password = verify_password(user["password"], password)
    if not valid:
        c.close()
        return jsonify(error="الإيميل أو كلمة المرور غلط."), 401

    if legacy_password:
        c.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (generate_password_hash(password), user["id"])
        )
        c.commit()

    c.close()
    session.clear()
    session.update(
        uid=user["id"],
        name=user["name"],
        admin=bool(user["is_admin"])
    )
    return jsonify(ok=True)


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.get("/api/me")
def me():
    if "uid" not in session:
        return jsonify(logged_in=False)

    c = db()
    user = c.execute(
        "SELECT name, email, credits, is_admin FROM users WHERE id = ?",
        (session["uid"],)
    ).fetchone()
    c.close()

    if not user:
        session.clear()
        return jsonify(logged_in=False)

    return jsonify(logged_in=True, **dict(user))


@app.post("/api/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()

    if not message:
        return jsonify(error="اكتب رسالتك أولاً."), 400

    if len(message) > 12000:
        return jsonify(error="الرسالة طويلة شديد. اختصرها وجرب تاني."), 400

    c = db()
    user = c.execute(
        "SELECT credits FROM users WHERE id = ?", (session["uid"],)
    ).fetchone()

    if not user:
        c.close()
        session.clear()
        return jsonify(error="سجل دخولك من جديد."), 401

    if user["credits"] <= 0:
        c.close()
        return jsonify(
            error="رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"
        ), 402

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        c.close()
        return jsonify(
            error="مفتاح الذكاء الاصطناعي ما مضاف في إعدادات الاستضافة."
        ), 503

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        previous = c.execute(
            """SELECT role, content FROM chats
               WHERE user_id = ? ORDER BY id DESC LIMIT 12""",
            (session["uid"],)
        ).fetchall()

        history = []
        for item in reversed(previous):
            role = "user" if item["role"] == "user" else "model"
            history.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=item["content"])]
                )
            )

        history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=message)]
            )
        )

        response = client.models.generate_content(
            model=model,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "أنت زولك AI، مساعد ذكاء اصطناعي سوداني ودود. "
                    "أجب بوضوح ودقة، واستخدم اللهجة السودانية عندما يطلبها "
                    "المستخدم. لا تدّعي أنك إنسان، وإذا لم تعرف الإجابة "
                    "فقل ذلك بوضوح."
                ),
                temperature=0.7
            )
        )

        answer = (response.text or "").strip()
        if not answer:
            c.close()
            return jsonify(
                error="ما قدرنا نستخرج رد من الخدمة. جرّب تاني."
            ), 502

        result = c.execute(
            """UPDATE users SET credits = credits - 1
               WHERE id = ? AND credits > 0""",
            (session["uid"],)
        )

        if result.rowcount != 1:
            c.rollback()
            c.close()
            return jsonify(error="رصيدك ما كفاية لإرسال رسالة جديدة."), 402

        c.execute(
            "INSERT INTO chats(user_id, role, content) VALUES(?, ?, ?)",
            (session["uid"], "user", message)
        )
        c.execute(
            "INSERT INTO chats(user_id, role, content) VALUES(?, ?, ?)",
            (session["uid"], "assistant", answer)
        )
        c.commit()
        c.close()

        return jsonify(answer=answer)

    except Exception:
        c.close()
        app.logger.exception("AI response failed")
        return jsonify(
            error="حصلت مشكلة في خدمة الذكاء الاصطناعي. جرّب تاني."
        ), 500


@app.get("/api/chats")
@login_required
def chats():
    c = db()
    rows = c.execute(
        """SELECT role, content, created_at FROM chats
           WHERE user_id = ? ORDER BY id DESC LIMIT 50""",
        (session["uid"],)
    ).fetchall()
    c.close()

    return jsonify(chats=[dict(row) for row in reversed(rows)])


@app.get("/admin")
@admin_required
def admin():
    c = db()
    users = c.execute(
        """SELECT id, name, email, credits, is_admin
           FROM users ORDER BY id DESC"""
    ).fetchall()

    total = c.execute(
        "SELECT COUNT(*) AS n FROM users"
    ).fetchone()["n"]

    messages = c.execute(
        "SELECT COUNT(*) AS n FROM chats"
    ).fetchone()["n"]

    c.close()

    return render_template(
        "admin.html",
        users=users,
        total=total,
        msgs=messages,
        free=setting("free_credits", "10")
    )


@app.post("/api/admin/settings")
@admin_required
def admin_settings():
    data = request.get_json(silent=True) or {}
    c = db()

    if "free_credits" in data:
        try:
            credits = max(0, int(data["free_credits"]))
        except (ValueError, TypeError):
            c.close()
            return jsonify(error="قيمة الرصيد غير صحيحة."), 400

        c.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
            ("free_credits", str(credits))
        )

    if "welcome" in data:
        welcome = str(data["welcome"])[:1000]
        c.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
            ("welcome", welcome)
        )

    c.commit()
    c.close()
    return jsonify(ok=True)


@app.post("/api/admin/user/<int:uid>/credits")
@admin_required
def add_credits(uid):
    data = request.get_json(silent=True) or {}

    try:
        amount = int(data.get("amount", 10))
    except (ValueError, TypeError):
        return jsonify(error="عدد الرصيد غير صحيح."), 400

    if amount < 0 or amount > 100000:
        return jsonify(error="قيمة الرصيد خارج الحدود المسموحة."), 400

    c = db()
    result = c.execute(
        "UPDATE users SET credits = credits + ? WHERE id = ?",
        (amount, uid)
    )
    c.commit()
    c.close()

    if result.rowcount != 1:
        return jsonify(error="المستخدم غير موجود."), 404

    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000"))
    )
