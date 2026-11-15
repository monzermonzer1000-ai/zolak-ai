import os
import sqlite3
import psycopg
import io
import time
import secrets
import hashlib
from urllib.parse import urlsplit
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
    Response,
    stream_with_context
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv(
        "COOKIE_SECURE",
        "true"
    ).lower() == "true",
    MAX_CONTENT_LENGTH=15 * 1024 * 1024
)


@app.before_request
def protect_state_changing_requests():
    """Reject cross-origin browser mutations while allowing non-browser API clients."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None

    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        return jsonify(error="تم رفض الطلب لأسباب أمنية."), 403

    source = request.headers.get("Origin", "").strip() or request.headers.get("Referer", "").strip()
    if source:
        try:
            parsed = urlsplit(source)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != request.host.lower():
                return jsonify(error="مصدر الطلب غير موثوق."), 403
        except ValueError:
            return jsonify(error="مصدر الطلب غير صالح."), 403

    return None


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=()")
    return response

DB = os.getenv(
    "DATABASE_PATH",
    "zolak.db"
)


# =========================================================
# قاعدة البيانات
# =========================================================

def db():
    database_url = os.getenv("DATABASE_URL", "").strip()

    if database_url:
        from db_adapter import connect_database
        return connect_database(database_url)

    # Vercel's deployment filesystem is read-only and ephemeral.
    # Never silently create a local SQLite database in production.
    if os.getenv("VERCEL") == "1":
        raise RuntimeError(
            "DATABASE_URL is missing. Configure the Supabase transaction-pooler URI in Vercel."
        )

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
            session_version INTEGER NOT NULL DEFAULT 0,
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
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'محادثة جديدة',
            gemini_interaction_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conversation_columns = {
        row["name"] for row in c.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "project_id" not in conversation_columns:
        c.execute("ALTER TABLE conversations ADD COLUMN project_id INTEGER")

    conversation_columns = {
        row["name"] for row in c.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "is_pinned" not in conversation_columns:
        c.execute("ALTER TABLE conversations ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")

    chat_columns = {
        row["name"] for row in c.execute("PRAGMA table_info(chats)").fetchall()
    }
    if "conversation_id" not in chat_columns:
        c.execute("ALTER TABLE chats ADD COLUMN conversation_id INTEGER")

    old_users = c.execute("""
        SELECT DISTINCT user_id FROM chats WHERE conversation_id IS NULL
    """).fetchall()
    for old_user in old_users:
        user_id = old_user["user_id"]
        first_message = c.execute("""
            SELECT content FROM chats
            WHERE user_id = ? AND role = 'user'
            ORDER BY id ASC LIMIT 1
        """, (user_id,)).fetchone()
        title = str(first_message["content"])[:55] if first_message else "محادثة سابقة"
        c.execute("INSERT INTO conversations(user_id, title) VALUES (?, ?)", (user_id, title))
        conversation_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("""
            UPDATE chats SET conversation_id = ?
            WHERE user_id = ? AND conversation_id IS NULL
        """, (conversation_id, user_id))

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

    if "session_version" not in user_columns:
        c.execute("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0")

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

    # Preserve the legacy Gemini context when migrating old chat history.
    c.execute("""
        UPDATE conversations
        SET gemini_interaction_id = (
            SELECT users.gemini_interaction_id
            FROM users
            WHERE users.id = conversations.user_id
        )
        WHERE gemini_interaction_id IS NULL
          AND EXISTS (
              SELECT 1 FROM chats
              WHERE chats.conversation_id = conversations.id
          )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_chats_user_id_id ON chats(user_id, id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chats_conversation_id ON chats(conversation_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chats_user_conversation_id ON chats(user_id, conversation_id, id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC, id DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_projects_user_created ON projects(user_id, created_at DESC)")

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
            "gemini-3.5-flash-lite"
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

    admin_password = os.getenv("ADMIN_PASSWORD")

    admin_name = os.getenv(
        "ADMIN_NAME",
        "مدير زولك"
    )

    # Apply ADMIN_PASSWORD only when its value changes. This makes the
    # environment variable a one-time bootstrap/reset mechanism, so a
    # password changed later from the admin dashboard is not overwritten
    # on every serverless cold start.
    password_fingerprint = (
        hashlib.sha256(admin_password.encode("utf-8")).hexdigest()
        if admin_password else None
    )
    applied_password = c.execute(
        "SELECT value FROM settings WHERE key = 'admin_password_env_fingerprint'"
    ).fetchone()
    apply_admin_password = bool(
        admin_password
        and (
            not applied_password
            or applied_password["value"] != password_fingerprint
        )
    )

    existing_admin = c.execute(
        """
        SELECT id
        FROM users
        WHERE email = ?
        """,
        (admin_email,)
    ).fetchone()

    if not existing_admin and admin_password:
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
        c.execute(
            """
            INSERT INTO settings(key, value)
            VALUES ('admin_password_env_fingerprint', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (password_fingerprint,)
        )

    elif existing_admin:
        if apply_admin_password:
            c.execute(
                """
                UPDATE users
                SET name = ?, password = ?, is_admin = 1,
                    session_version = session_version + 1
                WHERE email = ?
                """,
                (
                    admin_name,
                    generate_password_hash(admin_password),
                    admin_email
                )
            )
            c.execute(
                """
                INSERT INTO settings(key, value)
                VALUES ('admin_password_env_fingerprint', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (password_fingerprint,)
            )
        # When the environment password is unchanged, preserve the admin's
        # current role, ban state, and credits. Cold starts must not reset them.

    # -----------------------------------------------------
    # إصلاح أي إعداد قديم
    # -----------------------------------------------------

    c.execute(
        """
        UPDATE settings
        SET value = 'gemini-3.5-flash-lite'
        WHERE key = 'ai_model'
        AND value = 'gemini-2.5-flash'
        """
    )

    # One-time migration: move the old primary to the faster Flash-Lite model.
    model_migration = c.execute(
        "SELECT value FROM settings WHERE key = 'ai_model_fast_migration_v1'"
    ).fetchone()
    if not model_migration:
        c.execute("""
            UPDATE settings SET value = 'gemini-3.5-flash-lite'
            WHERE key = 'ai_model' AND value = 'gemini-3.8-flash'
        """)
        c.execute("""
            INSERT OR IGNORE INTO settings(key, value)
            VALUES ('ai_model_fast_migration_v1', 'done')
        """)

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


def history_enabled():
    return setting("enable_history", "true").strip().lower() not in (
        "false", "0", "off", "no"
    )


init_db()


def configure_secret_key():
    configured_key = os.getenv("SECRET_KEY")
    if configured_key:
        app.secret_key = configured_key
        return

    c = db()
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_secrets (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    c.execute("""
        INSERT OR IGNORE INTO app_secrets(key, value)
        VALUES ('flask_secret_key', ?)
    """, (secrets.token_urlsafe(48),))
    c.commit()

    row = c.execute("""
        SELECT value FROM app_secrets
        WHERE key = 'flask_secret_key'
    """).fetchone()
    c.close()

    app.secret_key = row["value"]


configure_secret_key()


# =========================================================
# PWA - ملف تعريف التطبيق
# =========================================================

@app.get("/manifest.json")
def web_manifest():

    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "manifest.json"
    )

    return send_file(
        manifest_path,
        mimetype="application/manifest+json"
    )


@app.get("/sw.js")
def service_worker():

    worker_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "static",
        "sw.js"
    )

    response = send_file(
        worker_path,
        mimetype="application/javascript"
    )

    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"

    return response


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
            SELECT id, is_banned, session_version
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

        if user["is_banned"] or int(user["session_version"] or 0) != int(session.get("session_version", 0)):

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

            return redirect("/login?next=/admin")

        c = db()

        user = c.execute(
            """
            SELECT id, is_admin, is_banned, session_version
            FROM users
            WHERE id = ?
            """,
            (session["uid"],)
        ).fetchone()

        c.close()

        if (
            not user
            or user["is_banned"]
            or int(user["session_version"] or 0) != int(session.get("session_version", 0))
        ):
            session.clear()

            if request.path.startswith("/api/"):
                return jsonify(
                    error="سجل دخولك من جديد."
                ), 401

            return redirect("/login")

        # An authenticated ordinary user must keep their session when
        # requesting an administrator-only page or API by mistake.
        if not user["is_admin"]:
            if request.path.startswith("/api/"):
                return jsonify(
                    error="ما عندك صلاحية للدخول."
                ), 403

            return redirect("/")

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
        site_name=setting("site_name", "زولك AI 🇸🇩"),
        welcome=setting("welcome", ""),
        site_description=setting(
            "site_description",
            "مساعد ذكاء اصطناعي سوداني يساعدك في الكتابة والدراسة والترجمة والشغل والدردشة 🇸🇩🤖"
        ),
        primary_color=setting("primary_color", "#08b991"),
        theme=setting("theme", "dark"),
        homepage_title=setting(
            "homepage_title",
            "كيف أقدر أساعدك اليوم؟"
        ),
        homepage_subtitle=setting(
            "homepage_text",
            "اسأل، اتعلّم، اكتب، أو ناقش أي فكرة."
        )
    )


@app.get("/login")
def login():

    return render_template(
        "login.html",
        admin_email=os.getenv("ADMIN_EMAIL", "admin@zolak.ai").strip().lower()
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
        or len(password) < 8
        or len(password) > 256
        or len(email) > 254
        or not re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", email)
    ):

        return jsonify(
            error="أدخل البيانات كاملة، وكلمة المرور 8 أحرف على الأقل."
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
            SELECT id, name, is_admin, session_version
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

    except (sqlite3.IntegrityError, psycopg.IntegrityError):

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
        ),
        session_version=int(user["session_version"] or 0)
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

    if len(email) > 254 or len(password) > 256:
        return jsonify(error="بيانات تسجيل الدخول غير صحيحة."), 400

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
        ),
        session_version=int(user["session_version"] or 0)
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
            is_banned,
            session_version
        FROM users
        WHERE id = ?
        """,
        (session["uid"],)
    ).fetchone()

    c.close()

    if (
        not user
        or user["is_banned"]
        or int(user["session_version"] or 0) != int(session.get("session_version", 0))
    ):

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

    import base64
    import binascii

    if request.content_length and request.content_length > 3_800_000:
        return jsonify(error="حجم المرفقات كبير. الحد الإجمالي 2.5 ميجابايت."), 413

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    raw_attachments = data.get("attachments") or []

    if not isinstance(raw_attachments, list) or len(raw_attachments) > 4:
        return jsonify(error="يمكنك إرفاق 4 ملفات كحد أقصى."), 400
    if not message and not raw_attachments:
        return jsonify(error="اكتب رسالتك أو أرفق ملفاً أولاً."), 400

    try:
        max_message_length = int(setting("max_message_length", "12000"))
        if max_message_length < 1:
            max_message_length = 12000
    except (TypeError, ValueError):
        max_message_length = 12000

    if len(message) > max_message_length:
        return jsonify(error=f"الرسالة طويلة شديد. الحد الأقصى {max_message_length} حرف."), 400

    allowed_mimes = {
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown", "text/csv"
    }
    attachments = []
    total_bytes = 0
    for item in raw_attachments:
        if not isinstance(item, dict):
            return jsonify(error="بيانات أحد المرفقات غير صحيحة."), 400
        name = os.path.basename(str(item.get("name", "ملف")).replace("\\", "/"))[:120]
        mime_type = str(item.get("mime_type", "")).lower().strip()
        encoded = str(item.get("data", ""))
        if mime_type not in allowed_mimes:
            return jsonify(error="نوع الملف غير مدعوم. استخدم صورة أو PDF أو TXT أو MD أو CSV."), 415
        if not encoded or len(encoded) > 3_500_000:
            return jsonify(error="حجم أحد الملفات أكبر من الحد المسموح."), 413
        try:
            file_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return jsonify(error="تعذر قراءة أحد الملفات المرفقة."), 400
        if not file_bytes:
            return jsonify(error="أحد الملفات المرفقة فارغ."), 400
        if len(file_bytes) > 2_500_000:
            return jsonify(error="حجم الملف الواحد يجب ألا يتجاوز 2.5 ميجابايت."), 413
        total_bytes += len(file_bytes)
        if total_bytes > 2_500_000:
            return jsonify(error="إجمالي حجم المرفقات يجب ألا يتجاوز 2.5 ميجابايت."), 413
        if mime_type == "application/pdf" and not file_bytes.startswith(b"%PDF-"):
            return jsonify(error="الملف لا يبدو مستند PDF صالحاً."), 400
        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            if not file_bytes.startswith(b"PK"):
                return jsonify(error="الملف لا يبدو مستند Word صالحاً."), 400
        if mime_type.startswith("image/"):
            signatures = {
                "image/jpeg": file_bytes.startswith(b"\xff\xd8\xff"),
                "image/png": file_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
                "image/gif": file_bytes.startswith((b"GIF87a", b"GIF89a")),
                "image/webp": len(file_bytes) > 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP"
            }
            if not signatures.get(mime_type, False):
                return jsonify(error="صيغة الصورة لا تطابق نوع الملف."), 400
        text_content = None
        if mime_type.startswith("text/"):
            try:
                text_content = file_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                return jsonify(error="الملف النصي يجب أن يكون بترميز UTF-8."), 400
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            import zipfile
            import xml.etree.ElementTree as ET
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as docx:
                    info = docx.getinfo("word/document.xml")
                    if info.file_size > 4_000_000:
                        return jsonify(error="مستند Word يحتوي على نص أكبر من الحد المسموح."), 413
                    document_xml = docx.read("word/document.xml")
                root = ET.fromstring(document_xml)
                text_content = "\n".join(
                    " ".join(part.strip() for part in paragraph.itertext() if part.strip())
                    for paragraph in root.iter()
                    if paragraph.tag.endswith("}p")
                )
            except (KeyError, zipfile.BadZipFile, ET.ParseError, OSError):
                return jsonify(error="تعذر قراءة مستند Word. تأكد أنه ملف DOCX سليم."), 400
        if text_content is not None and len(text_content) > 100_000:
            return jsonify(error="الملف النصي طويل جداً. الحد 100 ألف حرف."), 413
        attachments.append({
            "name": name,
            "mime_type": mime_type,
            "data": file_bytes,
            "text": text_content
        })

    if setting("maintenance", "false").lower() == "true":
        return jsonify(error="الموقع تحت الصيانة حالياً. جرب بعد شوية."), 503

    user_id = session["uid"]
    c = db()
    user = c.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()

    if not user:
        c.close()
        session.clear()
        return jsonify(error="سجل دخولك من جديد."), 401

    if user["credits"] <= 0:
        c.close()
        return jsonify(error="رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"), 402

    attachment_names = [item["name"] for item in attachments]
    stored_message = message
    if attachment_names:
        marker = "[المرفقات: " + "، ".join(attachment_names) + "]"
        stored_message = (message + "\n\n" + marker).strip()

    conversation_id = data.get("conversation_id")
    if conversation_id is not None:
        try:
            conversation_id = int(conversation_id)
        except (TypeError, ValueError):
            c.close()
            return jsonify(error="المحادثة المطلوبة غير صحيحة."), 400

        conversation = c.execute("""
            SELECT id FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()

        if not conversation:
            c.close()
            return jsonify(error="المحادثة غير موجودة."), 404
    else:
        title = message[:55] if message else ("ملف: " + attachment_names[0][:45])
        c.execute("""
            INSERT INTO conversations(user_id, title)
            VALUES (?, ?)
        """, (user_id, title))
        conversation_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.commit()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        c.close()
        return jsonify(error="مفتاح Gemini غير مضاف. راجع إعدادات الاستضافة."), 503

    save_history = history_enabled()
    history_rows = []
    if save_history:
        history_rows = c.execute("""
            SELECT role, content
            FROM chats
            WHERE conversation_id = ? AND user_id = ?
            ORDER BY id DESC
            LIMIT 6
        """, (conversation_id, user_id)).fetchall()
    c.close()

    def generate():
        import json

        def emit(event, payload):
            return "event: " + event + "\ndata: " + json.dumps(payload, ensure_ascii=False) + "\n\n"

        answer_parts = []
        stream_started = False
        save_conn = None
        try:
            system_instruction = (
                "أنت زولك AI، مساعد ذكاء اصطناعي سوداني ودود. "
                "أجب بوضوح ودقة وباختصار مفيد، ولا تطل بلا داعٍ. "
                "استخدم اللهجة السودانية عندما يكون ذلك مناسباً. "
                "عند إرفاق صورة أو مستند، افحص محتواه فعلياً وأجب عن المطلوب منه. "
                "لا تدّعي أنك إنسان. إذا لم تعرف الإجابة فقل ذلك بوضوح. "
                "لا تخترع معلومات."
            )

            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=12000,
                    retry_options=types.HttpRetryOptions(
                        attempts=1,
                        initial_delay=0.8,
                        max_delay=2.0,
                        exp_base=2.0,
                        jitter=0.2,
                        http_status_codes=[500, 502, 503, 504]
                    )
                )
            )

            model = setting("ai_model", "gemini-3.5-flash-lite").strip()
            if not model.startswith("gemini-"):
                model = "gemini-3.5-flash-lite"

            contents = []
            for row in reversed(history_rows):
                role = "user" if row["role"] == "user" else "model"
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=row["content"])]
                ))

            user_parts = []
            if message:
                user_parts.append(types.Part.from_text(text=message))
            for attachment in attachments:
                if attachment["text"] is not None:
                    user_parts.append(types.Part.from_text(
                        text="\n\nمحتوى الملف " + attachment["name"] + ":\n" + attachment["text"]
                    ))
                else:
                    user_parts.append(types.Part.from_bytes(
                        data=attachment["data"],
                        mime_type=attachment["mime_type"]
                    ))
            contents.append(types.Content(role="user", parts=user_parts))

            generation_config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                max_output_tokens=1536
            )

            yield emit("meta", {"conversation_id": conversation_id})

            try:
                # Keep the upstream request bounded and log each stage so a
                # production stall can be isolated without exposing user data.
                app.logger.info("AI generation started (model=%s)", model)
                response = client.models.generate_content(
                    model=model, contents=contents, config=generation_config
                )
                app.logger.info("AI generation response received (model=%s)", model)
                piece = (getattr(response, "text", None) or "")
                if piece:
                    stream_started = True
                    answer_parts.append(piece)
            except Exception as primary_error:
                error_text = str(primary_error).upper()
                temporary = any(marker in error_text for marker in (
                    "503", "UNAVAILABLE", "HIGH DEMAND", "MODEL_OVERLOADED",
                    "429", "RESOURCE_EXHAUSTED"
                ))
                fallback_model = os.getenv(
                    "GEMINI_FALLBACK_MODEL", "gemini-3.8-flash"
                ).strip()
                if stream_started or not temporary or not fallback_model.startswith("gemini-") or fallback_model == model:
                    raise
                app.logger.warning("Primary Gemini model unavailable; trying fallback model %s", fallback_model)
                response = client.models.generate_content(
                    model=fallback_model, contents=contents, config=generation_config
                )
                app.logger.info("AI fallback response received (model=%s)", fallback_model)
                piece = (getattr(response, "text", None) or "")
                if piece:
                    stream_started = True
                    answer_parts.append(piece)

            answer = "".join(answer_parts).strip()
            if not answer:
                yield emit("error", {"error": "وصلنا رد فارغ من خدمة الذكاء الاصطناعي. جرّب تاني."})
                return

            app.logger.info("AI generation completed; opening database connection to save reply")
            save_conn = db()
            app.logger.info("AI reply database connection opened")
            result = save_conn.execute("""
                UPDATE users SET credits = credits - 1
                WHERE id = ? AND credits > 0
            """, (user_id,))
            if result.rowcount != 1:
                save_conn.rollback()
                yield emit("error", {"error": "رصيدك ما كفاية لإرسال رسالة جديدة."})
                return

            if save_history:
                save_conn.execute("""
                    INSERT INTO chats(user_id, role, content, conversation_id)
                    VALUES (?, 'user', ?, ?)
                """, (user_id, stored_message, conversation_id))
                save_conn.execute("""
                    INSERT INTO chats(user_id, role, content, conversation_id)
                    VALUES (?, 'assistant', ?, ?)
                """, (user_id, answer, conversation_id))

            save_conn.execute("""
                UPDATE conversations
                SET title = CASE WHEN title = 'محادثة جديدة' THEN ? ELSE title END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, ((message[:55] or ("ملف: " + attachment_names[0][:45])) if attachment_names else message[:55], conversation_id, user_id))
            save_conn.commit()
            app.logger.info("AI reply and credit transaction committed")
            # Deliver the completed answer only after the credit deduction and
            # conversation writes have committed successfully. This prevents a
            # user from seeing a reply that the server later reports as failed.
            yield emit("token", {"text": answer})
            yield emit("done", {"conversation_id": conversation_id})

        except Exception as error:
            try:
                if save_conn is not None:
                    save_conn.rollback()
            except Exception:
                pass
            error_text = str(error)
            app.logger.exception("AI attachment/chat request failed: %s", error_text)
            upper = error_text.upper()
            if any(marker in upper for marker in ("API_KEY_INVALID", "INVALID API KEY", "UNAUTHENTICATED", "PERMISSION_DENIED", "403", "401")):
                message_text = "مفتاح Gemini غير صحيح أو ما عنده صلاحية. راجع إعدادات الاستضافة."
            elif any(marker in upper for marker in ("RESOURCE_EXHAUSTED", "QUOTA", "429", "RATE_LIMIT")):
                message_text = "وصلت خدمة الذكاء الاصطناعي لحد الاستخدام المتاح حالياً."
            elif "NOT_FOUND" in upper or ("MODEL" in upper and "NOT FOUND" in upper) or "404" in upper:
                message_text = "موديل الذكاء الاصطناعي المحدد غير متاح. راجع إعدادات الموديل."
            elif any(marker in upper for marker in ("503", "UNAVAILABLE", "HIGH DEMAND", "INTERNAL")):
                message_text = "خدمة Gemini مشغولة حالياً. حاول بعد شوية."
            elif any(marker in upper for marker in ("504", "DEADLINE_EXCEEDED", "TIMEOUT", "TIMED OUT")):
                message_text = "Gemini اتأخر في الرد. جرّب رسالة أقصر بعد لحظات، ولم يتم خصم رصيدك."
            elif "INVALID_ARGUMENT" in upper or "400" in upper:
                message_text = "إعداد طلب الذكاء الاصطناعي غير مقبول. راجع اسم الموديل وإعداداته."
            else:
                message_text = "تعذر الحصول على رد من Gemini. حاول مجدداً بعد قليل."
            yield emit("error", {"error": message_text})
        finally:
            if save_conn is not None:
                try:
                    save_conn.close()
                except Exception:
                    pass

    # Buffer the short SSE event sequence before returning it. Vercel's
    # serverless Python adapter can keep a streamed Flask generator alive
    # after upstream work has completed; that leaves invocations open until
    # the platform's 300-second hard timeout. The browser still parses the
    # same SSE events, but the serverless invocation now has a clear end.
    response = Response("".join(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache, no-transform"
    response.headers["X-Accel-Buffering"] = "no"
    return response


# =========================================================
# بدء محادثة جديدة
# =========================================================

@app.post("/api/chat/new")
@login_required
def new_chat():

    c = db()

    c.execute("""
        INSERT INTO conversations(user_id, title)
        VALUES (?, 'محادثة جديدة')
    """, (session["uid"],))
    conversation_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit()
    c.close()

    return jsonify(ok=True, conversation_id=conversation_id)


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


@app.get("/api/conversations")
@login_required
def list_conversations():
    if not history_enabled():
        return jsonify(conversations=[])

    query = str(request.args.get("q", "")).strip()[:120]
    project_value = request.args.get("project_id")
    project_id = None
    if project_value:
        try:
            project_id = int(project_value)
        except (TypeError, ValueError):
            return jsonify(error="المشروع المحدد غير صحيح."), 400

    conditions = ["conversations.user_id = ?"]
    params = [session["uid"]]
    if project_id is not None:
        conditions.append("conversations.project_id = ?")
        params.append(project_id)
    if query:
        pattern = f"%{query}%"
        conditions.append("""(
            conversations.title LIKE ?
            OR EXISTS (
                SELECT 1 FROM chats AS matching_chat
                WHERE matching_chat.conversation_id = conversations.id
                  AND matching_chat.user_id = conversations.user_id
                  AND matching_chat.content LIKE ?
            )
        )""")
        params.extend([pattern, pattern])

    c = db()
    rows = c.execute("""
        SELECT conversations.id, conversations.title, conversations.is_pinned,
               conversations.project_id, conversations.updated_at,
               COUNT(chats.id) AS message_count
        FROM conversations
        LEFT JOIN chats ON chats.conversation_id = conversations.id
        WHERE """ + " AND ".join(conditions) + """
        GROUP BY conversations.id
        HAVING COUNT(chats.id) > 0
        ORDER BY conversations.is_pinned DESC, conversations.updated_at DESC, conversations.id DESC
        LIMIT 100
    """, tuple(params)).fetchall()
    c.close()
    return jsonify(conversations=[dict(row) for row in rows])


@app.patch("/api/conversations/<int:conversation_id>")
@login_required
def update_conversation(conversation_id):
    data = request.get_json(silent=True) or {}
    title_value = data.get("title")
    pinned_value = data.get("is_pinned")
    project_requested = "project_id" in data
    project_value = data.get("project_id")

    if title_value is None and pinned_value is None and not project_requested:
        return jsonify(error="ما في تعديل مطلوب."), 400

    title = None
    if title_value is not None:
        title = str(title_value).strip()
        if not title:
            return jsonify(error="اكتب اسماً للمحادثة."), 400
        if len(title) > 80:
            return jsonify(error="اسم المحادثة طويل؛ الحد الأقصى 80 حرفاً."), 400

    if pinned_value is not None and not isinstance(pinned_value, bool):
        return jsonify(error="قيمة التثبيت غير صحيحة."), 400

    project_id = None
    if project_requested and project_value is not None:
        try:
            project_id = int(project_value)
        except (TypeError, ValueError):
            return jsonify(error="المشروع المحدد غير صحيح."), 400
        c = db()
        project = c.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?",
            (project_id, session["uid"])
        ).fetchone()
        c.close()
        if not project:
            return jsonify(error="المشروع غير موجود."), 404

    updates = []
    params = []
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if pinned_value is not None:
        updates.append("is_pinned = ?")
        params.append(int(pinned_value))
    if project_requested:
        updates.append("project_id = ?")
        params.append(project_id)
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([conversation_id, session["uid"]])

    c = db()
    result = c.execute(
        "UPDATE conversations SET " + ", ".join(updates) +
        " WHERE id = ? AND user_id = ?",
        tuple(params)
    )
    c.commit()
    c.close()
    if result.rowcount != 1:
        return jsonify(error="المحادثة غير موجودة."), 404
    return jsonify(ok=True, title=title, is_pinned=pinned_value, project_id=project_id if project_requested else None)


@app.get("/api/projects")
@login_required
def list_projects():
    c = db()
    rows = c.execute("""
        SELECT projects.id, projects.name, projects.created_at,
               COUNT(conversations.id) AS conversation_count
        FROM projects
        LEFT JOIN conversations
          ON conversations.project_id = projects.id
         AND conversations.user_id = projects.user_id
        WHERE projects.user_id = ?
        GROUP BY projects.id
        ORDER BY projects.created_at DESC, projects.id DESC
        LIMIT 50
    """, (session["uid"],)).fetchall()
    c.close()
    return jsonify(projects=[dict(row) for row in rows])


@app.post("/api/projects")
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify(error="اكتب اسم المشروع."), 400
    if len(name) > 60:
        return jsonify(error="اسم المشروع طويل؛ الحد الأقصى 60 حرفاً."), 400

    c = db()
    count = c.execute(
        "SELECT COUNT(*) AS total FROM projects WHERE user_id = ?",
        (session["uid"],)
    ).fetchone()["total"]
    if count >= 50:
        c.close()
        return jsonify(error="وصلت للحد الأقصى وهو 50 مشروعاً."), 400
    c.execute("INSERT INTO projects(user_id, name) VALUES (?, ?)", (session["uid"], name))
    project_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit()
    c.close()
    return jsonify(ok=True, project_id=project_id, name=name), 201


@app.patch("/api/projects/<int:project_id>")
@login_required
def rename_project(project_id):
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    if not name:
        return jsonify(error="اكتب اسم المشروع."), 400
    if len(name) > 60:
        return jsonify(error="اسم المشروع طويل؛ الحد الأقصى 60 حرفاً."), 400
    c = db()
    result = c.execute(
        "UPDATE projects SET name = ? WHERE id = ? AND user_id = ?",
        (name, project_id, session["uid"])
    )
    c.commit()
    c.close()
    if result.rowcount != 1:
        return jsonify(error="المشروع غير موجود."), 404
    return jsonify(ok=True, name=name)


@app.delete("/api/projects/<int:project_id>")
@login_required
def delete_project(project_id):
    c = db()
    project = c.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?",
        (project_id, session["uid"])
    ).fetchone()
    if not project:
        c.close()
        return jsonify(error="المشروع غير موجود."), 404
    c.execute(
        "UPDATE conversations SET project_id = NULL WHERE project_id = ? AND user_id = ?",
        (project_id, session["uid"])
    )
    c.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, session["uid"]))
    c.commit()
    c.close()
    return jsonify(ok=True)


@app.post("/api/conversations")
@login_required
def create_conversation():
    c = db()
    c.execute("""
        INSERT INTO conversations(user_id, title)
        VALUES (?, 'محادثة جديدة')
    """, (session["uid"],))
    conversation_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.commit()
    c.close()
    return jsonify(ok=True, conversation_id=conversation_id)


@app.get("/api/conversations/<int:conversation_id>")
@login_required
def get_conversation(conversation_id):
    if not history_enabled():
        return jsonify(error="حفظ المحادثات متوقف حالياً."), 403

    c = db()
    conversation = c.execute("""
        SELECT id, title FROM conversations
        WHERE id = ? AND user_id = ?
    """, (conversation_id, session["uid"])).fetchone()
    if not conversation:
        c.close()
        return jsonify(error="المحادثة غير موجودة."), 404
    rows = c.execute("""
        SELECT role, content, created_at FROM chats
        WHERE conversation_id = ? AND user_id = ?
        ORDER BY id ASC
    """, (conversation_id, session["uid"])).fetchall()
    c.close()
    return jsonify(conversation=dict(conversation), chats=[dict(row) for row in rows])


@app.delete("/api/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id):
    c = db()
    exists = c.execute("""
        SELECT id FROM conversations
        WHERE id = ? AND user_id = ?
    """, (conversation_id, session["uid"])).fetchone()
    if not exists:
        c.close()
        return jsonify(error="المحادثة غير موجودة."), 404
    c.execute("DELETE FROM chats WHERE conversation_id = ? AND user_id = ?",
              (conversation_id, session["uid"]))
    c.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?",
              (conversation_id, session["uid"]))
    c.commit()
    c.close()
    return jsonify(ok=True)


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
        "homepage_title",
        "homepage_text",
        "site_description",
        "welcome",
        "primary_color",
        "theme",
        "support_email",
        "announcement",
        "ai_model",
        "free_credits",
        "max_message_length",
        "enable_history",
        "maintenance",
        "allow_register"
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

                value = "gemini-3.5-flash-lite"

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

    if amount == 0 or abs(amount) > 1_000_000_000:

        return jsonify(
            error="أدخل عدداً صحيحاً بين -1,000,000,000 و1,000,000,000."
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

            except (sqlite3.IntegrityError, psycopg.IntegrityError):

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

            c.close()
            return jsonify(error="الرصيد غير صحيح."), 400

    if "is_admin" in data:
        requested_admin = data["is_admin"] in (
            True, 1, "1", "true", "True", "TRUE"
        )
        current_admin = bool(user["is_admin"])

        if uid == session.get("uid") and requested_admin != current_admin:
            c.close()
            return jsonify(error="ما ممكن تغيّر صلاحية حساب المدير المستخدم حالياً."), 400

        if current_admin and not requested_admin:
            admin_count = c.execute(
                "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1"
            ).fetchone()["n"]
            if admin_count <= 1:
                c.close()
                return jsonify(error="لا يمكن سحب صلاحية آخر مدير في النظام."), 400

        c.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?",
            (1 if requested_admin else 0, uid)
        )

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


@app.post("/api/admin/user/<int:uid>/ban")
@admin_required
def ban_user(uid):

    if uid == session.get("uid"):
        return jsonify(error="ما ممكن توقف حساب المدير الحالي."), 400

    c = db()
    target = c.execute(
        "SELECT id, is_admin FROM users WHERE id = ?",
        (uid,)
    ).fetchone()

    if not target:
        c.close()
        return jsonify(error="المستخدم ما موجود."), 404

    if target["is_admin"]:
        c.close()
        return jsonify(error="ما ممكن توقف حساب مدير."), 403

    c.execute(
        "UPDATE users SET is_banned = 1 WHERE id = ?",
        (uid,)
    )
    c.commit()
    c.close()

    return jsonify(ok=True)


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
        return jsonify(error="ما ممكن تحذف حساب المدير الحالي."), 400

    c = db()
    target = c.execute(
        "SELECT id, is_admin FROM users WHERE id = ?",
        (uid,)
    ).fetchone()

    if not target:
        c.close()
        return jsonify(error="المستخدم ما موجود."), 404

    if target["is_admin"]:
        c.close()
        return jsonify(error="ما ممكن تحذف حساب مدير."), 403

    c.execute("DELETE FROM users WHERE id = ?", (uid,))
    c.commit()
    c.close()

    return jsonify(ok=True)


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

    try:
        c = db()
        c.execute("SELECT 1").fetchone()
        c.close()
        checks["database"] = {
            "status": "ok",
            "message": "اتصال قاعدة البيانات يعمل بصورة طبيعية."
        }
    except Exception as error:
        checks["database"] = {
            "status": "error",
            "message": "تعذر الاتصال بقاعدة البيانات: " + str(error)[:180]
        }

    provider = "gemini"
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        checks["gemini"] = {
            "status": "ok",
            "message": "مفتاح Gemini موجود. اضغط «اختبار رد الذكاء الاصطناعي» للتأكد من صلاحية المفتاح والاتصال الفعلي."
        }
    else:
        checks["gemini"] = {
            "status": "warning",
            "message": "مفتاح GEMINI_API_KEY غير موجود في إعدادات الاستضافة. لن تعمل الردود الذكية قبل إضافته."
        }

    if os.getenv("DATABASE_URL", "").strip():
        checks["storage"] = {
            "status": "ok",
            "message": "التخزين الدائم مربوط بقاعدة PostgreSQL الخارجية (Supabase)."
        }
    else:
        directory = os.path.dirname(os.path.abspath(DB)) or "."
        writable = os.path.isdir(directory) and os.access(directory, os.W_OK)
        checks["storage"] = {
            "status": "ok" if writable else "error",
            "message": (
                "مسار قاعدة البيانات المحلية متاح للكتابة."
                if writable else "مجلد قاعدة البيانات المحلية غير متاح للكتابة."
            )
        }

    configured_model = setting("ai_model", "").strip()
    model = (
        configured_model
        if configured_model.startswith("gemini-")
        else "gemini-3.5-flash-lite"
    )

    checks["ai_model"] = model
    checks["provider"] = "gemini"

    statuses = [
        checks["database"]["status"],
        checks["gemini"]["status"],
        checks["storage"]["status"]
    ]
    overall = (
        "error" if "error" in statuses
        else "warning" if "warning" in statuses
        else "ok"
    )

    return jsonify(
        overall_status=overall,
        checks=checks,
        checked_at=datetime.now(timezone.utc).isoformat(),
        db_path=os.path.abspath(DB)
    )


@app.post("/api/admin/ai-test")
@admin_required
def admin_ai_test():

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return jsonify(
            ok=False,
            error="مفتاح Gemini غير مضاف. أضف GEMINI_API_KEY في إعدادات الاستضافة."
        ), 503

    try:
        from google import genai
        from google.genai import types

        model = setting("ai_model", "gemini-3.5-flash-lite").strip()
        if not model.startswith("gemini-"):
            model = "gemini-3.5-flash-lite"

        # Bound upstream latency so a stalled provider/network call cannot
        # occupy a Vercel function until the platform's hard timeout.
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=12000,
                retry_options=types.HttpRetryOptions(attempts=1)
            )
        )
        response = client.models.generate_content(
            model=model,
            contents="أجب بكلمة واحدة فقط: جاهز",
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                max_output_tokens=128
            )
        )
        answer = (response.text or "").strip()

        if not answer:
            return jsonify(
                ok=False,
                error="تم الاتصال بالموديل لكن لم يصل نص رد."
            ), 502

        return jsonify(
            ok=True,
            provider="gemini",
            model=model,
            answer=answer
        )

    except Exception as error:
        app.logger.exception("Admin Gemini connectivity test failed")
        upper = str(error).upper()

        if "API_KEY_INVALID" in upper or "UNAUTHENTICATED" in upper or "PERMISSION_DENIED" in upper or "403" in upper:
            friendly = "مفتاح Gemini غير صحيح أو لا يملك صلاحية."
        elif "RESOURCE_EXHAUSTED" in upper or "QUOTA" in upper or "429" in upper:
            friendly = "تم تجاوز حد الاستخدام أو الرصيد المتاح لمفتاح Gemini."
        elif "NOT_FOUND" in upper or "404" in upper:
            friendly = "موديل Gemini المحدد غير متاح لهذا المفتاح."
        else:
            friendly = "فشل الاتصال بـ Gemini. راجع سجل الأخطاء في الاستضافة."

        return jsonify(
            ok=False,
            error=friendly
        ), 503


# =========================================================
# إدارة المحادثات وحساب المدير
# =========================================================

@app.get("/api/admin/conversations")
@admin_required
def admin_conversations():
    c = db()
    rows = c.execute("""
        SELECT
            conversations.id,
            conversations.user_id,
            conversations.title,
            conversations.created_at,
            conversations.updated_at,
            users.name AS user_name,
            users.email AS user_email,
            COUNT(chats.id) AS message_count
        FROM conversations
        JOIN users ON users.id = conversations.user_id
        LEFT JOIN chats ON chats.conversation_id = conversations.id
        GROUP BY conversations.id, users.name, users.email
        ORDER BY conversations.updated_at DESC, conversations.id DESC
        LIMIT 100
    """).fetchall()
    c.close()
    return jsonify(conversations=[dict(row) for row in rows])


@app.delete("/api/admin/conversation/<int:conversation_id>")
@admin_required
def admin_delete_conversation(conversation_id):
    c = db()
    exists = c.execute(
        "SELECT id FROM conversations WHERE id = ?",
        (conversation_id,)
    ).fetchone()
    if not exists:
        c.close()
        return jsonify(error="المحادثة غير موجودة."), 404
    c.execute("DELETE FROM chats WHERE conversation_id = ?", (conversation_id,))
    c.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    c.commit()
    c.close()
    return jsonify(ok=True)


@app.get("/api/admin/account")
@admin_required
def admin_account():
    c = db()
    user = c.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (session["uid"],)
    ).fetchone()
    c.close()
    if not user:
        return jsonify(error="حساب المدير غير موجود."), 404
    return jsonify(account=dict(user))


@app.post("/api/admin/change-password")
@admin_required
def admin_change_password():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    if len(new_password) < 12:
        return jsonify(error="كلمة المرور الجديدة يجب أن تكون 12 حرفاً على الأقل."), 400
    if len(new_password) > 256:
        return jsonify(error="كلمة المرور طويلة جداً."), 400
    c = db()
    user = c.execute(
        "SELECT password FROM users WHERE id = ?",
        (session["uid"],)
    ).fetchone()
    if not user:
        c.close()
        session.clear()
        return jsonify(error="سجل الدخول من جديد."), 401
    valid, _legacy = verify_password(user["password"], current_password)
    if not valid:
        c.close()
        return jsonify(error="كلمة المرور الحالية غير صحيحة."), 403
    c.execute(
        "UPDATE users SET password = ?, session_version = session_version + 1 WHERE id = ?",
        (generate_password_hash(new_password), session["uid"])
    )
    c.commit()
    updated = c.execute("SELECT session_version FROM users WHERE id = ?", (session["uid"],)).fetchone()
    c.close()
    session["session_version"] = int(updated["session_version"] or 0)
    return jsonify(ok=True)


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
                conversation_id,
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

    projects_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT id, user_id, name, created_at
            FROM projects
            """
        ).fetchall()
    ]

    conversations_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT id, user_id, title, project_id, is_pinned, created_at, updated_at
            FROM conversations
            """
        ).fetchall()
    ]

    c.close()

    return jsonify(
        users=users,
        chats=chats_data,
        conversations=conversations_data,
        projects=projects_data,
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
                conversation_id,
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

    projects_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT id, user_id, name, created_at
            FROM projects
            """
        ).fetchall()
    ]

    conversations_data = [
        dict(row)
        for row in c.execute(
            """
            SELECT id, user_id, title, project_id, is_pinned, created_at, updated_at
            FROM conversations
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
        "conversations": conversations_data,
        "projects": projects_data,
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