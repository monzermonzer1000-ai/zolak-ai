import os
import sqlite3
import time
import json
import logging
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-in-production")
DB = os.getenv("DB_PATH", "/tmp/zolak.db")

logging.basicConfig(level=logging.INFO)

DEFAULT_SETTINGS = {
    "site_name": "زولك AI 🇸🇩",
    "site_description": "مساعد ذكاء اصطناعي سوداني يساعدك في الكتابة والدراسة والترجمة والشغل والدردشة 🇸🇩🤖",
    "free_credits": "10",
    "welcome": "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة.",
    "homepage_title": "زولك AI 🇸🇩",
    "homepage_subtitle": "مساعد الذكاء الاصطناعي السوداني 🇸🇩",
    "homepage_button": "ابدأ الآن",
    "primary_color": "#00c896",
    "theme": "dark",
    "mobile_ui": "1",
    "no_credits_message": "رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️",
    "error_message": "حصلت مشكلة، حاول مرة تانية.",
    "logo_url": "",
    "background_url": "",
    "sudan_identity": "1",
    "ad_text": "",
    "notifications": "1",
    "ai_model": "gemini-3.6-flash",
    "ai_free_messages": "10",
    "feature_writing": "1",
    "feature_translation": "1",
    "feature_study": "1",
    "registration_enabled": "1",
    "chat_history_enabled": "1",
    "email_login_enabled": "1",
    "maintenance_mode": "0",
    "allow_login": "1",
    "admin_protection": "1",
    "packages": "[]"
}


def db():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def setting(key, default=""):
    c = db()
    try:
        row = c.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        c.close()


