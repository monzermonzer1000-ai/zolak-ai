import os
import sqlite3
import io
import time
from functools import wraps
from datetime import datetime, timezone

from flask import (
    Flask, render_template, request, jsonify, session,
    redirect, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-in-production")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() == "true",
    MAX_CONTENT_LENGTH=15 * 1024 * 1024
)

DB = os.getenv("DATABASE_PATH", "zolak.db")


# =========================================================
# قاعدة البيانات
# =========================================================

def db():
    connection = sqlite3.connect(DB, timeout=20)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
    # إضافة الأعمدة الناقصة في قواعد البيانات القديمة
    # -----------------------------------------

    user_columns = {
        row["name"]
        for row in c.execute("PRAGMA table_info(users)").fetchall()
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
        ("site_name", "زولك AI 🇸🇩"),
        ("free_credits", "10"),
        ("welcome", "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة."),
        ("maintenance", "false"),
        ("allow_register", "true"),
        ("ai_model", os.getenv("GEMINI_MODEL", "gemini-2.5-flash")),
    ]

    for key, value in defaults:
        c.execute(
            """
            INSERT OR IGNORE INTO settings(key, value)
            VALUES(?, ?)
            """,
            (key, value)
        )

    # =====================================================
    # إنشاء / إصلاح حساب المدير
    # =====================================================
    #
    # البيانات الافتراضية:
    # البريد: admin@zolak.ai
    # كلمة السر: admin123
    #
    # ويمكن تغييرها من متغيرات البيئة إذا كانت موجودة.
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

        # إنشاء المدير إذا لم يكن موجوداً
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
                admin_email,
                generate_password_hash(admin_password),
                999999
            )
        )

    else:

        # إصلاح الحساب الموجود:
        # - مدير
        # - غير موقوف
        # - كلمة المرور تصبح admin123
        # - الرصيد كبير
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
                generate_password_hash(admin_password),
                admin_email
            )
        )

    c.commit()
    c.close()


def setting(key, default=""):
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

    return result["value"] if result else default


