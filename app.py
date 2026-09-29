import os
import sqlite3
import time
import json
from functools import wraps
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    Response
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

DB = os.getenv(
    "DB_PATH",
    "/tmp/zolak.db"
)


# =========================================================
# إعدادات الموقع
# =========================================================

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


# =========================================================
# قاعدة البيانات
# =========================================================

def db():
    connection = sqlite3.connect(
        DB,
        timeout=20
    )

    connection.row_factory = sqlite3.Row

    return connection


def setting(key, default=""):
    connection = db()

    try:
        row = connection.execute(
            "SELECT value FROM settings WHERE key=?",
            (key,)
        ).fetchone()

        if row:
            return row["value"]

        return default

    finally:
        connection.close()


def init_db():

    connection = db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            credits INTEGER DEFAULT 10,
            is_admin INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'محادثة جديدة',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    user_columns = [
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "banned" not in user_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0"
        )

    chat_columns = [
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(chats)"
        ).fetchall()
    ]

    if "conversation_id" not in chat_columns:
        connection.execute(
            "ALTER TABLE chats ADD COLUMN conversation_id INTEGER"
        )

    for key, value in DEFAULT_SETTINGS.items():

        connection.execute(
            """
            INSERT OR IGNORE INTO settings(key,value)
            VALUES(?,?)
            """,
            (key, value)
        )

    admin = connection.execute(
        """
        SELECT id
        FROM users
        WHERE is_admin=1
        LIMIT 1
        """
    ).fetchone()

    if not admin:

        connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                credits,
                is_admin,
                banned
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                "مدير زولك",
                "admin@zolak.ai",
                generate_password_hash("admin123"),
                9999,
                1,
                0
            )
        )

    # ربط المحادثات القديمة
    old_users = connection.execute(
        """
        SELECT DISTINCT user_id
        FROM chats
        WHERE conversation_id IS NULL
        AND user_id IS NOT NULL
        """
    ).fetchall()

    for item in old_users:

        user_id = item["user_id"]

        conversation = connection.execute(
            """
            SELECT id
            FROM conversations
            WHERE user_id=?
            ORDER BY id
            LIMIT 1
            """,
            (user_id,)
        ).fetchone()

        if conversation:

            conversation_id = conversation["id"]

        else:

            cursor = connection.execute(
                """
                INSERT INTO conversations
                (user_id,title)
                VALUES(?,?)
                """,
                (
                    user_id,
                    "المحادثات القديمة"
                )
            )

            conversation_id = cursor.lastrowid

        connection.execute(
            """
            UPDATE chats
            SET conversation_id=?
            WHERE user_id=?
            AND conversation_id IS NULL
            """,
            (
                conversation_id,
                user_id
            )
        )

    connection.commit()
    connection.close()


init_db()


# =========================================================
# وظائف مساعدة
# =========================================================

def make_title(message):

    title = " ".join(
        str(message).strip().split()
    )

    if not title:
        return "محادثة جديدة"

    if len(title) > 42:
        return title[:42].rstrip() + "..."

    return title


def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("uid"):

            return jsonify(
                error="لازم تسجل دخول أولاً."
            ), 401

        return function(
            *args,
            **kwargs
        )

    return wrapper


def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if (
            not session.get("uid")
            or not session.get("admin")
        ):

            return jsonify(
                error="غير مصرح لك."
            ), 403

        return function(
            *args,
            **kwargs
        )

    return wrapper


def current_user():

    if not session.get("uid"):
        return None

    connection = db()

    try:

        return connection.execute(
            """
            SELECT *
            FROM users
            WHERE id=?
            """,
            (session["uid"],)
        ).fetchone()

    finally:

        connection.close()


# =========================================================
# الصفحة الرئيسية
# =========================================================

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


# =========================================================
# تسجيل الدخول والخروج
# =========================================================

@app.get("/login")
def login():
    return render_template("login.html")


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
        "registration_enabled",
        "1"
    ) != "1":

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

    except Exception:

        credits = 10

    connection = db()

    try:

        connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                credits,
                banned
            )
            VALUES(?,?,?,?,0)
            """,
            (
                name,
                email,
                generate_password_hash(password),
                credits
            )
        )

        connection.commit()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email=?
            """,
            (email,)
        ).fetchone()

    except sqlite3.IntegrityError:

        connection.close()

        return jsonify(
            error="الإيميل مستخدم قبل كده."
        ), 409

    connection.close()

    session.clear()

    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(
        user["is_admin"]
    )

    return jsonify(
        ok=True
    )


# =========================================================
# تسجيل الدخول
# =========================================================

