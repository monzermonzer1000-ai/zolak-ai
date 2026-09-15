import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-in-production")
DB = "zolak.db"

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=db()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        credits INTEGER DEFAULT 10, is_admin INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chats(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, role TEXT,
        content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT)""")
    if not c.execute("SELECT 1 FROM users WHERE is_admin=1").fetchone():
        c.execute("INSERT OR IGNORE INTO users(name,email,password,credits,is_admin) VALUES(?,?,?,?,1)",
                  ("مدير زولك","admin@zolak.ai","admin123",9999,1))
    for k,v in [("site_name","زولك AI 🇸🇩"),("free_credits","10"),
                ("welcome","أها يا زول 👋❤️ زولك جاهز يساعدك في أي حاجة.")]:
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",(k,v))
    c.commit(); c.close()

def setting(k, default=""):
    c=db(); r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone(); c.close()
    return r["value"] if r else default

def login_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if "uid" not in session: return jsonify(error="لازم تسجل دخول أولاً."),401
        return fn(*a,**kw)
    return w

def admin_required(fn):
    @wraps(fn)
    def w(*a,**kw):
        if not session.get("admin"): return redirect("/login")
        return fn(*a,**kw)
    return w

init_db()

@app.get("/")
def home(): return render_template("index.html", site_name=setting("site_name"))

@app.get("/login")
def login(): return render_template("login.html")

@app.post("/api/register")
def register():
    d=request.get_json() or {}; name=d.get("name","").strip(); email=d.get("email","").strip().lower(); pw=d.get("password","")
    if not name or not email or len(pw)<4: return jsonify(error="أدخل البيانات كاملة، وكلمة المرور 4 أحرف على الأقل."),400
    c=db()
    try:
        c.execute("INSERT INTO users(name,email,password,credits) VALUES(?,?,?,?)",(name,email,pw,int(setting("free_credits","10")))); c.commit()
    except sqlite3.IntegrityError: c.close(); return jsonify(error="الإيميل مستخدم قبل كده."),409
    u=c.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone(); c.close()
    session.update(uid=u["id"],name=u["name"],admin=bool(u["is_admin"]))
    return jsonify(ok=True)

@app.post("/api/login")
def api_login():
    d=request.get_json() or {}; email=d.get("email","").strip().lower(); pw=d.get("password","")
    c=db(); u=c.execute("SELECT * FROM users WHERE email=? AND password=?",(email,pw)).fetchone(); c.close()
    if not u: return jsonify(error="الإيميل أو كلمة المرور غلط."),401
    session.update(uid=u["id"],name=u["name"],admin=bool(u["is_admin"]))
    return jsonify(ok=True)

@app.get("/logout")
def logout(): session.clear(); return redirect("/")

@app.get("/api/me")
def me():
    if "uid" not in session: return jsonify(logged_in=False)
    c=db(); u=c.execute("SELECT name,email,credits,is_admin FROM users WHERE id=?",(session["uid"],)).fetchone(); c.close()
    return jsonify(logged_in=True, **dict(u))

@app.post("/api/chat")
@login_required
def chat():
    d=request.get_json() or {}; msg=d.get("message","").strip()
    if not msg: return jsonify(error="اكتب رسالتك أولاً."),400
    c=db(); u=c.execute("SELECT credits FROM users WHERE id=?",(session["uid"],)).fetchone()
    if u["credits"]<=0: c.close(); return jsonify(error="رصيدك المجاني خلص. قريباً نضيف باقات زولك بلس ❤️"),402
    key=os.getenv("OPENAI_API_KEY")
    if not key: c.close(); return jsonify(error="زولك جاهز، لكن مفتاح الذكاء الاصطناعي لم تتم إضافته في الاستضافة بعد."),503
    try:
        from openai import OpenAI
        client=OpenAI(api_key=key)
        r=client.responses.create(model=os.getenv("OPENAI_MODEL","gpt-5"),
            instructions="أنت زولك AI، مساعد سوداني ودود. أجب بوضوح. استخدم السوداني عند طلبه. لا تدّعي أنك إنسان.",
            input=msg)
        ans=r.output_text
        c.execute("UPDATE users SET credits=credits-1 WHERE id=?",(session["uid"],))
        c.execute("INSERT INTO chats(user_id,role,content) VALUES(?,?,?)",(session["uid"],"user",msg))
        c.execute("INSERT INTO chats(user_id,role,content) VALUES(?,?,?)",(session["uid"],"assistant",ans))
        c.commit(); c.close(); return jsonify(answer=ans)
    except Exception:
        c.close(); return jsonify(error="حصلت مشكلة في خدمة الذكاء الاصطناعي. جرّب تاني."),500

@app.get("/api/chats")
@login_required
def chats():
    c=db(); rows=c.execute("SELECT role,content,created_at FROM chats WHERE user_id=? ORDER BY id DESC LIMIT 50",(session["uid"],)).fetchall(); c.close()
    return jsonify(chats=[dict(x) for x in reversed(rows)])

@app.get("/admin")
@admin_required
def admin():
    c=db(); users=c.execute("SELECT id,name,email,credits,is_admin FROM users ORDER BY id DESC").fetchall()
    total=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]; msgs=c.execute("SELECT COUNT(*) n FROM chats").fetchone()["n"]; c.close()
    return render_template("admin.html", users=users,total=total,msgs=msgs,free=setting("free_credits","10"))

@app.post("/api/admin/settings")
@admin_required
def admin_settings():
    d=request.get_json() or {}; c=db()
    for k in ["free_credits","welcome"]:
        if k in d: c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(k,str(d[k])))
    c.commit(); c.close(); return jsonify(ok=True)

@app.post("/api/admin/user/<int:uid>/credits")
@admin_required
def add_credits(uid):
    n=int((request.get_json() or {}).get("amount",10)); c=db(); c.execute("UPDATE users SET credits=credits+? WHERE id=?",(n,uid)); c.commit(); c.close(); return jsonify(ok=True)

if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
