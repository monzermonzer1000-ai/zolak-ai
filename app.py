import os
import sqlite3
import io
import time
from functools import wraps
from datetime import datetime, timezone

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    send_file
)
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-secret-in-production"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv(
        "COOKIE_SECURE",
        "true"
    ).lower() == "true",
    MAX_CONTENT_LENGTH=15 * 1024 * 1024
)

DB = os.getenv(
    "DATABASE_PATH",
    "zolak.db"
)


# =========================================================
# قاعدة البيانات
# =========================================================

def db():
    connection = sqlite3.connect(
        DB,
        timeout=20
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


def init_db():

    c = db()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            credits INTEGER NOT NULL DEFAULT 10,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_banned INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # -----------------------------------------
    # الأعمدة الناقصة في قواعد البيانات القديمة
    # -----------------------------------------

    user_columns = {
        row["name"]
        for row in c.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    }

    if "is_banned" not in user_columns:

        c.execute("""
            ALTER TABLE users
            ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0
        """)

    if "created_at" not in user_columns:

        c.execute("""
            ALTER TABLE users
            ADD COLUMN created_at DATETIME
        """)

    # -----------------------------------------
    # الإعدادات الافتراضية
    # -----------------------------------------

    defaults = [
        (
            "site_name",
            "زولك AI 🇸🇩"
        ),
        (
            "free_credits",
            "10"
        ),
        (
            "welcome",
            "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة."
        ),
        (
            "maintenance",
            "false"
        ),
        (
            "allow_register",
            "true"
        ),
        (
            "ai_model",
            os.getenv(
                "GEMINI_MODEL",
                "gemini-3.8-flash"
            )
        ),
    ]

    for key, value in defaults:

        c.execute(
            """
            INSERT OR IGNORE INTO settings(key, value)
            VALUES(?, ?)
            """,
            (
                key,
                value
            )
        )

    # =====================================================
    # إنشاء / إصلاح حساب المدير
    # =====================================================

    admin_email = os.getenv(
        "ADMIN_EMAIL",
        "admin@zolak.ai"
    ).strip().lower()

    admin_password = os.getenv(
        "ADMIN_PASSWORD",
        "admin123"
    )

    admin_name = os.getenv(
        "ADMIN_NAME",
        "مدير زولك"
    )

    existing_admin = c.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (admin_email,)
    ).fetchone()

    if not existing_admin:

        c.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                credits,
                is_admin,
                is_banned
            )
            VALUES (?, ?, ?, ?, 1, 0)
            """,
            (
                admin_name,
                generate_password_hash(
                    admin_password
                ),
                999999
            )
        )

    else:

        c.execute(
            """
            UPDATE users
            SET
                name = ?,
                password = ?,
                credits = 999999,
                is_admin = 1,
                is_banned = 0
            WHERE email = ?
            """,
            (
                admin_name,
                generate_password_hash(
                    admin_password
                ),
                admin_email
            )
        )

    c.commit()
    c.close()


def setting(
    key,
    default=""
):

    c = db()

    result = c.execute(
        """
        SELECT value
        FROM settings
        WHERE key = ?
        """,
        (key,)
    ).fetchone()

    c.close()

    return (
        result["value"]
        if result
        else default
    )


def save_setting(
    c,
    key,
    value
):

    c.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (
            str(key),
            str(value)
        )
    )


init_db()


# =========================================================
# تسجيل الدخول والصلاحيات
# =========================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(
        *args,
        **kwargs
    ):

        if not session.get("uid"):

            return jsonify(
                error="لازم تسجل دخول أولاً."
            ), 401

        c = db()

        user = c.execute(
            """
            SELECT id, is_banned
            FROM users
            WHERE id = ?
            """,
            (session["uid"],)
        ).fetchone()

        c.close()

        if not user:

            session.clear()

            return jsonify(
                error="سجل دخولك من جديد."
            ), 401

        if user["is_banned"]:

            session.clear()

            return jsonify(
                error="حسابك موقوف. راجع الإدارة."
            ), 403

        return fn(
            *args,
            **kwargs
        )

    return wrapper


def admin_required(fn):

    @wraps(fn)
    def wrapper(
        *args,
        **kwargs
    ):

        if not session.get("uid"):

            if request.path.startswith("/api/"):

                return jsonify(
                    error="سجل دخولك أولاً."
                ), 401

            return redirect("/login")

        c = db()

        user = c.execute(
            """
            SELECT id, is_admin, is_banned
            FROM users
            WHERE id = ?
            """,
            (session["uid"],)
        ).fetchone()

        c.close()

        if (
            not user
            or user["is_banned"]
            or not user["is_admin"]
        ):

            session.clear()

            if request.path.startswith("/api/"):

                return jsonify(
                    error="ما عندك صلاحية للدخول."
                ), 403

            return redirect("/login")

        return fn(
            *args,
            **kwargs
        )

    return wrapper


def verify_password(
    stored_password,
    entered_password
):

    try:

        if check_password_hash(
            stored_password,
            entered_password
        ):

            return True, False

    except (
        ValueError,
        TypeError
    ):

        pass

    # دعم كلمات المرور القديمة
    if stored_password == entered_password:

        return True, True

    return False, False


# =========================================================
# الصفحات الأساسية
# =========================================================

@app.get("/")
def home():

    return render_template(
        "index.html",
        site_name=setting(
            "site_name",
            "زولك AI 🇸🇩"
        ),
        welcome=setting(
            "welcome",
            ""
        )
    )


@app.get("/login")
def login():

    return render_template(
        "login.html"
    )


@app.get("/admin")
@admin_required
def admin():

    c = db()

    users = c.execute(
        """
        SELECT
            id,
            name,
            email,
            credits,
            is_admin,
            is_banned,
            created_at
        FROM users
        ORDER BY id DESC
        LIMIT 100
        """
    ).fetchall()

    total = c.execute(
        """
        SELECT COUNT(*) AS n
        FROM users
        """
    ).fetchone()["n"]

    messages = c.execute(
        """
        SELECT COUNT(*) AS n
        FROM chats
        """
    ).fetchone()["n"]

    c.close()

    return render_template(
        "admin.html",
        users=users,
        total=total,
        msgs=messages,
        free=setting(
            "free_credits",
            "10"
        )
    )


@app.get("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# التسجيل
# =========================================================

@app.post("/api/register")
def register():

    if setting(
        "allow_register",
        "true"
    ).lower() == "false":

        return jsonify(
            error="التسجيل متوقف حالياً."
        ), 403

    data = request.get_json(
        silent=True
    ) or {}

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    email = str(
        data.get(
            "email",
            ""
        )
    ).strip().lower()

    password = str(
        data.get(
            "password",
            ""
        )
    )

    if (
        not name
        or not email
        or len(password) < 4
    ):

        return jsonify(
            error="أدخل البيانات كاملة، وكلمة المرور 4 أحرف على الأقل."
        ), 400

    if (
        len(name) > 100
        or len(email) > 200
    ):

        return jsonify(
            error="البيانات المدخلة طويلة."
        ), 400

    try:

        credits = max(
            0,
            int(
                setting(
                    "free_credits",
                    "10"
                )
            )
        )

    except (
        ValueError,
        TypeError
    ):

        credits = 10

    c = db()

    try:

        c.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                credits
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                generate_password_hash(
                    password
                ),
                credits
            )
        )

        c.commit()

        user = c.execute(
            """
            SELECT
                id,
                name,
                is_admin
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

    except sqlite3.IntegrityError:

        c.close()

        return jsonify(
            error="الإيميل مستخدم قبل كده."
        ), 409

    c.close()

    session.clear()

    session.update(
        uid=user["id"],
        name=user["name"],
        admin=bool(
            user["is_admin"]
        )
    )

    return jsonify(
        ok=True
    )


