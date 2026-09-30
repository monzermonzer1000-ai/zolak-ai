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
    send_file,
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
        "false"
    ).lower() == "true",
    MAX_CONTENT_LENGTH=15 * 1024 * 1024,
)

DB_PATH = os.getenv("DB_PATH", "zolak.db")


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def column_exists(conn, table_name, column_name):
    rows = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(row["name"] == column_name for row in rows)


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
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
        """
    )

    cur.execute(
        """
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
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    # Migrations for older databases
    if not column_exists(conn, "users", "is_banned"):
        cur.execute(
            "ALTER TABLE users ADD COLUMN is_banned INTEGER NOT NULL DEFAULT 0"
        )

    if not column_exists(conn, "users", "created_at"):
        cur.execute(
            "ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"
        )

    if not column_exists(conn, "users", "gemini_interaction_id"):
        cur.execute(
            "ALTER TABLE users ADD COLUMN gemini_interaction_id TEXT"
        )

    defaults = {
        "site_name": "زولك AI",
        "welcome_message": "مرحب بيك في زولك AI 🇸🇩",
        "free_credits": "10",
        "ai_model": "gemini-3.8-flash",
        "site_description": (
            "مساعد ذكاء اصطناعي سوداني يساعدك في الكتابة "
            "والدراسة والترجمة والشغل والدردشة 🇸🇩🤖"
        ),
    }

    for key, value in defaults.items():
        cur.execute(
            """
            INSERT OR IGNORE INTO settings (key, value)
            VALUES (?, ?)
            """,
            (key, value),
        )

    conn.commit()

    # Create admin if ADMIN_EMAIL and ADMIN_PASSWORD exist
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_name = os.getenv("ADMIN_NAME", "مدير زولك")

    if admin_email and admin_password:
        existing_admin = cur.execute(
            "SELECT id FROM users WHERE email = ?",
            (admin_email,),
        ).fetchone()

        if not existing_admin:
            cur.execute(
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
                    999999,
                ),
            )

            conn.commit()

    conn.close()


init_db()


# =========================================================
# SETTINGS
# =========================================================

def get_setting(key, default=None):
    conn = get_db()

    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?",
        (key,),
    ).fetchone()

    conn.close()

    if row is None:
        return default

    return row["value"]


def set_setting(key, value):
    conn = get_db()

    conn.execute(
        """
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
        """,
        (key, str(value)),
    )

    conn.commit()
    conn.close()


# =========================================================
# AUTH
# =========================================================

def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user:
            return jsonify(
                {
                    "error": "لازم تسجل دخول أول."
                }
            ), 401

        if user["is_banned"]:
            session.clear()

            return jsonify(
                {
                    "error": "حسابك محظور حالياً."
                }
            ), 403

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user:
            return redirect("/login")

        if not user["is_admin"]:
            return redirect("/")

        return fn(*args, **kwargs)

    return wrapper


def admin_api_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user:
            return jsonify(
                {
                    "error": "غير مسجل دخول."
                }
            ), 401

        if not user["is_admin"]:
            return jsonify(
                {
                    "error": "ما عندك صلاحية."
                }
            ), 403

        return fn(*args, **kwargs)

    return wrapper


# =========================================================
# PAGES
# =========================================================

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/login")
def login_page():
    return render_template("login.html")


@app.get("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect("/")


# =========================================================
# AUTH API
# =========================================================

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or not email or not password:
        return jsonify(
            {
                "error": "أدخل الاسم والإيميل وكلمة السر."
            }
        ), 400

    if len(name) < 2:
        return jsonify(
            {
                "error": "الاسم قصير شديد."
            }
        ), 400

    if len(password) < 6:
        return jsonify(
            {
                "error": "كلمة السر لازم تكون 6 أحرف على الأقل."
            }
        ), 400

    conn = get_db()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if existing:
        conn.close()

        return jsonify(
            {
                "error": "الإيميل مسجل من قبل."
            }
        ), 409

    try:
        free_credits = int(
            get_setting("free_credits", "10")
        )
    except Exception:
        free_credits = 10

    cur = conn.execute(
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
            max(0, free_credits),
        ),
    )

    user_id = cur.lastrowid

    conn.commit()
    conn.close()

    session["user_id"] = user_id

    return jsonify(
        {
            "success": True,
            "message": "تم إنشاء حسابك بنجاح.",
        }
    )


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify(
            {
                "error": "أدخل الإيميل وكلمة السر."
            }
        ), 400

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    conn.close()

    if not user:
        return jsonify(
            {
                "error": "الإيميل أو كلمة السر غلط."
            }
        ), 401

    if not check_password_hash(
        user["password"],
        password
    ):
        return jsonify(
            {
                "error": "الإيميل أو كلمة السر غلط."
            }
        ), 401

    if user["is_banned"]:
        return jsonify(
            {
                "error": "الحساب محظور حالياً."
            }
        ), 403

    session["user_id"] = user["id"]

    return jsonify(
        {
            "success": True,
            "message": "تم تسجيل الدخول.",
        }
    )


