import os
import sqlite3
import time
import json
from functools import wraps

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

    c.execute("""
        CREATE TABLE IF NOT EXISTS chats(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    columns = [
        x["name"]
        for x in c.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "banned" not in columns:
        c.execute("""
            ALTER TABLE users
            ADD COLUMN banned INTEGER DEFAULT 0
        """)

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

        c.execute("""
            INSERT INTO chats
            (
                user_id,
                role,
                content
            )
            VALUES(?,?,?)
        """, (
            session["uid"],
            "user",
            message
        ))

        c.execute("""
            INSERT INTO chats
            (
                user_id,
                role,
                content
            )
            VALUES(?,?,?)
        """, (
            session["uid"],
            "assistant",
            answer
        ))

        c.commit()

        return jsonify(
            answer=answer
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
# سجل المحادثات
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
            created_at
        FROM chats
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 50
    """, (
        session["uid"],
    )).fetchall()

    c.close()

    return jsonify(
        chats=[
            dict(row)
            for row in reversed(rows)
        ]
    )


# =========================================================
# لوحة المدير
# =========================================================

@app.get("/admin")
@admin_required
def admin():

    c = db()

    users = c.execute("""
        SELECT
            id,
            name,
            email,
            credits,
            is_admin,
            banned
        FROM users
        ORDER BY id DESC
    """).fetchall()

    total = c.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE is_admin=0
    """).fetchone()[0]

    messages = c.execute("""
        SELECT COUNT(*)
        FROM chats
    """).fetchone()[0]

    banned = c.execute("""
        SELECT COUNT(*)
        FROM users
        WHERE banned=1
        AND is_admin=0
    """).fetchone()[0]

    total_credits = c.execute("""
        SELECT COALESCE(SUM(credits),0)
        FROM users
        WHERE is_admin=0
    """).fetchone()[0]

    c.close()

    return render_template(
        "admin.html",
        users=users,
        total=total,
        msgs=messages,
        banned=banned,
        total_credits=total_credits,
        free=setting(
            "free_credits",
            "10"
        ),
        welcome=setting(
            "welcome"
        ),
        rights="© 2026 منذر السيد — جميع الحقوق محفوظة"
    )


# =========================================================
# محادثات مستخدم
# =========================================================

@app.get("/api/admin/user/<int:uid>/chats")
@admin_required
def admin_user_chats(uid):

    c = db()

    user = c.execute("""
        SELECT
            id,
            name,
            email
        FROM users
        WHERE id=?
    """, (
        uid,
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    rows = c.execute("""
        SELECT
            role,
            content,
            created_at
        FROM chats
        WHERE user_id=?
        ORDER BY id ASC
    """, (
        uid,
    )).fetchall()

    c.close()

    return jsonify(
        user=dict(user),
        chats=[
            dict(row)
            for row in rows
        ]
    )


# =========================================================
# إعدادات الإدارة
# =========================================================

ADMIN_SETTING_KEYS = {

    "site_name",
    "site_description",
    "free_credits",
    "welcome",

    "homepage_title",
    "homepage_subtitle",
    "homepage_button",

    "primary_color",
    "theme",
    "mobile_ui",

    "no_credits_message",
    "error_message",

    "logo_url",
    "background_url",

    "sudan_identity",
    "ad_text",
    "notifications",

    "ai_model",
    "ai_free_messages",

    "feature_writing",
    "feature_translation",
    "feature_study",

    "registration_enabled",
    "chat_history_enabled",
    "email_login_enabled",

    "maintenance_mode",
    "allow_login",
    "admin_protection",

    "packages"
}


@app.get("/api/admin/settings")
@admin_required
def get_admin_settings():

    c = db()

    rows = c.execute("""
        SELECT
            key,
            value
        FROM settings
    """).fetchall()

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

    boolean_keys = {

        "mobile_ui",
        "sudan_identity",
        "notifications",

        "feature_writing",
        "feature_translation",
        "feature_study",

        "registration_enabled",
        "chat_history_enabled",
        "email_login_enabled",

        "maintenance_mode",
        "allow_login",
        "admin_protection"
    }

    number_keys = {
        "free_credits",
        "ai_free_messages"
    }

    c = db()

    try:

        for key, value in data.items():

            if key not in ADMIN_SETTING_KEYS:
                continue

            if key in number_keys:

                try:

                    value = max(
                        0,
                        int(value)
                    )

                except (
                    ValueError,
                    TypeError
                ):

                    return jsonify(
                        error="القيمة الرقمية غير صحيحة."
                    ), 400

            elif key in boolean_keys:

                value = (
                    "1"
                    if str(value).lower()
                    in {
                        "1",
                        "true",
                        "yes",
                        "on"
                    }
                    else "0"
                )

            else:

                value = str(
                    value
                ).strip()

            c.execute("""
                INSERT OR REPLACE INTO settings
                (
                    key,
                    value
                )
                VALUES(?,?)
            """, (
                key,
                value
            ))

        c.commit()

    except Exception:

        c.rollback()

        raise

    finally:

        c.close()

    return jsonify(
        ok=True,
        message="تم حفظ الإعدادات بنجاح."
    )


# =========================================================
# إدارة الرصيد
# =========================================================

@app.post("/api/admin/user/<int:uid>/credits")
@admin_required
def add_credits(uid):

    data = request.get_json(
        silent=True
    ) or {}

    if "credits" in data:

        try:

            new_credits = int(
                data.get(
                    "credits",
                    0
                )
            )

        except (
            ValueError,
            TypeError
        ):

            return jsonify(
                error="قيمة الرصيد غير صحيحة."
            ), 400

        if new_credits < 0:

            return jsonify(
                error="الرصيد لا يمكن أن يكون سالباً."
            ), 400

        mode = "set"

    elif "amount" in data:

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

            return jsonify(
                error="قيمة الرصيد غير صحيحة."
            ), 400

        if amount <= 0:

            return jsonify(
                error="أدخل رقم أكبر من صفر."
            ), 400

        mode = "add"

    else:

        return jsonify(
            error="أدخل قيمة الرصيد."
        ), 400

    c = db()

    user = c.execute("""
        SELECT
            id,
            credits,
            is_admin
        FROM users
        WHERE id=?
    """, (
        uid,
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    if user["is_admin"]:

        c.close()

        return jsonify(
            error="لا يمكن تعديل رصيد المدير من هنا."
        ), 403

    if mode == "set":

        c.execute("""
            UPDATE users
            SET credits=?
            WHERE id=?
            AND is_admin=0
        """, (
            new_credits,
            uid
        ))

    else:

        c.execute("""
            UPDATE users
            SET credits=credits+?
            WHERE id=?
            AND is_admin=0
        """, (
            amount,
            uid
        ))

    updated = c.execute("""
        SELECT credits
        FROM users
        WHERE id=?
    """, (
        uid,
    )).fetchone()

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        message="تم تحديث الرصيد بنجاح.",
        credits=updated["credits"]
    )


# =========================================================
# حظر المستخدم
# =========================================================

@app.post("/api/admin/user/<int:uid>/ban")
@admin_required
def ban_user(uid):

    c = db()

    user = c.execute("""
        SELECT is_admin
        FROM users
        WHERE id=?
    """, (
        uid,
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    if user["is_admin"]:

        c.close()

        return jsonify(
            error="لا يمكن حظر المدير."
        ), 403

    c.execute("""
        UPDATE users
        SET banned=1
        WHERE id=?
        AND is_admin=0
    """, (
        uid,
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================================================
# إلغاء الحظر
# =========================================================

@app.post("/api/admin/user/<int:uid>/unban")
@admin_required
def unban_user(uid):

    c = db()

    user = c.execute("""
        SELECT
            id,
            is_admin
        FROM users
        WHERE id=?
    """, (
        uid,
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    if user["is_admin"]:

        c.close()

        return jsonify(
            error="لا يمكن تعديل حالة المدير."
        ), 403

    c.execute("""
        UPDATE users
        SET banned=0
        WHERE id=?
        AND is_admin=0
    """, (
        uid,
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================================================
# حذف المستخدم
# =========================================================

@app.delete("/api/admin/user/<int:uid>")
@admin_required
def delete_user(uid):

    c = db()

    user = c.execute("""
        SELECT
            id,
            is_admin
        FROM users
        WHERE id=?
    """, (
        uid,
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="المستخدم غير موجود."
        ), 404

    if user["is_admin"]:

        c.close()

        return jsonify(
            error="لا يمكن حذف حساب المدير."
        ), 403

    c.execute("""
        DELETE FROM chats
        WHERE user_id=?
    """, (
        uid,
    ))

    c.execute("""
        DELETE FROM users
        WHERE id=?
        AND is_admin=0
    """, (
        uid,
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True,
        message="تم حذف المستخدم ومحادثاته."
    )


# =========================================================
# المستخدمون
# =========================================================

@app.get("/api/admin/users")
@admin_required
def admin_users():

    query = request.args.get(
        "q",
        ""
    ).strip()

    c = db()

    sql = """
        SELECT
            u.id,
            u.name,
            u.email,
            u.credits,
            u.is_admin,
            u.banned,

            COUNT(ch.id)