# =========================================================
# تسجيل الدخول
# =========================================================

@app.post("/api/login")
def api_login():

    data = request.get_json(
        silent=True
    ) or {}

    email = str(
        data.get(
            "email",
            ""
        )
    ).strip().lower()

    password = str(
        data.get(
            "password",
            ""
        )
    )

    c = db()

    user = c.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    if user["is_banned"]:

        c.close()

        return jsonify(
            error="حسابك موقوف. راجع الإدارة."
        ), 403

    valid, legacy_password = verify_password(
        user["password"],
        password
    )

    if not valid:

        c.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    if legacy_password:

        c.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (
                generate_password_hash(
                    password
                ),
                user["id"]
            )
        )

        c.commit()

    c.close()

    session.clear()

    session.update(
        uid=user["id"],
        name=user["name"],
        admin=bool(
            user["is_admin"]
        )
    )

    return jsonify(
        ok=True
    )


# =========================================================
# المستخدم الحالي
# =========================================================

@app.get("/api/me")
def me():

    if not session.get("uid"):

        return jsonify(
            logged_in=False
        )

    c = db()

    user = c.execute(
        """
        SELECT
            id,
            name,
            email,
            credits,
            is_admin,
            is_banned
        FROM users
        WHERE id = ?
        """,
        (session["uid"],)
    ).fetchone()

    c.close()

    if not user or user["is_banned"]:

        session.clear()

        return jsonify(
            logged_in=False
        )

    return jsonify(
        logged_in=True,
        **dict(user)
    )