@app.get("/api/me")
def me():
    user = current_user()

    if not user:
        return jsonify(
            {
                "logged_in": False
            }
        )

    return jsonify(
        {
            "logged_in": True,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "credits": user["credits"],
                "is_admin": bool(user["is_admin"]),
                "is_banned": bool(user["is_banned"]),
            },
        }
    )


# =========================================================
# GEMINI
# =========================================================

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY غير موجود في متغيرات البيئة."
        )

    from google import genai

    # زيادة المهلة إلى 120 ثانية
    return genai.Client(
        api_key=api_key,
        http_options={
            "timeout": 120000
        },
    )


def get_ai_model():
    model = get_setting(
        "ai_model",
        os.getenv(
            "GEMINI_MODEL",
            "gemini-3.8-flash"
        ),
    )

    model = str(model or "").strip()

    if model.startswith("models/"):
        model = model[len("models/"):]

    # منع الرجوع للموديل القديم
    if model == "gemini-2.5-flash":
        model = "gemini-3.8-flash"

    if not model:
        model = "gemini-3.8-flash"

    return model


AI_SYSTEM_INSTRUCTION = """
أنت زولك AI 🇸🇩، مساعد ذكاء اصطناعي سوداني.

اتكلم مع المستخدم بطريقة واضحة وطبيعية.
استخدم اللهجة السودانية عندما تكون مناسبة.
لا تتصنع اللهجة بصورة مبالغ فيها.
كن مفيداً ومختصراً ومباشراً.
إذا كان السؤال يحتاج شرحاً، اشرح بطريقة سهلة.
لا تدعي أنك إنسان.
لا تخترع معلومات غير متأكد منها.
"""