@app.post("/api/login")
def api_login():

    if setting(
        "allow_login",
        "1"
    ) != "1":

        return jsonify(
            error="تسجيل الدخول متوقف حالياً."
        ), 403

    data = request.get_json(
        silent=True
    ) or {}

    email = str(
        data.get("email", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )

    connection = db()

    user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE email=?
        """,
        (email,)
    ).fetchone()

    if not user:

        connection.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    valid = False

    try:

        valid = check_password_hash(
            user["password"],
            password
        )

    except Exception:

        valid = False

    if (
        not valid
        and user["password"] == password
    ):

        valid = True

        connection.execute(
            """
            UPDATE users
            SET password=?
            WHERE id=?
            """,
            (
                generate_password_hash(password),
                user["id"]
            )
        )

        connection.commit()

    if not valid:

        connection.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    if (
        user["banned"]
        and not user["is_admin"]
    ):

        connection.close()

        return jsonify(
            error="الحساب موقوف حالياً. تواصل مع إدارة زولك."
        ), 403

    connection.close()

    session.clear()

    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(
        user["is_admin"]
    )

    return jsonify(
        ok=True
    )


# =========================================================
# بيانات المستخدم
# =========================================================

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


# =========================================================
# المحادثات
# =========================================================

@app.post("/api/conversations")
@login_required
def new_conversation():

    connection = db()

    cursor = connection.execute(
        """
        INSERT INTO conversations
        (user_id,title)
        VALUES(?,?)
        """,
        (
            session["uid"],
            "محادثة جديدة"
        )
    )

    conversation_id = cursor.lastrowid

    connection.commit()

    row = connection.execute(
        """
        SELECT *
        FROM conversations
        WHERE id=?
        """,
        (conversation_id,)
    ).fetchone()

    connection.close()

    return jsonify(
        ok=True,
        conversation=dict(row)
    )


@app.get("/api/conversations")
@login_required
def conversations():

    if setting(
        "chat_history_enabled",
        "1"
    ) != "1":

        return jsonify(
            conversations=[]
        )

    connection = db()

    rows = connection.execute(
        """
        SELECT
            id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE user_id=?
        ORDER BY updated_at DESC,id DESC
        """,
        (session["uid"],)
    ).fetchall()

    connection.close()

    return jsonify(
        conversations=[
            dict(row)
            for row in rows
        ]
    )


@app.get("/api/conversations/<int:conversation_id>")
@login_required
def get_conversation(conversation_id):

    connection = db()

    conversation = connection.execute(
        """
        SELECT *
        FROM conversations
        WHERE id=?
        AND user_id=?
        """,
        (
            conversation_id,
            session["uid"]
        )
    ).fetchone()

    if not conversation:

        connection.close()

        return jsonify(
            error="المحادثة غير موجودة."
        ), 404

    rows = connection.execute(
        """
        SELECT
            id,
            role,
            content,
            created_at
        FROM chats
        WHERE user_id=?
        AND conversation_id=?
        ORDER BY id
        """,
        (
            session["uid"],
            conversation_id
        )
    ).fetchall()

    connection.close()

    return jsonify(
        conversation=dict(conversation),
        chats=[
            dict(row)
            for row in rows
        ]
    )


@app.delete("/api/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id):

    connection = db()

    conversation = connection.execute(
        """
        SELECT id
        FROM conversations
        WHERE id=?
        AND user_id=?
        """,
        (
            conversation_id,
            session["uid"]
        )
    ).fetchone()

    if not conversation:

        connection.close()

        return jsonify(
            error="المحادثة غير موجودة."
        ), 404

    connection.execute(
        """
        DELETE FROM chats
        WHERE conversation_id=?
        AND user_id=?
        """,
        (
            conversation_id,
            session["uid"]
        )
    )

    connection.execute(
        """
        DELETE FROM conversations
        WHERE id=?
        AND user_id=?
        """,
        (
            conversation_id,
            session["uid"]
        )
    )

    connection.commit()
    connection.close()

    return jsonify(
        ok=True
    )


# =========================================================
# الذكاء الاصطناعي للمستخدم
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

    user_id = session["uid"]

    connection = db()

    try:

        user = connection.execute(
            """
            SELECT
                credits,
                banned,
                is_admin
            FROM users
            WHERE id=?
            """,
            (user_id,)
        ).fetchone()

        if not user:

            return jsonify(
                error="الحساب غير موجود."
            ), 404

        if (
            user["banned"]
            and not user["is_admin"]
        ):

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

        # ---------------------------------------------
        # المحادثة
        # ---------------------------------------------

        conversation_id = data.get(
            "conversation_id"
        )

        try:

            conversation_id = (
                int(conversation_id)
                if conversation_id is not None
                else None
            )

        except Exception:

            return jsonify(
                error="رقم المحادثة غير صحيح."
            ), 400

        if conversation_id is None:

            cursor = connection.execute(
                """
                INSERT INTO conversations
                (user_id,title)
                VALUES(?,?)
                """,
                (
                    user_id,
                    make_title(message)
                )
            )

            conversation_id = cursor.lastrowid

        else:

            conversation = connection.execute(
                """
                SELECT id
                FROM conversations
                WHERE id=?
                AND user_id=?
                """,
                (
                    conversation_id,
                    user_id
                )
            ).fetchone()

            if not conversation:

                return jsonify(
                    error="المحادثة غير موجودة."
                ), 404

        # ---------------------------------------------
        # مفتاح Gemini
        # ---------------------------------------------

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not api_key:

            connection.rollback()

            return jsonify(
                error="خدمة الذكاء الاصطناعي غير متاحة حالياً."
            ), 503

        try:

            from google import genai
            from google.genai import types

        except Exception:

            connection.rollback()

            return jsonify(
                error="خدمة الذكاء الاصطناعي غير متاحة حالياً."
            ), 503

        model = setting(
            "ai_model",
            "gemini-3.6-flash"
        ).strip()

        if not model:

            model = "gemini-3.6-flash"

        client = genai.Client(
            api_key=api_key
        )

        # ---------------------------------------------
        # محاولة الرد
        # ---------------------------------------------

        response = None
        last_error = None

        system_instruction = (
            "أنت زولك AI 🇸🇩، "
            "مساعد ذكاء اصطناعي سوداني ودود. "
            "أجب بوضوح وباختصار مناسب. "
            "استخدم اللهجة السودانية عندما يطلبها المستخدم. "
            "لا تدّعي أنك إنسان."
        )

        for attempt in range(3):

            try:

                # المحاولة الأولى بالإعدادات
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction
                )

                response = client.models.generate_content(
                    model=model,
                    contents=message,
                    config=config
                )

                break

            except Exception as exc:

                last_error = exc

                error_text = str(
                    exc
                ).upper()

                # -----------------------------------------
                # إصلاح مهم:
                # إذا فشل config نجرب الطلب بدونه
                # -----------------------------------------

                try:

                    response = client.models.generate_content(
                        model=model,
                        contents=message
                    )

                    break

                except Exception as second_exc:

                    last_error = second_exc

                    error_text = str(
                        second_exc
                    ).upper()

                    temporary = any(
                        word in error_text
                        for word in (
                            "503",
                            "UNAVAILABLE",
                            "429",
                            "RESOURCE_EXHAUSTED",
                            "TIMEOUT",
                            "DEADLINE"
                        )
                    )

                    if (
                        temporary
                        and attempt < 2
                    ):

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

        # ---------------------------------------------
        # استخراج الرد
        # ---------------------------------------------

        answer = (
            getattr(
                response,
                "text",
                None
            )
            or ""
        ).strip()

        if not answer:

            connection.rollback()

            return jsonify(
                error="الذكاء الاصطناعي ما رجّع إجابة. جرّب تاني."
            ), 502

        answer += (
            "\n\n— تطوير منذر السيد 🇸🇩"
        )

        # ---------------------------------------------
        # خصم استخدام
        # ---------------------------------------------

        if not user["is_admin"]:

            connection.execute(
                """
                UPDATE users
                SET credits=credits-1
                WHERE id=?
                AND credits>0
                """,
                (user_id,)
            )

            if connection.total_changes < 1:

                connection.rollback()

                return jsonify(
                    error=setting(
                        "no_credits_message",
                        "رصيدك المجاني خلص."
                    )
                ), 402

        # ---------------------------------------------
        # حفظ الرسائل
        # ---------------------------------------------

        connection.execute(
            """
            INSERT INTO chats
            (
                user_id,
                conversation_id,
                role,
                content
            )
            VALUES(?,?,?,?)
            """,
            (
                user_id,
                conversation_id,
                "user",
                message
            )
        )

        connection.execute(
            """
            INSERT INTO chats
            (
                user_id,
                conversation_id,
                role,
                content
            )
            VALUES(?,?,?,?)
            """,
            (
                user_id,
                conversation_id,
                "assistant",
                answer
            )
        )

        connection.execute(
            """
            UPDATE conversations
            SET
                title=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            AND user_id=?
            """,
            (
                make_title(message),
                conversation_id,
                user_id
            )
        )

        connection.commit()

        conversation = connection.execute(
            """
            SELECT
                id,
                title,
                created_at,
                updated_at
            FROM conversations
            WHERE id=?
            AND user_id=?
            """,
            (
                conversation_id,
                user_id
            )
        ).fetchone()

        return jsonify(
            answer=answer,
            conversation_id=conversation_id,
            conversation=dict(conversation)
        )

    except Exception as exc:

        connection.rollback()

        error_text = str(
            exc
        ).upper()

        if (
            "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
        ):

            return jsonify(
                error="الخدمة عليها ضغط أو وصلت للحد المسموح. جرّب تاني بعد شوية."
            ), 429

        if (
            "503" in error_text
            or "UNAVAILABLE" in