# =========================================================
# الذكاء الاصطناعي - Gemini
# =========================================================

@app.post("/api/chat")
@login_required
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    if not message:

        return jsonify(
            error="اكتب رسالتك أولاً."
        ), 400

    if len(message) > 12000:

        return jsonify(
            error="الرسالة طويلة شديد. اختصرها وجرب تاني."
        ), 400

    if setting(
        "maintenance",
        "false"
    ).lower() == "true":

        return jsonify(
            error="الموقع تحت الصيانة حالياً. جرب بعد شوية."
        ), 503

    c = db()

    user = c.execute(
        """
        SELECT credits
        FROM users
        WHERE id = ?
        """,
        (session["uid"],)
    ).fetchone()

    if not user:

        c.close()

        session.clear()

        return jsonify(
            error="سجل دخولك من جديد."
        ), 401

    if user["credits"] <= 0:

        c.close()

        return jsonify(
            error="رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"
        ), 402

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:

        c.close()

        return jsonify(
            error="مفتاح الذكاء الاصطناعي ما مضاف في إعدادات الاستضافة."
        ), 503

    try:

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key
        )

        # -------------------------------------------------
        # الموديل
        # -------------------------------------------------

        model = setting(
            "ai_model",
            os.getenv(
                "GEMINI_MODEL",
                "gemini-3.8-flash"
            )
        ).strip()

        # حماية من وجود الموديل القديم في الإعدادات
        if (
            not model
            or model == "gemini-2.5-flash"
        ):

            model = "gemini-3.8-flash"

        # -------------------------------------------------
        # جلب آخر رسائل المحادثة
        # -------------------------------------------------

        previous = c.execute(
            """
            SELECT
                role,
                content
            FROM chats
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 12
            """,
            (session["uid"],)
        ).fetchall()

        history = []

        for item in reversed(previous):

            role = (
                "user"
                if item["role"] == "user"
                else "model"
            )

            history.append(
                types.Content(
                    role=role,
                    parts=[
                        types.Part.from_text(
                            text=item["content"]
                        )
                    ]
                )
            )

        # -------------------------------------------------
        # الرسالة الجديدة
        # -------------------------------------------------

        history.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=message
                    )
                ]
            )
        )

        # -------------------------------------------------
        # طلب Gemini
        #
        # مهم:
        # لا نستخدم temperature مع Gemini 3.8 Flash
        # -------------------------------------------------

        response = client.models.generate_content(
            model=model,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "أنت زولك AI، مساعد ذكاء اصطناعي سوداني ودود. "
                    "أجب بوضوح ودقة. استخدم اللهجة السودانية عندما "
                    "يطلبها المستخدم أو عندما يكون ذلك مناسباً. "
                    "لا تدّعي أنك إنسان. إذا لم تعرف الإجابة فقل "
                    "ذلك بوضوح. لا تخترع معلومات."
                )
            )
        )

        # -------------------------------------------------
        # استخراج الرد
        # -------------------------------------------------

        answer = (
            response.text or ""
        ).strip()

        if not answer:

            c.close()

            return jsonify(
                error="ما قدرنا نستخرج رد من خدمة الذكاء الاصطناعي. جرّب تاني."
            ), 502

        # -------------------------------------------------
        # خصم الرصيد فقط بعد نجاح الرد
        # -------------------------------------------------

        result = c.execute(
            """
            UPDATE users
            SET credits = credits - 1
            WHERE id = ?
            AND credits > 0
            """,
            (session["uid"],)
        )

        if result.rowcount != 1:

            c.rollback()
            c.close()

            return jsonify(
                error="رصيدك ما كفاية لإرسال رسالة جديدة."
            ), 402

        # -------------------------------------------------
        # حفظ رسالة المستخدم
        # -------------------------------------------------

        c.execute(
            """
            INSERT INTO chats
            (
                user_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                session["uid"],
                "user",
                message
            )
        )

        # -------------------------------------------------
        # حفظ رد الذكاء الاصطناعي
        # -------------------------------------------------

        c.execute(
            """
            INSERT INTO chats
            (
                user_id,
                role,
                content
            )
            VALUES (?, ?, ?)
            """,
            (
                session["uid"],
                "assistant",
                answer
            )
        )

        c.commit()
        c.close()

        return jsonify(
            answer=answer
        )

    except Exception as error:

        try:
            c.rollback()
        except Exception:
            pass

        try:
            c.close()
        except Exception:
            pass

        # تسجيل الخطأ الحقيقي في Faable Logs
        app.logger.exception(
            "AI response failed: %s",
            str(error)
        )

        return jsonify(
            error="حصلت مشكلة في خدمة الذكاء الاصطناعي. جرّب تاني."
        ), 500


# =========================================================
# المحادثات
# =========================================================

@app.get("/api/chats")
@login_required
def chats():

    c = db()

    rows = c.execute(
        """
        SELECT
            role,
            content,
            created_at
        FROM chats
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (session["uid"],)
    ).fetchall()

    c.close()

    return jsonify(
        chats=[
            dict(row)
            for row in reversed(rows)
        ]
    )