@app.post("/api/chat")
@login_required
def chat():
    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    if not message:
        return jsonify(
            {
                "error": "اكتب رسالتك أول."
            }
        ), 400

    if len(message) > 20000:
        return jsonify(
            {
                "error": "الرسالة طويلة شديد."
            }
        ), 400

    user = current_user()

    if not user:
        return jsonify(
            {
                "error": "سجل دخول أول."
            }
        ), 401

    if user["credits"] <= 0:
        return jsonify(
            {
                "error": "رصيدك خلص. محتاج رصيد عشان تواصل."
            }
        ), 402

    try:
        client = get_gemini_client()
        model = get_ai_model()

        previous_interaction_id = user["gemini_interaction_id"]

        create_kwargs = {
            "model": model,
            "input": message,
            "system_instruction": AI_SYSTEM_INSTRUCTION,
        }

        if previous_interaction_id:
            create_kwargs[
                "previous_interaction_id"
            ] = previous_interaction_id

        try:
            interaction = client.interactions.create(
                **create_kwargs
            )

        except Exception as first_error:
            error_text = str(first_error).lower()

            # إذا كان الـ interaction القديم غير صالح،
            # نبدأ Interaction جديد.
            stale_interaction = (
                "not found" in error_text
                or "invalid" in error_text
                or "previous_interaction" in error_text
            )

            if stale_interaction and previous_interaction_id:
                create_kwargs.pop(
                    "previous_interaction_id",
                    None
                )

                interaction = client.interactions.create(
                    **create_kwargs
                )

            else:
                raise

        answer = getattr(
            interaction,
            "output_text",
            None
        )

        if not answer:
            # محاولة قراءة output بطريقة احتياطية
            output = getattr(
                interaction,
                "output",
                None
            )

            if output:
                answer = str(output)

        answer = str(answer or "").strip()

        if not answer:
            return jsonify(
                {
                    "error": "الذكاء الاصطناعي ما رجّع رد. جرّب تاني."
                }
            ), 502

        interaction_id = getattr(
            interaction,
            "id",
            None
        )

        conn = get_db()

        # حفظ المحادثة
        conn.execute(
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
                user["id"],
                "user",
                message,
            ),
        )

        conn.execute(
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
                user["id"],
                "assistant",
                answer,
            ),
        )

        # خصم رصيد واحد فقط بعد نجاح الرد
        conn.execute(
            """
            UPDATE users
            SET
                credits = credits - 1,
                gemini_interaction_id = ?
            WHERE id = ?
            """,
            (
                interaction_id,
                user["id"],
            ),
        )

        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "answer": answer,
                "credits": max(
                    0,
                    user["credits"] - 1
                ),
            }
        )

    except Exception as exc:
        print(
            "GEMINI ERROR:",
            repr(exc),
            flush=True
        )

        error_text = str(exc).lower()

        if (
            "503" in error_text
            or "unavailable" in error_text
            or "high demand" in error_text
        ):
            return jsonify(
                {
                    "error": (
                        "خدمة الذكاء الاصطناعي مضغوطة حالياً. "
                        "جرّب تاني بعد شوية."
                    )
                }
            ), 503

        if (
            "404" in error_text
            or "not found" in error_text
        ):
            return jsonify(
                {
                    "error": (
                        "موديل الذكاء الاصطناعي غير متاح حالياً. "
                        "راجع إعدادات Gemini."
                    )
                }
            ), 502

        if (
            "401" in error_text
            or "403" in error_text
            or "api key" in error_text
            or "permission" in error_text
        ):
            return jsonify(
                {
                    "error": (
                        "مفتاح Gemini أو صلاحياته فيها مشكلة."
                    )
                }
            ), 502

        if (
            "timeout" in error_text
            or "timed out" in error_text
        ):
            return jsonify(
                {
                    "error": (
                        "الاتصال بخدمة الذكاء الاصطناعي "
                        "استغرق وقت طويل. جرّب تاني."
                    )
                }
            ), 504

        return jsonify(
            {
                "error": (
                    "حصلت مشكلة في خدمة الذكاء الاصطناعي. "
                    "جرّب تاني."
                )
            }
        ), 500


# =========================================================
# CHATS
# =========================================================

@app.get("/api/chats")
@login_required
def get_chats():
    user = current_user()

    conn = get_db()

    rows = conn.execute(
        """
        SELECT
            id,
            role,
            content,
            created_at
        FROM chats
        WHERE user_id = ?
        ORDER BY id ASC
        """,
        (user["id"],),
    ).fetchall()

    conn.close()

    chats = []

    for row in rows:
        chats.append(
            {
                "id": row["id"],
                "role": row["role"],
                "content": row["content"],
                "created_at": row["created_at"],
            }
        )

    return jsonify(
        {
            "success": True,
            "chats": chats,
        }
    )


# =========================================================
# ADMIN - STATS
# =========================================================

