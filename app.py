import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-in-production")

DB = "zolak.db"


# =========================
# قاعدة البيانات
# =========================

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

    # إضافة banned لو قاعدة البيانات القديمة ما فيها العمود
    columns = [
        x["name"]
        for x in c.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "banned" not in columns:
        c.execute(
            "ALTER TABLE users ADD COLUMN banned INTEGER DEFAULT 0"
        )

    # إنشاء المدير إذا غير موجود
    admin = c.execute(
        "SELECT id FROM users WHERE is_admin=1 LIMIT 1"
    ).fetchone()

    if not admin:
        c.execute("""
            INSERT INTO users
            (name,email,password,credits,is_admin,banned)
            VALUES(?,?,?,?,?,?)
        """, (
            "مدير زولك",
            "admin@zolak.ai",
            "admin123",
            9999,
            1,
            0
        ))

    # الإعدادات الافتراضية
    settings = [
        ("site_name", "زولك AI 🇸🇩"),
        ("free_credits", "10"),
        ("welcome", "أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة.")
    ]

    for key, value in settings:
        c.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value)
        )

    c.commit()
    c.close()


def setting(key, default=""):
    c = db()

    row = c.execute(
        "SELECT value FROM settings WHERE key=?",
        (key,)
    ).fetchone()

    c.close()

    if row:
        return row["value"]

    return default


init_db()


# =========================
# الحماية
# =========================

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):

        if "uid" not in session:
            return jsonify(
                error="لازم تسجل دخول أولاً."
            ), 401

        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):

        if not session.get("admin"):
            return jsonify(
                error="غير مصرح لك."
            ), 403

        return fn(*args, **kwargs)

    return wrapper


# =========================
# الصفحات
# =========================

@app.get("/")
def home():

    return render_template(
        "index.html",
        site_name=setting("site_name")
    )


@app.get("/login")
def login():

    return render_template("login.html")


@app.get("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================
# التسجيل
# =========================

@app.post("/api/register")
def register():

    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or not email or len(password) < 4:

        return jsonify(
            error="أدخل البيانات كاملة، وكلمة المرور 4 أحرف على الأقل."
        ), 400

    try:
        free = int(
            setting("free_credits", "10")
        )
    except:
        free = 10

    c = db()

    try:

        c.execute("""
            INSERT INTO users
            (name,email,password,credits,banned)
            VALUES(?,?,?,?,?)
        """, (
            name,
            email,
            password,
            free,
            0
        ))

        c.commit()

    except sqlite3.IntegrityError:

        c.close()

        return jsonify(
            error="الإيميل مستخدم قبل كده."
        ), 409

    user = c.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    ).fetchone()

    c.close()

    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(user["is_admin"])

    return jsonify(
        ok=True
    )


# =========================
# تسجيل الدخول
# =========================

@app.post("/api/login")
def api_login():

    data = request.get_json() or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    c = db()

    user = c.execute("""
        SELECT *
        FROM users
        WHERE email=? AND password=?
    """, (
        email,
        password
    )).fetchone()

    c.close()

    if not user:

        return jsonify(
            error="الإيميل أو كلمة المرور غلط."
        ), 401

    if user["banned"] and not user["is_admin"]:

        return jsonify(
            error="الحساب موقوف حالياً. تواصل مع إدارة زولك."
        ), 403

    session["uid"] = user["id"]
    session["name"] = user["name"]
    session["admin"] = bool(user["is_admin"])

    return jsonify(
        ok=True
    )


# =========================
# بيانات المستخدم
# =========================