def save_setting(c, key, value):
    c.execute(
        """
        INSERT INTO settings(key, value)
        VALUES(?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (str(key), str(value))
    )


init_db()


# =========================================================
# تسجيل الدخول والصلاحيات
# =========================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

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

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

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

        return fn(*args, **kwargs)

    return wrapper


def verify_password(stored_password, entered_password):

    try:

        if check_password_hash(
            stored_password,
            entered_password
        ):
            return True, False

    except (ValueError, TypeError):

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
        data.get("name", "")
    ).strip()

    email = str(
        data.get("email", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
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
                generate_password_hash(password),
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
        data.get("email", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
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
                generate_password_hash(password),
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
# الذكاء الاصطناعي
# =========================================================

@app.post("/api/chat")
@login_required
def chat():

    data = request.get_json(
        silent=True
    ) or {}

    message = str(
        data.get("message", "")
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

        model = setting(
            "ai_model",
            os.getenv(
                "GEMINI_MODEL",
                "gemini-2.5-flash"
            )
        )

        previous = c.execute(
            """
            SELECT role, content
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

        answer = (
            response.text or ""
        ).strip()

        if not answer:

            c.close()

            return jsonify(
                error="ما قدرنا نستخرج رد من الخدمة. جرّب تاني."
            ), 502

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

    except Exception:

        c.close()

        app.logger.exception(
            "AI response failed"
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
        SELECT key, value
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
@admin_required
def admin_settings():

    data = request.get_json(
        silent=True
    ) or {}

    if not isinstance(data, dict):

        return jsonify(
            error="صيغة الإعدادات غير صحيحة."
        ), 400

    allowed = {
        "site_name",
        "free_credits",
        "welcome",
        "maintenance",
        "allow_register",
        "ai_model",
        "site_description",
        "homepage_title",
        "homepage_text",
        "primary_color",
        "theme",
        "support_email",
        "announcement",
        "enable_history",
        "enable_registration",
        "max_message_length"
    }

    c = db()

    for key, value in data.items():

        if key not in allowed:
            continue

        if key == "free_credits":

            try:

                value = max(
                    0,
                    min(
                        100000,
                        int(value)
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                c.close()

                return jsonify(
                    error="قيمة الرصيد المجاني غير صحيحة."
                ), 400

        if isinstance(
            value,
            (dict, list)
        ):

            c.close()

            return jsonify(
                error="قيمة أحد الإعدادات غير صحيحة."
            ), 400

        value = str(value)[:2000]

        save_setting(
            c,
            key,
            value
        )

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        message="تم حفظ الإعدادات."
    )


# =========================================================
# إدارة المستخدمين
# =========================================================

@app.get("/api/admin/users")
@admin_required
def admin_users():

    search = str(
        request.args.get(
            "q",
            ""
        )
    ).strip()[:100]

    c = db()

    if search:

        pattern = f"%{search}%"

        rows = c.execute(
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
            WHERE name LIKE ?
            OR email LIKE ?
            ORDER BY id DESC
            LIMIT 300
            """,
            (
                pattern,
                pattern
            )
        ).fetchall()

    else:

        rows = c.execute(
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
            LIMIT 300
            """
        ).fetchall()

    c.close()

    users = [
        dict(row)
        for row in rows
    ]

    return jsonify(
        users=users,
        total=len(users)
    )


@app.post("/api/admin/user/<int:uid>/credits")
@admin_required
def add_credits(uid):

    data = request.get_json(
        silent=True
    ) or {}

    try:

        amount = int(
            data.get(
                "amount",
                10
            )
        )

    except (
        ValueError,
        TypeError
    ):

        return jsonify(
            error="عدد الرصيد غير صحيح."
        ), 400

    if amount < 0 or amount > 100000:

        return jsonify(
            error="قيمة الرصيد خارج الحدود المسموحة."
        ), 400

    c = db()

    result = c.execute(
        """
        UPDATE users
        SET credits = credits + ?
        WHERE id = ?
        """,
        (
            amount,
            uid
        )
    )

    c.commit()
    c.close()

    if result.rowcount != 1:

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    return jsonify(
        ok=True,
        message="تمت إضافة الرصيد."
    )


@app.patch("/api/admin/user/<int:uid>")
@admin_required
def update_user(uid):

    data = request.get_json(
        silent=True
    ) or {}

    c = db()

    user = c.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
        """,
        (uid,)
    ).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    if "name" in data:

        name = str(
            data["name"]
        ).strip()[:100]

        if not name:

            c.close()

            return jsonify(
                error="اسم المستخدم مطلوب."
            ), 400

        c.execute(
            """
            UPDATE users
            SET name = ?
            WHERE id = ?
            """,
            (
                name,
                uid
            )
        )

    if "credits" in data:

        try:

            credits = max(
                0,
                min(
                    1000000,
                    int(data["credits"])
                )
            )

        except (
            ValueError,
            TypeError
        ):

            c.close()

            return jsonify(
                error="قيمة الرصيد غير صحيحة."
            ), 400

        c.execute(
            """
            UPDATE users
            SET credits = ?
            WHERE id = ?
            """,
            (
                credits,
                uid
            )
        )

    if "is_banned" in data:

        banned = (
            1
            if str(
                data["is_banned"]
            ).lower()
            in (
                "1",
                "true",
                "yes",
                "on"
            )
            else 0
        )

        c.execute(
            """
            UPDATE users
            SET is_banned = ?
            WHERE id = ?
            """,
            (
                banned,
                uid
            )
        )

    if "is_admin" in data:

        if uid == session.get("uid"):

            c.close()

            return jsonify(
                error="ما ممكن تعدل صلاحيات حسابك الحالي."
            ), 400

        admin_value = (
            1
            if str(
                data["is_admin"]
            ).lower()
            in (
                "1",
                "true",
                "yes",
                "on"
            )
            else 0
        )

        c.execute(
            """
            UPDATE users
            SET is_admin = ?
            WHERE id = ?
            """,
            (
                admin_value,
                uid
            )
        )

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        message="تم تحديث المستخدم."
    )


@app.post("/api/admin/user/<int:uid>/ban")
@admin_required
def ban_user(uid):

    if uid == session.get("uid"):

        return jsonify(
            error="ما ممكن توقف حسابك الحالي."
        ), 400

    data = request.get_json(
        silent=True
    ) or {}

    banned = data.get(
        "banned",
        True
    )

    banned = (
        1
        if str(banned).lower()
        in (
            "1",
            "true",
            "yes",
            "on"
        )
        else 0
    )

    c = db()

    result = c.execute(
        """
        UPDATE users
        SET is_banned = ?
        WHERE id = ?
        """,
        (
            banned,
            uid
        )
    )

    c.commit()
    c.close()

    if result.rowcount != 1:

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    return jsonify(
        ok=True
    )


@app.delete("/api/admin/user/<int:uid>")
@admin_required
def delete_user(uid):

    if uid == session.get("uid"):

        return jsonify(
            error="ما ممكن تحذف حسابك الحالي."
        ), 400

    c = db()

    result = c.execute(
        """
        DELETE FROM users
        WHERE id = ?
        """,
        (uid,)
    )

    c.commit()
    c.close()

    if result.rowcount != 1:

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    return jsonify(
        ok=True,
        message="تم حذف المستخدم."
    )


# =========================================================
# فحص صحة الموقع
# =========================================================

@app.get("/api/admin/health")
@admin_required
def admin_health():

    checks = []

    # قاعدة البيانات
    try:

        c = db()

        c.execute(
            "SELECT 1"
        ).fetchone()

        c.close()

        checks.append({
            "name": "قاعدة البيانات",
            "status": "ok",
            "message": "الاتصال بقاعدة البيانات يعمل."
        })

    except Exception as error:

        checks.append({
            "name": "قاعدة البيانات",
            "status": "error",
            "message": str(error)[:250]
        })

    # مفتاح الذكاء الاصطناعي
    if os.getenv("GEMINI_API_KEY"):

        checks.append({
            "name": "مفتاح الذكاء الاصطناعي",
            "status": "ok",
            "message": "مفتاح Gemini موجود في متغيرات الاستضافة."
        })

    else:

        checks.append({
            "name": "مفتاح الذكاء الاصطناعي",
            "status": "warning",
            "message": "لم تتم إضافة GEMINI_API_KEY."
        })

    # مسار قاعدة البيانات
    db_directory = os.path.dirname(
        os.path.abspath(DB)
    )

    if (
        os.path.isdir(db_directory)
        and os.access(
            db_directory,
            os.W_OK
        )
    ):

        checks.append({
            "name": "مسار التخزين",
            "status": "ok",
            "message": "مسار قاعدة البيانات قابل للكتابة."
        })

    else:

        checks.append({
            "name": "مسار التخزين",
            "status": "error",
            "message": "مسار قاعدة البيانات غير قابل للكتابة."
        })

    statuses = [
        item["status"]
        for item in checks
    ]

    if "error" in statuses:
        overall = "error"

    elif "warning" in statuses:
        overall = "warning"

    else:
        overall = "ok"

    return jsonify(
        checks=checks,
        overall_status=overall,
        checked_at=datetime.now(
            timezone.utc
        ).isoformat(),
        db_path=os.path.abspath(DB)
    )


# =========================================================
# النسخ الاحتياطي
# =========================================================

@app.get("/api/admin/backup")
@admin_required
def download_backup():

    try:

        c = db()

        c.execute(
            "PRAGMA wal_checkpoint(FULL)"
        )

        c.close()

        with open(
            DB,
            "rb"
        ) as backup_file:

            data = backup_file.read()

        filename = (
            "zolak-backup-"
            + time.strftime(
                "%Y%m%d-%H%M%S"
            )
            + ".db"
        )

        return send_file(
            io.BytesIO(data),
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name=filename
        )

    except Exception:

        app.logger.exception(
            "Backup failed"
        )

        return jsonify(
            error="تعذر إنشاء النسخة الاحتياطية."
        ), 500


@app.get("/api/admin/backup/download")
@admin_required
def download_backup_alias():

    return download_backup()


# =========================================================
# فحص بسيط للموقع
# =========================================================

@app.get("/health")
def health():

    try:

        c = db()

        c.execute(
            "SELECT 1"
        ).fetchone()

        c.close()

        return jsonify(
            status="ok"
        )

    except Exception:

        app.logger.exception(
            "Health endpoint failed"
        )

        return jsonify(
            status="error"
        ), 500


# =========================================================
# تشغيل التطبيق
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        )
)