@app.get("/api/admin/stats")
@admin_api_required
def admin_stats():
    conn = get_db()

    total_users = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    total_chats = conn.execute(
        "SELECT COUNT(*) AS count FROM chats"
    ).fetchone()["count"]

    banned_users = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM users
        WHERE is_banned = 1
        """
    ).fetchone()["count"]

    total_credits = conn.execute(
        """
        SELECT COALESCE(SUM(credits), 0) AS total
        FROM users
        """
    ).fetchone()["total"]

    conn.close()

    return jsonify(
        {
            "success": True,
            "stats": {
                "users": total_users,
                "chats": total_chats,
                "banned": banned_users,
                "credits": total_credits,
            },
        }
    )


# =========================================================
# ADMIN - SETTINGS
# =========================================================

@app.get("/api/admin/settings")
@admin_api_required
def admin_get_settings():
    conn = get_db()

    rows = conn.execute(
        "SELECT key, value FROM settings"
    ).fetchall()

    conn.close()

    settings = {
        row["key"]: row["value"]
        for row in rows
    }

    return jsonify(
        {
            "success": True,
            "settings": settings,
        }
    )


@app.post("/api/admin/settings")
@admin_api_required
def admin_save_settings():
    data = request.get_json(silent=True) or {}

    allowed = {
        "site_name",
        "welcome_message",
        "free_credits",
        "ai_model",
        "site_description",
    }

    for key in allowed:
        if key not in data:
            continue

        value = data[key]

        if key == "ai_model":
            value = str(value).strip()

            if value.startswith("models/"):
                value = value[len("models/"):]

            if value == "gemini-2.5-flash":
                value = "gemini-3.8-flash"

        if key == "free_credits":
            try:
                value = max(0, int(value))
            except Exception:
                value = 10

        set_setting(key, value)

    return jsonify(
        {
            "success": True,
            "message": "تم حفظ الإعدادات.",
        }
    )


# =========================================================
# ADMIN - USERS
# =========================================================

@app.get("/api/admin/users")
@admin_api_required
def admin_users():
    query = str(
        request.args.get("q", "")
    ).strip()

    conn = get_db()

    if query:
        rows = conn.execute(
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
            """,
            (
                f"%{query}%",
                f"%{query}%",
            ),
        ).fetchall()
    else:
        rows = conn.execute(
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
            """
        ).fetchall()

    conn.close()

    users = []

    for row in rows:
        users.append(
            {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "credits": row["credits"],
                "is_admin": bool(row["is_admin"]),
                "is_banned": bool(row["is_banned"]),
                "created_at": row["created_at"],
            }
        )

    return jsonify(
        {
            "success": True,
            "users": users,
        }
    )


# =========================================================
# ADMIN - CREDITS
# =========================================================

@app.post("/api/admin/user/<int:uid>/credits")
@admin_api_required
def admin_add_credits(uid):
    data = request.get_json(silent=True) or {}

    amount = data.get("amount", 10)

    try:
        amount = int(amount)
    except Exception:
        return jsonify(
            {
                "error": "قيمة الرصيد غير صحيحة."
            }
        ), 400

    if amount <= 0:
        return jsonify(
            {
                "error": "الرصيد لازم يكون أكبر من صفر."
            }
        ), 400

    conn = get_db()

    user = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (uid,),
    ).fetchone()

    if not user:
        conn.close()

        return jsonify(
            {
                "error": "المستخدم غير موجود."
            }
        ), 404

    conn.execute(
        """
        UPDATE users
        SET credits = credits + ?
        WHERE id = ?
        """,
        (
            amount,
            uid,
        ),
    )

    conn.commit()

    new_balance = conn.execute(
        "SELECT credits FROM users WHERE id = ?",
        (uid,),
    ).fetchone()["credits"]

    conn.close()

    return jsonify(
        {
            "success": True,
            "credits": new_balance,
        }
    )


# =========================================================
# ADMIN - EDIT USER
# =========================================================

@app.patch("/api/admin/user/<int:uid>")
@admin_api_required
def admin_edit_user(uid):
    data = request.get_json(silent=True) or {}

    conn = get_db()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (uid,),
    ).fetchone()

    if not user:
        conn.close()

        return jsonify(
            {
                "error": "المستخدم غير موجود."
            }
        ), 404

    name = data.get("name")
    email = data.get("email")

    updates = []
    params = []

    if name is not None:
        name = str(name).strip()

        if not name:
            conn.close()

            return jsonify(
                {
                    "error": "الاسم ما ممكن يكون فاضي."
                }
            ), 400

        updates.append("name = ?")
        params.append(name)

    if email is not None:
        email = str(email).strip().lower()

        if not email:
            conn.close()

            return jsonify(
                {
                    "error": "الإيميل ما ممكن يكون فاضي."
                }
            ), 400

        other = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            AND id != ?
            """,
            (
                email,
                uid,
            ),
        ).fetchone()

        if other:
            conn.close()

            return jsonify(
                {
                    "error": "الإيميل مستخدم من حساب تاني."
                }
            ), 409

        updates.append("email =
