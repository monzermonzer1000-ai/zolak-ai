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

from werkzeug.security import generate_password_hash, check_password_hash


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
# قاعدة البيانات
# =========================================================

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():

    c = db()

    # -----------------------------
    # المستخدمون
    # -----------------------------

    c.execute("""
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

    # -----------------------------
    # المحادثات الرئيسية
    # -----------------------------

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'محادثة جديدة',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------
    # الرسائل
    # -----------------------------

    c.execute("""
        CREATE TABLE IF NOT EXISTS chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            conversation_id INTEGER,
            role TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------
    # الإعدادات
    # -----------------------------

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # -----------------------------
    # توافق قاعدة البيانات القديمة
    # -----------------------------

    user_columns = [
        x["name"]
        for x in c.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "banned" not in user_columns:
        c.execute("""
            ALTER TABLE users
            ADD COLUMN banned INTEGER DEFAULT 0
        """)

    chat_columns = [
        x["name"]
        for x in c.execute(
            "PRAGMA table_info(chats)"
        ).fetchall()
    ]

    if "conversation_id" not in chat_columns:
        c.execute("""
            ALTER TABLE chats
            ADD COLUMN conversation_id INTEGER
        """)

    # -----------------------------
    # إنشاء المدير إذا غير موجود
    # -----------------------------

    admin = c.execute("""
        SELECT id
        FROM users
        WHERE is_admin=1
        LIMIT 1
    """).fetchone()

    if not admin:

        admin_password = generate_password_hash(
            "admin123"
        )

        c.execute("""
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
        """, (
            "مدير زولك",
            "admin@zolak.ai",
            admin_password,
            9999,
            1,
            0
        ))

    # -----------------------------
    # الإعدادات الافتراضية
    # -----------------------------

    settings = [

        ("site_name", "زولك AI 🇸🇩"),

        (
            "site_description",
            "مساعد ذكاء اصطناعي سوداني يساعدك في الكتابة والدراسة والترجمة والشغل والدردشة 🇸🇩🤖"
        ),

        ("free_credits", "10"),

        (
            "welcome",
            "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة."
        ),

        ("homepage_title", "زولك AI 🇸🇩"),

        (
            "homepage_subtitle",
            "مساعد الذكاء الاصطناعي السوداني 🇸🇩"
        ),

        ("homepage_button", "ابدأ الآن"),

        ("primary_color", "#00c896"),

        ("theme", "dark"),

        ("mobile_ui", "1"),

        (
            "no_credits_message",
            "رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"
        ),

        (
            "error_message",
            "حصلت مشكلة، حاول مرة تانية."
        ),

        ("logo_url", ""),

        ("background_url", ""),

        ("sudan_identity", "1"),

        ("ad_text", ""),

        ("notifications", "1"),

        ("ai_model", "gemini-3.6-flash"),

        ("ai_free_messages", "10"),

        ("feature_writing", "1"),

        ("feature_translation", "1"),

        ("feature_study", "1"),

        ("registration_enabled", "1"),

        ("chat_history_enabled", "1"),

        ("email_login_enabled", "1"),

        ("maintenance_mode", "0"),

        ("allow_login", "1"),

        ("admin_protection", "1"),

        ("packages", "[]")
    ]

    for key, value in settings:

        c.execute("""
            INSERT OR IGNORE INTO settings
            (
                key,
                value
            )
            VALUES(?,?)
        """, (
            key,
            value
        ))

    # =====================================================
    # ترحيل المحادثات القديمة
    # =====================================================
    #
    # إذا كانت عندك رسائل قديمة من النظام السابق بدون
    # conversation_id، يتم وضعها داخل محادثة واحدة قديمة
    # لكل مستخدم بدلاً من حذفها.
    #

    old_rows = c.execute("""
        SELECT DISTINCT user_id
        FROM chats
        WHERE conversation_id IS NULL
        AND user_id IS NOT NULL
    """).fetchall()

    for old_user in old_rows:

        uid = old_user["user_id"]

        existing = c.execute("""
            SELECT id
            FROM conversations
            WHERE user_id=?
            ORDER BY id ASC
            LIMIT 1
        """, (
            uid,
        )).fetchone()

        if existing:

            conversation_id = existing["id"]

        else:

            c.execute("""
                INSERT INTO conversations
                (
                    user_id,
                    title
                )
                VALUES(?,?)
            """, (
                uid,
                "المحادثات القديمة"
            ))

            conversation_id = c.lastrowid

        c.execute("""
            UPDATE chats
            SET conversation_id=?
            WHERE user_id=?
            AND conversation_id IS NULL
        """, (
            conversation_id,
            uid
        ))

        c.execute("""
            UPDATE conversations
            SET updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (
            conversation_id,
        ))

    c.commit()
    c.close()


def setting(key, default=""):

    c = db()

    row = c.execute("""
        SELECT value
        FROM settings
        WHERE key=?
    """, (
        key,
    )).fetchone()

    c.close()

    if row:
        return row["value"]

    return default


init_db()


# =========================================================
# أدوات المحادثات
# =========================================================

def create_conversation(user_id, title="محادثة جديدة"):

    c = db()

    c.execute("""
        INSERT INTO conversations
        (
            user_id,
            title
        )
        VALUES(?,?)
    """, (
        user_id,
        title
    ))

    conversation_id = c.lastrowid

    c.commit()
    c.close()

    return conversation_id


def get_conversation(user_id, conversation_id):

    c = db()

    row = c.execute("""
        SELECT
            id,
            user_id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE id=?
        AND user_id=?
    """, (
        conversation_id,
        user_id
    )).fetchone()

    c.close()

    return row


def make_title(message):

    title = str(message).strip()

    if not title:
        return "محادثة جديدة"

    # إزالة الأسطر
    title = " ".join(
        title.split()
    )

    # عنوان قصير للقائمة
    if len(title) > 42:
        title = title[:42].rstrip() + "..."

    return title


# =========================================================
# الحماية
# =========================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if "uid" not in session:

            return jsonify(
                error="لازم تسجل دخول أولاً."
            ), 401

        return fn(
            *args,
            **kwargs
        )

    return wrapper


def admin_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if not session.get("admin"):

            return jsonify(
                error="غير مصرح لك."
            ), 403

        return fn(
            *args,
            **kwargs
        )

    return wrapper


# =========================================================
# الصفحة الرئيسية
# =========================================================

@app.get("/")
def home():

    return render_template(
        "index.html",

        site_name=setting(
            "site_name",
            "زولك AI"
        ),

        site_description=setting(
            "site_description",
            "مساعد ذكاء اصطناعي سوداني 🇸🇩🤖"
        ),

        welcome=setting(
            "welcome",
            "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة."
        ),

        homepage_title=setting(
            "homepage_title",
            "زولك AI 🇸🇩"
        ),

        homepage_subtitle=setting(
            "homepage_subtitle",
            "مساعد الذكاء الاصطناعي السوداني 🇸🇩"
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
            "رصيدك المجاني خلص."
        ),

        error_message=setting(
            "error_message",
            "حصلت مشكلة، حاول مرة تانية."
        )
    )


# =========================================================
# تسجيل الدخول والخروج
# =========================================================

@app.get("/login")
def login():

    return render_template(
        "login.html"
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

    try:

        free = int(
            setting(
                "free_credits",
                "10"
            )
        )

    except (
        ValueError,
        TypeError
    ):

        free = 10

    password_hash = generate_password_hash(
        password
    )

    c = db()

    try:

        c.execute("""
            INSERT INTO users
            (
                name,
                email,
                password,
                credits,
                banned
            )
            VALUES(?,?,?,?,?)
        """, (
            name,
            email,
            password_hash,
            free,
            0
        ))

        c.commit()

    except sqlite3.IntegrityError:

        c.close()

        return jsonify(
            error="الإيميل مستخدم قبل كده."
        ), 409

    user = c.execute("""
        SELECT *
        FROM users
        WHERE email=?
    """, (
        email,
    )).fetchone()

    c.close()

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

    user = c.execute("""
        SELECT *
        FROM users
        WHERE email=?
    """, (
        email,
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    stored_password = user["password"]

    password_ok = False

    try:

        password_ok = check_password_hash(
            stored_password,
            password
        )

    except Exception:

        password_ok = False

    if (
        not password_ok
        and stored_password == password
    ):

        password_ok = True

        new_hash = generate_password_hash(
            password
        )

        c.execute("""
            UPDATE users
            SET password=?
            WHERE id=?
        """, (
            new_hash,
            user["id"]
        ))

        c.commit()

    if not password_ok:

        c.close()

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    if (
        user["banned"]
        and not user["is_admin"]
    ):

        c.close()

        return jsonify(
            error="الحساب موقوف حالياً. تواصل مع إدارة زولك."
        ), 403

    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(
        user["is_admin"]
    )

    c.close()

    return jsonify(
        ok=True
    )


# =========================================================
# بيانات المستخدم
# =========================================================

@app.get("/api/me")
def me():

    if "uid" not in session:

        return jsonify(
            logged_in=False
        )

    c = db()

    user = c.execute("""
        SELECT
            name,
            email,
            credits,
            is_admin,
            banned
        FROM users
        WHERE id=?
    """, (
        session["uid"],
    )).fetchone()

    c.close()

    if not user:

        session.clear()

        return jsonify(
            logged_in=False
        )

    return jsonify(
        logged_in=True,
        **dict(user)
    )


# =========================================================
# إنشاء محادثة جديدة
# =========================================================

@app.post("/api/conversations")
@login_required
def new_conversation():

    if setting(
        "chat_history_enabled",
        "1"
    ) != "1":

        return jsonify(
            error="حفظ المحادثات متوقف حالياً."
        ), 403

    conversation_id = create_conversation(
        session["uid"],
        "محادثة جديدة"
    )

    conversation = get_conversation(
        session["uid"],
        conversation_id
    )

    return jsonify(
        ok=True,
        conversation=dict(conversation)
    )


# =========================================================
# قائمة محادثات المستخدم
# =========================================================

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

    c = db()

    rows = c.execute("""
        SELECT
            id,
            title,
            created_at,
            updated_at
        FROM conversations
        WHERE user_id=?
        ORDER BY updated_at DESC, id DESC
    """, (
        session["uid"],
    )).fetchall()

    c.close()

    return jsonify(
        conversations=[
            dict(row)
            for row in rows
        ]
    )


# =========================================================
# رسائل محادثة معينة
# =========================================================

@app.get("/api/conversations/<int:conversation_id>")
@login_required
def get_conversation_messages(conversation_id):

    if setting(
        "chat_history_enabled",
        "1"
    ) != "1":

        return jsonify(
            error="حفظ المحادثات متوقف حالياً."
        ), 403

    conversation = get_conversation(
        session["uid"],
        conversation_id
    )

    if not conversation:

        return jsonify(
            error="المحادثة غير موجودة."
        ), 404

    c = db()

    rows = c.execute("""
        SELECT
            id,
            role,
            content,
            created_at
        FROM chats
        WHERE user_id=?
        AND conversation_id=?
        ORDER BY id ASC
    """, (
        session["uid"],
        conversation_id
    )).fetchall()

    c.close()

    return jsonify(
        conversation=dict(conversation),
        chats=[
            dict(row)
            for row in rows
        ]
    )


# =========================================================
# حذف محادثة
# =========================================================

@app.delete("/api/conversations/<int:conversation_id>")
@login_required
def delete_conversation(conversation_id):

    c = db()

    conversation = c.execute("""
        SELECT id
        FROM conversations
        WHERE id=?
        AND user_id=?
    """, (
        conversation_id,
        session["uid"]
    )).fetchone()

    if not conversation:

        c.close()

        return jsonify(
            error="المحادثة غير موجودة."
        ), 404

    c.execute("""
        DELETE FROM chats
        WHERE conversation_id=?
        AND user_id=?
    """, (
        conversation_id,
        session["uid"]
    ))

    c.execute("""
        DELETE FROM conversations
        WHERE id=?
        AND user_id=?
    """, (
        conversation_id,
        session["uid"]
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        message="تم حذف المحادثة."
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
        data.get(
            "message",
            ""
        )
    ).strip()

    if not message:

        return jsonify(
            error="اكتب رسالتك أولاً."
        ), 400

    # -----------------------------------------
    # تحديد المحادثة
    # -----------------------------------------

    conversation_id = data.get(
        "conversation_id"
    )

    try:

        if conversation_id is not None:
            conversation_id = int(
                conversation_id
            )

    except (
        ValueError,
        TypeError
    ):

        conversation_id = None

    c = db()

    try:

        user = c.execute("""
            SELECT
                credits,
                banned,
                is_admin
            FROM users
            WHERE id=?
        """, (
            session["uid"],
        )).fetchone()

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

        # -----------------------------------------
        # إنشاء محادثة إذا لم يتم تحديد واحدة
        # -----------------------------------------

        if conversation_id is None:

            c.execute("""
                INSERT INTO conversations
                (
                    user_id,
                    title
                )
                VALUES(?,?)
            """, (
                session["uid"],
                make_title(message)
            ))

            conversation_id = c.lastrowid

        else:

            conversation = c.execute("""
                SELECT id
                FROM conversations
                WHERE id=?
                AND user_id=?
            """, (
                conversation_id,
                session["uid"]
            )).fetchone()

            if not conversation:

                return jsonify(
                    error="المحادثة غير موجودة."
                ), 404

        # -----------------------------------------
        # مفتاح Gemini
        # -----------------------------------------

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        if not api_key:

            return jsonify(
                error="مفتاح Gemini لم تتم إضافته في الاستضافة."
            ), 503

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key
        )

        config = types.GenerateContentConfig(
            system_instruction=(
                "أنت زولك AI 🇸🇩، مساعد ذكاء اصطناعي سوداني ودود. "
                "أجب بوضوح وباختصار مناسب. "
                "استخدم اللهجة السودانية عندما يطلبها المستخدم. "
                "لا تدّعي أنك إنسان."
            )
        )

        response = None

        model_name = setting(
            "ai_model",
            "gemini-3.6-flash"
        )

        for attempt in range(3):

            try:

                response = client.models.generate_content(
                    model=model_name,
                    contents=message,
                    config=config
                )

                break

            except Exception as e:

                error_text = str(
                    e
                ).upper()

                if (
                    (
                        "503" in error_text
                        or "UNAVAILABLE" in error_text
                    )
                    and attempt < 2
                ):

                    time.sleep(
                        2 * (attempt + 1)
                    )

                    continue

                raise

        answer = (
            response.text or ""
        ).strip()

        if not answer:

            return jsonify(
                error="الذكاء الاصطناعي ما رجّع إجابة. جرّب تاني."
            ), 502

        answer += "\n\n— تطوير منذر السيد 🇸🇩"

        # -----------------------------------------
        # خصم الرصيد
        # -----------------------------------------

        if not user["is_admin"]:

            c.execute("""
                UPDATE users
                SET credits = credits - 1
                WHERE id=?
                AND credits > 0
            """, (
                session["uid"],
            ))

            if c.rowcount != 1:

                c.rollback()

                return jsonify(
                    error=setting(
                        "no_credits_message",
                        "رصيدك المجاني خلص."
                    )
                ), 402

        # -----------------------------------------
        # حفظ رسالة المستخدم
        # -----------------------------------------

        c.execute("""
            INSERT INTO chats
            (
                user_id,
                conversation_id,
                role,
                content
            )
            VALUES(?,?,?,?,?)
        """, (
            session["uid"],
            conversation_id,
            "user",
            message
        ))

        # -----------------------------------------
        # حفظ رد الذكاء الاصطناعي
        # -----------------------------------------

        c.execute("""
            INSERT INTO chats
            (
                user_id,
                conversation_id,
                role,
                content
            )
            VALUES(?,?,?,?,?)
        """, (
            session["uid"],
            conversation_id,
            "assistant",
            answer
        ))

        # -----------------------------------------
        # تحديث عنوان المحادثة
        # -----------------------------------------

        existing_messages = c.execute("""
            SELECT COUNT(*)
            FROM chats
            WHERE conversation_id=?
            AND user_id=?
        """, (
            conversation_id,
            session["uid"]
        )).fetchone()[0]

        if existing_messages <= 2:

            c.execute("""
                UPDATE conversations
                SET title=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                AND user_id=?
            """, (
                make_title(message),
                conversation_id,
                session["uid"]
            ))

        else:

            c.execute("""
                UPDATE conversations
                SET updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                AND user_id=?
            """, (
                conversation_id,
                session["uid"]
            ))

        c.commit()

        conversation = c.execute("""
            SELECT
                id,
                title,
                created_at,
                updated_at
            FROM conversations
            WHERE id=?
            AND user_id=?
        """, (
            conversation_id,
            session["uid"]
        )).fetchone()

        return jsonify(
            answer=answer,
            conversation_id=conversation_id,
            conversation=dict(conversation)
        )

    except Exception as e:

        c.rollback()

        error_text = str(
            e
        ).upper()

        if (
            "503" in error_text
            or "UNAVAILABLE" in error_text
        ):

            return jsonify(
                error="الخدمة عليها ضغط شديد حالياً. انتظر شوية وجرب تاني يا زول ❤️"
            ), 503

        app.logger.exception(
            "Gemini chat error"
        )

        return jsonify(
            error=setting(
                "error_message",
                "حصلت مشكلة أثناء إرسال رسالتك. جرّب تاني بعد شوية."
            )
        ), 500

    finally:

        c.close()


# =========================================================
# سجل المحادثات القديم - توافق
# =========================================================

@app.get("/api/chats")
@login_required
def chats():

    if setting(
        "chat_history_enabled",
        "1"
    ) != "1":

        return jsonify(
            chats=[]
        )

    c = db()

    rows = c.execute("""
        SELECT
            role,
            content,
            created_at,
            conversation_id
        FROM chats
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 50
    """, (
        session["uid"],
    )).fetchall()

    c.close()

    return jsonify(
        chats