def init_db():
    c = db()

    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        credits INTEGER DEFAULT 10,
        is_admin INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS conversations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT DEFAULT 'محادثة جديدة',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        conversation_id INTEGER,
        role TEXT,
        content TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT
    )""")

    user_cols = [
        x["name"]
        for x in c.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "banned" not in user_cols:
        c.execute(
            "ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0"
        )

    chat_cols = [
        x["name"]
        for x in c.execute("PRAGMA table_info(chats)").fetchall()
    ]

    if "conversation_id" not in chat_cols:
        c.execute(
            "ALTER TABLE chats ADD COLUMN conversation_id INTEGER"
        )

    for key, value in DEFAULT_SETTINGS.items():
        c.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value)
        )

    admin = c.execute(
        "SELECT id FROM users WHERE is_admin=1 LIMIT 1"
    ).fetchone()

    if not admin:
        c.execute(
            """INSERT INTO users
               (name,email,password,credits,is_admin,banned)
               VALUES(?,?,?,?,?,?)""",
            (
                "مدير زولك",
                "admin@zolak.ai",
                generate_password_hash("admin123"),
                9999,
                1,
                0
            )
        )

    old_users = c.execute(
        """SELECT DISTINCT user_id FROM chats
           WHERE conversation_id IS NULL
           AND user_id IS NOT NULL"""
    ).fetchall()

    for item in old_users:
        uid = item["user_id"]

        conv = c.execute(
            """SELECT id FROM conversations
               WHERE user_id=?
               ORDER BY id LIMIT 1""",
            (uid,)
        ).fetchone()

        if conv:
            conv_id = conv["id"]
        else:
            cur = c.execute(
                """INSERT INTO conversations(user_id,title)
                   VALUES(?,?)""",
                (uid, "المحادثات القديمة")
            )
            conv_id = cur.lastrowid

        c.execute(
            """UPDATE chats
               SET conversation_id=?
               WHERE user_id=?
               AND conversation_id IS NULL""",
            (conv_id, uid)
        )

    c.commit()
    c.close()


init_db()


def make_title(message):
    title = " ".join(str(message).strip().split())

    if not title:
        return "محادثة جديدة"

    return title[:42].rstrip() + (
        "..." if len(title) > 42 else ""
    )


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("uid"):
            return jsonify(
                error="لازم تسجل دخول أولاً."
            ), 401

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if (
            not session.get("uid")
            or not session.get("admin")
        ):
            return jsonify(
                error="غير مصرح لك."
            ), 403

        return fn(*args, **kwargs)

    return wrapper


def current_user():
    if not session.get("uid"):
        return None

    c = db()

    try:
        return c.execute(
            "SELECT * FROM users WHERE id=?",
            (session["uid"],)
        ).fetchone()
    finally:
        c.close()


@app.get("/")
def home():
    return render_template(
        "index.html",
        site_name=setting(
            "site_name",
            "زولك AI 🇸🇩"
        ),
        site_description=setting(
            "site_description",
            ""
        ),
        welcome=setting(
            "welcome",
            ""
        ),
        homepage_title=setting(
            "homepage_title",
            "زولك AI 🇸🇩"
        ),
        homepage_subtitle=setting(
            "homepage_subtitle",
            ""
        ),
        homepage_button=setting(
            "homepage_button",
            "ابدأ الآن"
        ),
        primary_color=setting(
            "primary_color",
            "#00c896"
        ),
        theme=setting(
            "theme",
            "dark"
        ),
        logo_url=setting(
            "logo_url",
            ""
        ),
        background_url=setting(
            "background_url",
            ""
        ),
        ad_text=setting(
            "ad_text",
            ""
        ),
        no_credits_message=setting(
            "no_credits_message",
            ""
        ),
        error_message=setting(
            "error_message",
            ""
        )
    )


@app.get("/login")
def login():
    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.post("/api/register")
def register():
    if setting("registration_enabled", "1") != "1":
        return jsonify(
            error="التسجيل متوقف حالياً."
        ), 403

    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or len(password) < 4:
        return jsonify(
            error="أدخل البيانات كاملة، وكلمة المرور 4 أحرف على الأقل."
        ), 400

    try:
        credits = max(
            0,
            int(setting("free_credits", "10"))
        )
    except (ValueError, TypeError):
        credits = 10

    c = db()

    try:
        c.execute(
            """INSERT INTO users
               (name,email,password,credits,banned)
               VALUES(?,?,?,?,0)""",
            (
                name,
                email,
                generate_password_hash(password),
                credits
            )
        )

        c.commit()

        user = c.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

    except sqlite3.IntegrityError:
        c.close()

        return jsonify(
            error="الإيميل مستخدم قبل كده."
        ), 409

    c.close()

    session.clear()
    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(user["is_admin"])

    return jsonify(ok=True)


@app.post("/api/login")
def api_login():
    if setting("allow_login", "1") != "1":
        return jsonify(
            error="تسجيل الدخول متوقف حالياً."
        ), 403

    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    c = db()

    user = c.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    ).fetchone()

    if not user:
        c.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    try:
        valid = check_password_hash(
            user["password"],
            password
        )
    except Exception:
        valid = False

    if not valid and user["password"] == password:
        valid = True

        c.execute(
            "UPDATE users SET password=? WHERE id=?",
            (
                generate_password_hash(password),
                user["id"]
            )
        )

        c.commit()

    if not valid:
        c.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    if user["banned"] and not user["is_admin"]:
        c.close()

        return jsonify(
            error="الحساب موقوف حالياً. تواصل مع إدارة زولك."
        ), 403

    c.close()

    session.clear()
    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(user["is_admin"])

    return jsonify(ok=True)


@app.get("/api/me")
def me():
    user = current_user()

    if not user:
        session.clear()

        return jsonify(
            logged_in=False
        )

    return jsonify(
        logged_in=True,
        name=user["name"],
        email=user["email"],
        credits=user["credits"],
        is_admin=bool(user["is_admin"]),
        banned=bool(user["banned"])
    )


@app.post("/api/conversations")
@login_required
def new_conversation():
    if setting("chat_history_enabled", "1") != "1":
        return jsonify(
            error="حفظ المحادثات متوقف حالياً."
        ), 403

    c = db()

    cur = c.execute(
        """INSERT INTO conversations(user_id,title)
           VALUES(?,?)""",
        (
            session["uid"],
            "محادثة جديدة"
        )
    )

    conv_id = cur.lastrowid

    c.commit()

    row = c.execute(
        "SELECT * FROM conversations WHERE id=?",
        (conv_id,)
    ).fetchone()

    c.close()

    return jsonify(
        ok=True,
        conversation=dict(row)
    )


@app.get("/api/conversations")
@login_required
def conversations():
    if setting("chat_history_enabled", "1") != "1":
        return jsonify(
            conversations=[]
        )

    c = db()

    rows = c.execute(
        """SELECT id,title,created_at,updated_at
           FROM conversations
           WHERE user_id=?
           ORDER BY updated_at DESC,id DESC""",
        (session["uid"],)
    ).fetchall()

    c.close()

    return jsonify(
        conversations=[
            dict(x) for x in rows
        ]
    )


@app.get("/api/conversations/<int:conversation_id>")
@login_required
def get_conversation_messages(conversation_id):
    if setting("chat_history_enabled", "1") != "1":
        return jsonify(
            error="حفظ المحادثات متوقف حالياً."
        ), 403

    c = db()

    conv = c.execute(
        """SELECT * FROM conversations
           WHERE id=? AND user_id=?""",
        (
            conversation_id,
            session["uid"]
        )
    ).fetchone()

    if not conv:
        c.close()

        return jsonify(
            error="المحادثة غير موجودة."
        ), 404

    rows = c.execute(
        """SELECT id,role,content,created_at
           FROM chats
           WHERE user_id=?
           AND conversation_id=?
           ORDER BY id""",
        (
            session["uid"],
            conversation_id
        )
    ).fetchall()

    c.close()

    return jsonify(
        conversation=dict(conv),
        chats=[dict(x) for x in rows]
    )


@app.delete("/api/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id):
    c = db()

    conv = c.execute(
        """SELECT id FROM conversations
           WHERE id=? AND user_id=?""",
        (
            conversation_id,
            session["uid"]
        )
    ).fetchone()

    if not conv:
        c.close()

        return jsonify(
            error="المحادثة غير موجودة."
        ), 404

    c.execute(
        """DELETE FROM chats
           WHERE conversation_id=?
           AND user_id=?""",
        (
            conversation_id,
            session["uid"]
        )
    )

    c.execute(
        """DELETE FROM conversations
           WHERE id=? AND user_id=?""",
        (
            conversation_id,
            session["uid"]
        )
    )

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        message="تم حذف المحادثة."
    )


@app.post("/api/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    if not message:
        return jsonify(
            error="اكتب رسالتك أولاً."
        ), 400

    user_id = session["uid"]
    c = db()

    try:
        user = c.execute(
            """SELECT credits,banned,is_admin
               FROM users
               WHERE id=?""",
            (user_id,)
        ).fetchone()

        if not user:
            return jsonify(
                error="الحساب غير موجود."
            ), 404

        if user["banned"] and not user["is_admin"]:
            return jsonify(
                error="حسابك موقوف حالياً."
            ), 403

        if (
            user["credits"] <= 0
            and not user["is_admin"]
        ):
            return jsonify(
                error=setting(
                    "no_credits_message",
                    "رصيدك المجاني خلص."
                )
            ), 402

        conv_id = data.get("conversation_id")

        try:
            conv_id = (
                int(conv_id)
                if conv_id is not None
                else None
            )
        except (ValueError, TypeError):
            return jsonify(
                error="رقم المحادثة غير صحيح."
            ), 400

        if conv_id is None:
            cur = c.execute(
                """INSERT INTO conversations
                   (user_id,title)
                   VALUES(?,?)""",
                (
                    user_id,
                    make_title(message)
                )
            )

            conv_id = cur.lastrowid

        else:
            conv = c.execute(
                """SELECT id
                   FROM conversations
                   WHERE id=? AND user_id=?""",
                (
                    conv_id,
                    user_id
                )
            ).fetchone()

            if not conv:
                return jsonify(
                    error="المحادثة غير موجودة."
                ), 404

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not api_key:
            app.logger.error(
                "GEMINI_API_KEY is missing"
            )

            c.rollback()

            return jsonify(
                error="خدمة الذكاء الاصطناعي غير متاحة حالياً."
            ), 503

        try:
            from google import genai
            from google.genai import types
        except Exception:
            app.logger.exception(
                "Failed to import google.genai"
            )

            c.rollback()

            return jsonify(
                error="خدمة الذكاء الاصطناعي غير متاحة حالياً."
            ), 503

        try:
            client = genai.Client(
                api_key=api_key
            )

            config = types.GenerateContentConfig(
                system_instruction=(
                    "أنت زولك AI 🇸🇩، "
                    "مساعد ذكاء اصطناعي سوداني ودود. "
                    "أجب بوضوح وباختصار مناسب. "
                    "استخدم اللهجة السودانية عندما يطلبها المستخدم. "
                    "لا تدّعي أنك إنسان."
                )
            )

            model = setting(
                "ai_model",
                "gemini-3.6-flash"
            ).strip()

            if not model:
                model = "gemini-3.6-flash"

            response = None
            last_error = None

            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=message,
                        config=config
                    )

                    break

                except Exception as exc:
                    last_error = exc
                    error_text = str(exc).upper()

                    app.logger.error(
                        "Gemini attempt %s failed: %s",
                        attempt + 1,
                        str(exc)
                    )

                    temporary = any(
                        x in error_text
                        for x in (
                            "503",
                            "UNAVAILABLE",
                            "429",
                            "RESOURCE_EXHAUSTED",
                            "TIMEOUT",
                            "DEADLINE"
                        )
                    )

                    if temporary and attempt < 2:
                        time.sleep(
                            2 * (attempt + 1)
                        )
                        continue

                    raise

            if response is None:
                raise RuntimeError(
                    str(last_error)
                    if last_error
                    else "Gemini returned no response"
                )

        except Exception as exc:
            app.logger.exception(
                "Gemini user chat failed | "
                "user_id=%s | model=%s | error=%s",
                user_id,
                model,
                str(exc)
            )

            c.rollback()

            error_text = str(exc).upper()

            if (
                "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
            ):
                return jsonify(
                    error="الخدمة عليها ضغط أو وصلت للحد المسموح. جرّب تاني بعد شوية."
                ), 429

            if (
                "503" in error_text
                or "UNAVAILABLE" in error_text
            ):
                return jsonify(
                    error="الخدمة عليها ضغط شديد حالياً. انتظر شوية وجرب تاني يا زول ❤️"
                ), 503

            if (
                "404" in error_text
                or "NOT_FOUND" in error_text
            ):
                return jsonify(
                    error="خدمة الذكاء الاصطناعي غير متاحة حالياً."
                ), 503

            return jsonify(
                error=setting(
                    "error_message",
                    "حصلت مشكلة، حاول مرة تانية."
                )
            ), 500

        answer = (
            getattr(response, "text", None)
            or ""
        ).strip()

        if not answer:
            app.logger.error(
                "Gemini returned empty answer | "
                "user_id=%s | model=%s",
                user_id,
                model
            )

            c.rollback()

            return jsonify(
                error="الذكاء الاصطناعي ما رجّع إجابة. جرّب تاني."
            ), 502

        answer += (
            "\n\n— تطوير منذر السيد 🇸🇩"
        )

        if not user["is_admin"]:
            c.execute(
                """UPDATE users
                   SET credits=credits-1
                   WHERE id=? AND credits>0""",
                (user_id,)
            )

            if c.rowcount != 1:
                c.rollback()

                return jsonify(
                    error=setting(
                        "no_credits_message",
                        "رصيدك المجاني خلص."
                    )
                ), 402

        c.execute(
            """INSERT INTO chats
               (user_id,conversation_id,role,content)
               VALUES(?,?,?,?)""",
            (
                user_id,
                conv_id,
                "user",
                message
            )
        )

        c.execute(
            """INSERT INTO chats
               (user_id,conversation_id,role,content)
               VALUES(?,?,?,?)""",
            (
                user_id,
                conv_id,
                "assistant",
                answer
            )
        )

        c.execute(
            """UPDATE conversations
               SET title=?,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND user_id=?""",
            (
                make_title(message),
                conv_id,
                user_id
            )
        )

        c.commit()

        conv = c.execute(
            """SELECT id,title,created_at,updated_at
               FROM conversations
               WHERE id=? AND user_id=?""",
            (
                conv_id,
                user_id
            )
        ).fetchone()

        return jsonify(
            answer=answer,
            conversation_id=conv_id,
            conversation=dict(conv)
        )

    except Exception as exc:
        c.rollback()

        app.logger.exception(
            "Unexpected /api/chat error | "
            "user_id=%s | error=%s",
            user_id,
            str(exc)
        )

        return jsonify(
            error=setting(
                "error_message",
                "حصلت مشكلة، حاول مرة تانية."
            )
        ), 500

    finally:
        c.close()


@app.get("/api/chats")
@login_required
def chats():
    if setting("chat_history_enabled", "1") != "1":
        return jsonify(chats=[])

    c = db()

    rows = c.execute(
        """SELECT role,content,created_at,conversation_id
           FROM chats
           WHERE user_id=?
           ORDER BY id DESC LIMIT 50""",
        (session["uid"],)
    ).fetchall()

    c.close()

    return jsonify(
        chats=[dict(x) for x in rows]
    )


@app.get("/admin")
@login_required
@admin_required
def admin():
    return render_template(
        "admin.html"
    )


@app.get("/api/admin/settings")
@login_required
@admin_required
def admin_settings():
    c = db()

    rows = c.execute(
        "SELECT key,value FROM settings"
    ).fetchall()

    c.close()

    values = {
        x["key"]: x["value"]
        for x in rows
    }

    for key, value in DEFAULT_SETTINGS.items():
        values.setdefault(key, value)

    return jsonify(
        settings=values
    )


@app.post("/api/admin/settings")
@login_required
@admin_required
def save_admin_settings():
    data = request.get_json(silent=True) or {}

    allowed = set(
        DEFAULT_SETTINGS.keys()
    )

    c = db()

    for key, value in data.items():
        if key not in allowed:
            continue

        if isinstance(value, bool):
            value = "1" if value else "0"

        elif isinstance(value, (dict, list)):
           
