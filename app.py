import os
import sqlite3
import time
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect
)

from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "change-this-secret-in-production"
)

DB = "/tmp/zolak.db"


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

    # إنشاء المدير إذا لم يكن موجوداً
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

    # الإعدادات الأساسية
    settings = [

        (
            "site_name",
            "زولك AI 🇸🇩"
        ),

        (
            "site_description",
            "مساعد ذكاء اصطناعي سوداني يساعدك في الكتابة والدراسة والترجمة والشغل والدردشة 🇸🇩🤖"
        ),

        (
            "free_credits",
            "10"
        ),

        (
            "welcome",
            "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة."
        )

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


def setting(
    key,
    default=""
):

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
# الصفحات
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


# =========================================================
# التسجيل
# =========================================================

@app.post("/api/register")
def register():

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

    # كلمات المرور الجديدة تكون Hash
    try:

        password_ok = check_password_hash(
            stored_password,
            password
        )

    except Exception:

        password_ok = False

    # توافق مع الحسابات القديمة
    if not password_ok and stored_password == password:

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
# المحادثة مع Gemini
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
                error="رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"
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

        for attempt in range(3):

            try:

                response = client.models.generate_content(
                    model="gemini-3.6-flash",
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

        # خصم رصيد المستخدم العادي
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
                    error="رصيدك المجاني خلص. حدّث الصفحة وجرب تاني."
                ), 402

        # حفظ رسالة المستخدم
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

        # حفظ رد الذكاء الاصطناعي
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
            error="حصلت مشكلة أثناء إرسال رسالتك. جرّب تاني بعد شوية."
        ), 500

    finally:

        c.close()


# =========================================================
# سجل محادثات المستخدم
# =========================================================

@app.get("/api/chats")
@login_required
def chats():

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
# محادثات مستخدم للأدمن
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
# إعدادات زولك
# =========================================================

@app.post("/api/admin/settings")
@admin_required
def admin_settings():

    data = request.get_json(
        silent=True
    ) or {}

    c = db()

    # اسم الموقع
    if "site_name" in data:

        c.execute("""
            INSERT OR REPLACE INTO settings
            (
                key,
                value
            )
            VALUES(?,?)
        """, (
            "site_name",
            str(
                data["site_name"]
            ).strip()
        ))

    # وصف الموقع
    if "site_description" in data:

        c.execute("""
            INSERT OR REPLACE INTO settings
            (
                key,
                value
            )
            VALUES(?,?)
        """, (
            "site_description",
            str(
                data["site_description"]
            ).strip()
        ))

    # الرصيد المجاني
    if "free_credits" in data:

        try:

            free = int(
                data["free_credits"]
            )

            if free < 0:
                free = 0

        except (
            ValueError,
            TypeError
        ):

            free = 10

        c.execute("""
            INSERT OR REPLACE INTO settings
            (
                key,
                value
            )
            VALUES(?,?)
        """, (
            "free_credits",
            str(free)
        ))

    # رسالة الترحيب
    if "welcome" in data:

        c.execute("""
            INSERT OR REPLACE INTO settings
            (
                key,
                value
            )
            VALUES(?,?)
        """, (
            "welcome",
            str(
                data["welcome"]
            )
        ))

    c.commit()
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

    # يدعم amount للإضافة
    # و credits كقيمة جديدة للرصيد
    has_amount = "amount" in data
    has_credits = "credits" in data

    if not has_amount and not has_credits:

        return jsonify(
            error="أدخل قيمة الرصيد."
        ), 400

    try:

        if has_credits:

            new_credits = int(
                data.get(
                    "credits",
                    0
                )
            )

            if new_credits < 0:

                return jsonify(
                    error="الرصيد لا يمكن أن يكون سالباً."
                ), 400

            mode = "set"

        else:

            amount = int(
                data.get(
                    "amount",
                    0
                )
            )

            if amount <= 0:

                return jsonify(
                    error="أدخل رقم أكبر من صفر."
                ), 400

            mode = "add"

    except (
        ValueError,
        TypeError
    ):

        return jsonify(
            error="قيمة الرصيد غير صحيحة."
        ), 400

    c = db()

    user = c.execute("""
        SELECT
            id,
            name,
            email,
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

    if c.rowcount != 1:

        c.rollback()
        c.close()

        return jsonify(
            error="لم يتم تحديث الرصيد."
        ), 500

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
        SELECT id,is_admin
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

    # حذف المحادثات أولاً
    c.execute("""
        DELETE FROM chats
        WHERE user_id=?
    """, (
        uid,
    ))

    # حذف المستخدم
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
# المستخدمون + إحصائياتهم
# =========================================================

@app.get("/api/admin/users")
@admin_required
def admin_users():

    query = request.args.get(
        "q",
        ""
    ).strip()

    c = db()

    base_sql = """
        SELECT
            u.id,
            u.name,
            u.email,
            u.credits,
            u.is_admin,
            u.banned,

            COUNT(ch.id) AS messages_count,

            COALESCE(
                SUM(
                    CASE
                        WHEN ch.role='user'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS user_messages,

            COALESCE(
                SUM(
                    CASE
                        WHEN ch.role='assistant'
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            ) AS ai_messages,

            MAX(ch.created_at) AS last_chat

        FROM users u

        LEFT JOIN chats ch
            ON ch.user_id=u.id
    """

    if query:

        users = c.execute(
            base_sql
            + """
                WHERE
                    u.name LIKE ?
                    OR u.email LIKE ?

                GROUP BY
                    u.id

                ORDER BY
                    u.id DESC
            """,
            (
                f"%{query}%",
                f"%{query}%"
            )
        ).fetchall()

    else:

        users = c.execute(
            base_sql
            + """
                GROUP BY
                    u.id

                ORDER BY
                    u.id DESC
            """
        ).fetchall()

    # إحصائيات عامة
    stats = c.execute("""
        SELECT

            (
                SELECT COUNT(*)
                FROM users
                WHERE is_admin=0
            ) AS total_users,

            (
                SELECT COUNT(*)
                FROM chats
            ) AS total_messages,

            (
                SELECT COUNT(*)
                FROM users
                WHERE banned=1
                AND is_admin=0
            ) AS banned_users,

            (
                SELECT COALESCE(
                    SUM(credits),
                    0
                )
                FROM users
                WHERE is_admin=0
            ) AS total_credits,

            (
                SELECT COUNT(DISTINCT user_id)
                FROM chats
            ) AS active_chat_users

    """).fetchone()

    c.close()

    return jsonify(

        users=[
            dict(user)
            for user in users
        ],

        stats=dict(stats)

    )


# =========================================================
# إحصائيات الإدارة منفصلة
# =========================================================

@app.get("/api/admin/stats")
@admin_required
def admin_stats():

    c = db()

    stats = c.execute("""
        SELECT

            (
                SELECT COUNT(*)
                FROM users
                WHERE is_admin=0
            ) AS users,

            (
                SELECT COUNT(*)
                FROM chats
            ) AS messages,

            (
                SELECT COUNT(*)
                FROM users
                WHERE banned=1
                AND is_admin=0
            ) AS banned,

            (
                SELECT COALESCE(
                    SUM(credits),
                    0
                )
                FROM users
                WHERE is_admin=0
            ) AS credits,

            (
                SELECT COUNT(DISTINCT user_id)
                FROM chats
            ) AS active_users

    """).fetchone()

    c.close()

    return jsonify(
        stats=dict(stats)
    )


# =========================================================
# تشغيل الموقع
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