# =========================================================
# إحصائيات لوحة الإدارة
# =========================================================

@app.get("/api/admin/stats")
@admin_required
def admin_stats():

    c = db()

    total_users = c.execute(
        """
        SELECT COUNT(*) AS n
        FROM users
        """
    ).fetchone()["n"]

    total_messages = c.execute(
        """
        SELECT COUNT(*) AS n
        FROM chats
        """
    ).fetchone()["n"]

    banned_users = c.execute(
        """
        SELECT COUNT(*) AS n
        FROM users
        WHERE is_banned = 1
        """
    ).fetchone()["n"]

    total_credits = c.execute(
        """
        SELECT COALESCE(
            SUM(credits),
            0
        ) AS n
        FROM users
        """
    ).fetchone()["n"]

    c.close()

    return jsonify(
        total_users=total_users,
        total_messages=total_messages,
        banned_users=banned_users,
        total_credits=total_credits
    )


# =========================================================
# إعدادات الموقع
# =========================================================

@app.get("/api/admin/settings")
@admin_required
def get_admin_settings():

    c = db()

    rows = c.execute(
        """
        SELECT
            key,
            value
        FROM settings
        """
    ).fetchall()

    c.close()

    return jsonify(
        settings={
            row["key"]: row["value"]
            for row in rows
        }
    )


@app.post("/api/admin/settings")