@app.get("/api/me")
def me():

    if "uid" not in session:

        return jsonify(
            logged_in=False
        )

    c = db()

    user = c.execute("""
        SELECT name,email,credits,is_admin,banned
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


# =========================
# المحادثة مع Gemini
# =========================

@app.post("/api/chat")
@login_required
def chat():

    data = request.get_json() or {}

    message = data.get("message", "").strip()

    if not message:

        return jsonify(
            error="اكتب رسالتك أولاً."
        ), 400

    c = db()

    user = c.execute("""
        SELECT credits,banned,is_admin
        FROM users
        WHERE id=?
    """, (
        session["uid"],
    )).fetchone()

    if not user:

        c.close()

        return jsonify(
            error="الحساب غير موجود."
        ), 404

    if user["banned"] and not user["is_admin"]:

        c.close()

        return jsonify(
            error="حسابك موقوف حالياً."
        ), 403

    if user["credits"] <= 0 and not user["is_admin"]:

        c.close()

        return jsonify(
            error="رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"
        ), 402

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:

        c.close()

        return jsonify(
            error="مفتاح Gemini لم تتم إضافته في الاستضافة."
        ), 503

    try:

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key
        )

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=message,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "أنت زولك AI 🇸🇩، مساعد ذكاء اصطناعي سوداني ودود. "
                    "أجب بوضوح وباختصار مناسب. "
                    "استخدم اللهجة السودانية عندما يطلبها المستخدم. "
                    "لا تدّعي أنك إنسان."
                )
            )
        )

        answer = response.text

        if not answer:

            raise Exception(
                "Gemini لم يرجع نصاً."
            )

        # المستخدم العادي يخسر محاولة
        if not user["is_admin"]:

            c.execute("""
                UPDATE users
                SET credits = credits - 1
                WHERE id=? AND credits > 0
            """, (
                session["uid"],
            ))

        # حفظ الرسائل
        c.execute("""
            INSERT INTO chats
            (user_id,role,content)
            VALUES(?,?,?)
        """, (
            session["uid"],
            "user",
            message
        ))

        c.execute("""
            INSERT INTO chats
            (user_id,role,content)
            VALUES(?,?,?)
        """, (
            session["uid"],
            "assistant",
            answer
        ))

        c.commit()
        c.close()

        return jsonify(
            answer=answer
        )

    except Exception as e:

        c.rollback()
        c.close()

        return jsonify(
            error=f"حصلت مشكلة: {str(e)}"
        ), 500


# =========================
# سجل المحادثات
# =========================

@app.get("/api/chats")
@login_required
def chats():

    c = db()

    rows = c.execute("""
        SELECT role,content,created_at
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


# =========================
# لوحة المدير
# =========================

@app.get("/admin")
@admin_required
def admin():

    c = db()

    users = c.execute("""
        SELECT id,name,email,credits,is_admin,banned
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
        WHERE banned=1 AND is_admin=0
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
        free=setting("free_credits", "10"),
        welcome=setting("welcome"),
        rights="© 2026 منذر السيد — جميع الحقوق محفوظة"
    )


# =========================
# إعدادات زولك
# =========================

@app.post("/api/admin/settings")
@admin_required
def admin_settings():

    data = request.get_json() or {}

    c = db()

    if "free_credits" in data:

        try:
            free = int(data["free_credits"])

            if free < 0:
                free = 0

        except:
            free = 10

        c.execute("""
            INSERT OR REPLACE INTO settings(key,value)
            VALUES(?,?)
        """, (
            "free_credits",
            str(free)
        ))

    if "welcome" in data:

        c.execute("""
            INSERT OR REPLACE INTO settings(key,value)
            VALUES(?,?)
        """, (
            "welcome",
            str(data["welcome"])
        ))

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================
# ⭐ إضافة الرصيد
# =========================

@app.post("/api/admin/user/<int:uid>/credits")
@admin_required
def add_credits(uid):

    data = request.get_json(silent=True) or {}

    try:
        amount = int(
            data.get("amount", 0)
        )
    except:

        return jsonify(
            error="قيمة الرصيد غير صحيحة."
        ), 400

    if amount <= 0:

        return jsonify(
            error="أدخل رقم أكبر من صفر."
        ), 400

    c = db()

    user = c.execute("""
        SELECT id,name,email,credits,is_admin
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

    # منع تعديل رصيد المدير من زر المستخدمين
    if user["is_admin"]:

        c.close()

        return jsonify(
            error="لا يمكن تعديل رصيد المدير من هنا."
        ), 403

    # إضافة الرصيد
    c.execute("""
        UPDATE users
        SET credits = credits + ?
        WHERE id=? AND is_admin=0
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

    # قراءة الرصيد الجديد للتأكد
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
        message="تمت إضافة الرصيد بنجاح.",
        credits=updated["credits"]
    )


# =========================
# حظر المستخدم
# =========================

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
        WHERE id=? AND is_admin=0
    """, (
        uid,
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================
# إلغاء الحظر
# =========================

@app.post("/api/admin/user/<int:uid>/unban")
@admin_required
def unban_user(uid):

    c = db()

    c.execute("""
        UPDATE users
        SET banned=0
        WHERE id=? AND is_admin=0
    """, (
        uid,
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================
# حذف المستخدم
# =========================

@app.delete("/api/admin/user/<int:uid>")
@admin_required
def delete_user(uid):

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
            error="لا يمكن حذف حساب المدير."
        ), 403

    # حذف محادثات المستخدم
    c.execute("""
        DELETE FROM chats
        WHERE user_id=?
    """, (
        uid,
    ))

    # حذف المستخدم
    c.execute("""
        DELETE FROM users
        WHERE id=? AND is_admin=0
    """, (
        uid,
    ))

    c.commit()
    c.close()

    return jsonify(
        ok=True
    )


# =========================
# البحث عن المستخدمين
# =========================

@app.get("/api/admin/users")
@admin_required
def admin_users():

    query = request.args.get(
        "q",
        ""
    ).strip()

    c = db()

    if query:

        users = c.execute("""
            SELECT id,name,email,credits,is_admin,banned
            FROM users
            WHERE name LIKE ?
               OR email LIKE ?
            ORDER BY id DESC
        """, (
            f"%{query}%",
            f"%{query}%"
        )).fetchall()

    else:

        users = c.execute("""
            SELECT id,name,email,credits,is_admin,banned
            FROM users
            ORDER BY id DESC
        """).fetchall()

    c.close()

    return jsonify(
        users=[
            dict(user)
            for user in users
        ]
    )


# =========================
# تشغيل الموقع
# =========================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(
            os.getenv("PORT", "5000")
        )
    )
