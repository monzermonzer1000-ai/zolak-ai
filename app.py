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

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            gemini_interaction_id TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

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

    if "gemini_interaction_id" not in user_columns:

        c.execute("""
            ALTER TABLE users
            ADD COLUMN gemini_interaction_id TEXT
        """)

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
            "gemini-3.8-flash"
        ),
    ]

    for key, value in defaults:

        c.execute(
            """
            INSERT OR IGNORE INTO settings
            (key, value)
            VALUES (?, ?)
            """,
            (
                key,
                value
            )
        )

    # -----------------------------------------------------
    # المدير
    # -----------------------------------------------------

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
                admin_email,
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

    # -----------------------------------------------------
    # إصلاح أي إعداد قديم
    # -----------------------------------------------------

    c.execute(
        """
        UPDATE settings
        SET value = 'gemini-3.8-flash'
        WHERE key = 'ai_model'
        AND value = 'gemini-2.5-flash'
        """
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

    if result:
        return result["value"]

    return default


def save_setting(c, key, value):

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
# الصلاحيات
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

    if stored_password == entered_password:

        return True, True

    return False, False


# =========================================================
# الصفحات
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


@app.get("/logout")
def logout():

    session.clear()

    return redirect("/")


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

    if len(name) > 100 or len(email) > 200:

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
            SELECT id, name, is_admin
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

    return jsonify(ok=True)


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

    return jsonify(ok=True)


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
# الذكاء الاصطناعي - Gemini Interactions API
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
        SELECT
            credits,
            gemini_interaction_id
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

        client = genai.Client(
            api_key=api_key
        )

        # -------------------------------------------------
        # الموديل
        # -------------------------------------------------

        model = setting(
            "ai_model",
            "gemini-3.8-flash"
        ).strip()

        # منع أي موديل قديم
        if (
            not model
            or model == "gemini-2.5-flash"
        ):

            model = "gemini-3.8-flash"

        # -------------------------------------------------
        # التعليمات
        # -------------------------------------------------

        system_instruction = (
            "أنت زولك AI، مساعد ذكاء اصطناعي سوداني ودود. "
            "أجب بوضوح ودقة. "
            "استخدم اللهجة السودانية عندما يطلبها المستخدم "
            "أو عندما يكون ذلك مناسباً. "
            "لا تدّعي أنك إنسان. "
            "إذا لم تعرف الإجابة فقل ذلك بوضوح. "
            "لا تخترع معلومات."
        )

        # -------------------------------------------------
        # استكمال المحادثة السابقة
        # -------------------------------------------------

        previous_interaction_id = (
            user["gemini_interaction_id"]
        )

        kwargs = {
            "model": model,
            "input": message,
            "system_instruction": system_instruction
        }

        if previous_interaction_id:

            kwargs[
                "previous_interaction_id"
            ] = previous_interaction_id

        # -------------------------------------------------
        # الطلب
        # -------------------------------------------------

        interaction = client.interactions.create(
            **kwargs
        )

        answer = (
            interaction.output_text or ""
        ).strip()

        if not answer:

            c.close()

            return jsonify(
                error="ما قدرنا نستخرج رد من الذكاء الاصطناعي. جرّب تاني."
            ), 502

        # -------------------------------------------------
        # حفظ Interaction ID
        # -------------------------------------------------

        interaction_id = getattr(
            interaction,
            "id",
            None
        )

        if interaction_id:

            c.execute(
                """
                UPDATE users
                SET gemini_interaction_id = ?
                WHERE id = ?
                """,
                (
                    interaction_id,
                    session["uid"]
                )
            )

        # -------------------------------------------------
        # خصم الرصيد
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
        # حفظ الرسائل
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

        error_text = str(error)

        app.logger.exception(
            "AI response failed: %s",
            error_text
        )

        # -------------------------------------------------
        # Gemini 503
        # -------------------------------------------------

        if (
            "503" in error_text
            or "UNAVAILABLE" in error_text
            or "high demand" in error_text.lower()
        ):

            return jsonify(
                error=(
                    "خدمة الذكاء الاصطناعي عليها ضغط حالياً. "
                    "جرّب تاني بعد شوية."
                )
            ), 503

        # -------------------------------------------------
        # موديل قديم
        # -------------------------------------------------

        if "gemini-2.5-flash" in error_text:

            return jsonify(
                error=(
                    "إعداد موديل قديم موجود في الخدمة. "
                    "تم اكتشاف المشكلة، جرّب بعد إعادة تشغيل الموقع."
                )
            ), 503

        return jsonify(
            error="حصلت مشكلة في خدمة الذكاء الاصطناعي. جرّب تاني."
        ), 500


# =========================================================
# بدء محادثة جديدة
# =========================================================

@app.post("/api/chat/new")
@login_required
def new_chat():

    c = db()

    c.execute(
        """
        UPDATE users
        SET gemini_interaction_id = NULL
        WHERE id = ?
        """,
        (session["uid"],)
    )

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


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
# إحصائيات الإدارة
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
# إعدادات الإدارة
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
def update_admin_settings():

    data = request.get_json(
        silent=True
    ) or {}

    c = db()

    allowed = {
        "site_name",
        "free_credits",
        "welcome",
        "maintenance",
        "allow_register",
        "ai_model"
    }

    for key, value in data.items():

        if key not in allowed:
            continue

        value = str(value)

        if key == "ai_model":

            if (
                not value.strip()
                or value.strip()
                == "gemini-2.5-flash"
            ):

                value = "gemini-3.8-flash"

        save_setting(
            c,
            key,
            value
        )

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================================================
# المستخدمين - الإدارة
# =========================================================

@app.get("/api/admin/users")
@admin_required
def admin_users():

    query = str(
        request.args.get(
            "q",
            ""
        )
    ).strip()

    c = db()

    if query:

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
            WHERE
                name LIKE ?
                OR email LIKE ?
            ORDER BY id DESC
            LIMIT 100
            """,
            (
                f"%{query}%",
                f"%{query}%"
            )
        ).fetchall()

    else:

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

    c.close()

    return jsonify(
        users=[
            dict(user)
            for user in users
        ]
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
                0
            )
        )

    except (
        ValueError,
        TypeError
    ):

        amount = 0

    if amount == 0:

        return jsonify(
            error="أدخل عدد صحيح."
        ), 400

    c = db()

    result = c.execute(
        """
        UPDATE users
        SET credits = MAX(
            0,
            credits + ?
        )
        WHERE id = ?
        """,
        (
            amount,
            uid
        )
    )

    c.commit()

    user = c.execute(
        """
        SELECT credits
        FROM users
        WHERE id = ?
        """,
        (uid,)
    ).fetchone()

    c.close()

    if result.rowcount != 1:

        return jsonify(
            error="المستخدم ما موجود."
        ), 404

    return jsonify(
        ok=True,
        credits=user["credits"]
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
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (uid,)
    ).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم ما موجود."
        ), 404

    if "name" in data:

        name = str(
            data["name"]
        ).strip()

        if name:

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

    if "email" in data:

        email = str(
            data["email"]
        ).strip().lower()

        if email:

            try:

                c.execute(
                    """
                    UPDATE users
                    SET email = ?
                    WHERE id = ?
                    """,
                    (
                        email,
                        uid
                    )
                )

            except sqlite3.IntegrityError:

                c.close()

                return jsonify(
                    error="الإيميل مستخدم قبل كده."
                ), 409

    if "credits" in data:

        try:

            credits = max(
                0,
                int(data["credits"])
            )

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

        except (
            ValueError,
            TypeError
        ):

            pass

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


@app.post("/api/admin/user/<int:uid>/ban")
@admin_required
def ban_user(uid):

    c = db()

    c.execute(
        """
        UPDATE users
        SET is_banned = 1
        WHERE id = ?
        """,
        (uid,)
    )

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


@app.post("/api/admin/user/<int:uid>/unban")
@admin_required
def unban_user(uid):

    c = db()

    c.execute(
        """
        UPDATE users
        SET is_banned = 0
        WHERE id = ?
        """,
        (uid,)
    )

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


@app.delete("/api/admin/user/<int:uid>")
@admin_required
def delete_user(uid):

    if uid == session.get("uid"):

        return jsonify(
            error="ما ممكن تحذف حساب المدير الحالي."
        ), 400

    c = db()

    c.execute(
        """
        DELETE FROM users
        WHERE id = ?
        """,
        (uid,)
    )

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================================================
# الصحة
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

    except Exception as error:

        app.logger.exception(
            "Health check failed: %s",
            str(error)
        )

        return jsonify(
            status="error"
        ), 500


@app.get("/api/admin/health")
@admin_required
def admin_health():

    checks = {}

    # قاعدة البيانات
    try:

        c = db()

        c.execute(
            "SELECT 1"
        ).fetchone()

        c.close()

        checks["database"] = "ok"

    except Exception:

        checks["database"] = "error"

    # مفتاح Gemini
    checks["gemini_key"] = (
        "ok"
        if os.getenv("GEMINI_API_KEY")
        else "missing"
    )

    # الموديل
    model = setting(
        "ai_model",
        "gemini-3.8-flash"
    )

    if model == "gemini-2.5-flash":

        model = "gemini-3.8-flash"

    checks["ai_model"] = model

    return jsonify(
        status="ok",
        checks=checks
    )


# =========================================================
# النسخ الاحتياطي
# =========================================================

@app.get("/api/admin/backup")
@admin_required
def backup():

    c = db()

    users = [
        dict(row)
        for row in c.execute(
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
            """
        ).fetchall()
    ]

    chats_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT
                id,
                user_id,
                role,
                content,
                created_at
            FROM chats
            """
        ).fetchall()
    ]

    settings_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT key, value
            FROM settings
            """
        ).fetchall()
    ]

    c.close()

    return jsonify(
        users=users,
        chats=chats_data,
        settings=settings_data
    )


@app.get("/api/admin/backup/download")
@admin_required
def backup_download():

    c = db()

    users = [
        dict(row)
        for row in c.execute(
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
            """
        ).fetchall()
    ]

    chats_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT
                id,
                user_id,
                role,
                content,
                created_at
            FROM chats
            """
        ).fetchall()
    ]

    settings_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT key, value
            FROM settings
            """
        ).fetchall()
    ]

    c.close()

    import json

    backup_data = {
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "users": users,
        "chats": chats_data,
        "settings": settings_data
    }

    raw = json.dumps(
        backup_data,
        ensure_ascii=False,
        indent=2
    ).encode("utf-8")

    return send_file(
        io.BytesIO(raw),
        mimetype="application/json",
        as_attachment=True,
        download_name="zolak-ai-backup.json"
    )


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
        ),
        debug=False
        )
