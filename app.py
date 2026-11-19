from datetime import datetime
from contextlib import contextmanager
from functools import wraps
import csv
import hmac
import io
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import uuid

from flask import (
    Flask, Response, abort, flash, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from openpyxl import Workbook
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from grader import evaluate_answer, extract_text

ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", ROOT))


def resolve_app_data_dir(project_root=ROOT):
    if getattr(sys, "frozen", False):
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / "GradePilot"
    return project_root


APP_DATA_DIR = resolve_app_data_dir()
UPLOAD_DIR = APP_DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB = APP_DATA_DIR / "assignments.db"
ALLOWED = {"pdf", "png", "jpg", "jpeg", "webp"}

app = Flask(
    __name__,
    template_folder=str(RESOURCE_ROOT / "templates"),
    static_folder=str(RESOURCE_ROOT / "static"),
)
app.secret_key = os.environ.get("GRADEPILOT_SECRET_KEY", "local-demo-change-before-deployment")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


@contextmanager
def connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student TEXT NOT NULL, college_id TEXT NOT NULL,
            department TEXT NOT NULL, semester TEXT DEFAULT '',
            total REAL NOT NULL, topics TEXT NOT NULL, filename TEXT NOT NULL,
            extracted TEXT, suggested REAL NOT NULL, final REAL NOT NULL,
            feedback TEXT, created TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL CHECK(role IN ('teacher', 'student')),
            login_id TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            college_id TEXT NOT NULL DEFAULT '',
            kid TEXT NOT NULL DEFAULT '',
            department TEXT NOT NULL DEFAULT '',
            semester TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL
        )""")
        columns = {row["name"] for row in con.execute("PRAGMA table_info(submissions)")}
        if "kid" not in columns:
            con.execute("ALTER TABLE submissions ADD COLUMN kid TEXT NOT NULL DEFAULT ''")
        if "account_id" not in columns:
            con.execute("ALTER TABLE submissions ADD COLUMN account_id INTEGER")
        con.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_student_kid
                       ON accounts(kid) WHERE role='student' AND kid <> ''""")
        con.execute("CREATE INDEX IF NOT EXISTS idx_submissions_account ON submissions(account_id)")


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return session["_csrf_token"]


@app.before_request
def protect_post_requests():
    if request.method == "POST":
        supplied = request.form.get("_csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not hmac.compare_digest(supplied, expected):
            abort(400, description="Security token expired. Refresh the page and try again.")


@app.context_processor
def template_helpers():
    return {"csrf_token": csrf_token, "current_account": current_account()}


def current_account():
    account_id = session.get("account_id")
    if account_id is None:
        return None
    with connect() as con:
        return con.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        account = current_account()
        if account is None:
            session.clear()
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorate(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            account = current_account()
            if account["role"] != role:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorate


@app.route("/")
def index():
    account = current_account()
    if account is None:
        with connect() as con:
            has_teacher = con.execute(
                "SELECT 1 FROM accounts WHERE role='teacher' LIMIT 1"
            ).fetchone()
        return redirect(url_for("login") if has_teacher else url_for("setup"))
    if account["role"] == "student":
        return redirect(url_for("student_dashboard"))
    q = request.args.get("q", "").strip()
    dept = request.args.get("department", "").strip()
    sql = "SELECT * FROM submissions WHERE 1=1"
    args = []
    if q:
        sql += " AND (student LIKE ? OR college_id LIKE ? OR kid LIKE ? OR department LIKE ?)"
        args += [f"%{q}%"] * 4
    if dept:
        sql += " AND department = ?"
        args.append(dept)
    sql += " ORDER BY id DESC"
    with connect() as con:
        rows = con.execute(sql, args).fetchall()
        total_submissions = con.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        student_count = con.execute("SELECT COUNT(DISTINCT college_id) FROM submissions").fetchone()[0]
        departments = [r[0] for r in con.execute(
            "SELECT DISTINCT department FROM submissions WHERE department <> '' ORDER BY department"
        ).fetchall()]
    return render_template("index.html", rows=rows, q=q, department=dept,
        departments=departments, total_submissions=total_submissions, student_count=student_count)


@app.route("/setup", methods=["GET", "POST"])
def setup():
    with connect() as con:
        exists = con.execute(
            "SELECT 1 FROM accounts WHERE role='teacher' LIMIT 1"
        ).fetchone()
    if exists:
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")
        if not name or not login_id or len(password) < 8:
            flash("नाम और यूज़रनेम भरें। पासवर्ड कम से कम 8 अक्षर का होना चाहिए।", "error")
        else:
            try:
                with connect() as con:
                    con.execute("""INSERT INTO accounts
                        (role, login_id, password_hash, full_name, created)
                        VALUES ('teacher', ?, ?, ?, ?)""",
                        (login_id, generate_password_hash(password), name, datetime.now().isoformat()))
                flash("Teacher account बन गया। अब लॉगिन करें।", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("यह यूज़रनेम पहले से उपयोग में है।", "error")
    return render_template("auth.html", mode="setup")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        college_id = request.form.get("college_id", "").strip()
        kid = request.form.get("kid", "").strip()
        department = request.form.get("department", "").strip()
        semester = request.form.get("semester", "").strip()
        password = request.form.get("password", "")
        if not all([name, college_id, kid, department, semester]):
            flash("कृपया सभी student details भरें।", "error")
        elif len(password) < 8:
            flash("पासवर्ड कम से कम 8 अक्षर का होना चाहिए।", "error")
        else:
            try:
                with connect() as con:
                    con.execute("""INSERT INTO accounts
                        (role, login_id, password_hash, full_name, college_id, kid,
                         department, semester, created)
                        VALUES ('student', ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (college_id, generate_password_hash(password), name, college_id,
                         kid, department, semester, datetime.now().isoformat()))
                flash("Student account बन गया। अब College ID और password से लॉगिन करें।", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("यह College ID या KID पहले से registered है।", "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_account():
        return redirect(url_for("index"))
    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip()
        password = request.form.get("password", "")
        with connect() as con:
            account = con.execute(
                "SELECT * FROM accounts WHERE login_id=? COLLATE NOCASE", (login_id,)
            ).fetchone()
        if account and check_password_hash(account["password_hash"], password):
            session.clear()
            session["account_id"] = account["id"]
            return redirect(url_for("index"))
        flash("यूज़रनेम / College ID या password सही नहीं है।", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


def create_submission(student, college_id, kid, department, semester, topics, total, upload, account_id=None):
    if not all([student, college_id, department, topics, upload, upload.filename]):
        return "नाम, College ID, Department, Topics और assignment file जरूरी हैं।"
    extension = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    if extension not in ALLOWED:
        return "केवल PDF, PNG, JPG या WEBP फाइल अपलोड करें।"
    filename = f"{uuid.uuid4().hex}_{secure_filename(upload.filename)}"
    path = UPLOAD_DIR / filename
    upload.save(path)
    extracted, note = extract_text(path)
    result = evaluate_answer(extracted, topics, total)
    feedback = (note + " " if note else "") + result["feedback"]
    with connect() as con:
        con.execute("""INSERT INTO submissions
            (student,college_id,kid,department,semester,total,topics,filename,extracted,
             suggested,final,feedback,created,account_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (student, college_id, kid, department, semester, total, topics, filename,
             extracted, result["score"], result["score"], feedback,
             datetime.now().strftime("%d %b %Y, %I:%M %p"), account_id))
    return None


def valid_total():
    try:
        total = float(request.form.get("total", "10"))
        return total if 0 < total <= 1000 else None
    except ValueError:
        return None


def spreadsheet_value(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


@app.route("/evaluate", methods=["POST"])
@role_required("teacher")
def evaluate():
    total = valid_total()
    if total is None:
        flash("कुल अंक 1 से 1000 के बीच होने चाहिए।", "error")
        return redirect(url_for("index"))
    error = create_submission(
        request.form.get("student", "").strip(),
        request.form.get("college_id", "").strip(),
        request.form.get("kid", "").strip(),
        request.form.get("department", "").strip(),
        request.form.get("semester", "").strip(),
        request.form.get("topics", "").strip(),
        total,
        request.files.get("assignment"),
    )
    if error:
        flash(error, "error")
    else:
        flash("Assignment evaluate करके marks सुरक्षित कर दिए गए।", "success")
    return redirect(url_for("index"))


@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    account = current_account()
    with connect() as con:
        rows = con.execute(
            "SELECT * FROM submissions WHERE college_id=? ORDER BY id DESC",
            (account["college_id"],),
        ).fetchall()
    return render_template("student_dashboard.html", rows=rows, account=account)


@app.route("/student/submit", methods=["POST"])
@role_required("student")
def student_submit():
    account = current_account()
    total = valid_total()
    if total is None:
        flash("कुल अंक 1 से 1000 के बीच होने चाहिए।", "error")
        return redirect(url_for("student_dashboard"))
    error = create_submission(
        account["full_name"], account["college_id"], account["kid"],
        account["department"], account["semester"],
        request.form.get("topics", "").strip(), total,
        request.files.get("assignment"), account["id"],
    )
    if error:
        flash(error, "error")
    else:
        flash("Assignment evaluate करके आपकी history में सुरक्षित कर दिया गया।", "success")
    return redirect(url_for("student_dashboard"))


@app.route("/edit/<int:item_id>", methods=["POST"])
@role_required("teacher")
def edit(item_id):
    try:
        mark = float(request.form.get("final", ""))
    except ValueError:
        flash("कृपया सही अंक डालें।", "error")
        return redirect(request.referrer or url_for("index"))
    with connect() as con:
        row = con.execute("SELECT total FROM submissions WHERE id=?", (item_id,)).fetchone()
        if not row:
            flash("रिकॉर्ड नहीं मिला।", "error")
        elif mark < 0 or mark > row["total"]:
            flash(f"अंक 0 से {row['total']:g} के बीच होने चाहिए।", "error")
        else:
            con.execute("UPDATE submissions SET final=? WHERE id=?", (mark, item_id))
            flash("Teacher के final marks सेव हो गए।", "success")
    return redirect(request.referrer or url_for("index"))


@app.route("/student/<college_id>")
@login_required
def student_history(college_id):
    account = current_account()
    if account["role"] != "teacher" and account["college_id"] != college_id:
        abort(403)
    with connect() as con:
        rows = con.execute("SELECT * FROM submissions WHERE college_id=? ORDER BY id DESC",
                           (college_id,)).fetchall()
    if not rows:
        flash("इस College ID का रिकॉर्ड नहीं मिला।", "error")
        return redirect(url_for("index"))
    return render_template("student.html", rows=rows, student=rows[0])


@app.route("/view/<int:item_id>")
@login_required
def view(item_id):
    account = current_account()
    with connect() as con:
        row = con.execute("SELECT * FROM submissions WHERE id=?", (item_id,)).fetchone()
    if not row:
        flash("रिकॉर्ड नहीं मिला।", "error")
        return redirect(url_for("index"))
    if account["role"] != "teacher" and row["college_id"] != account["college_id"]:
        abort(403)
    return render_template("detail.html", row=row)


@app.route("/uploads/<path:filename>")
@login_required
def uploaded(filename):
    account = current_account()
    with connect() as con:
        row = con.execute("SELECT college_id FROM submissions WHERE filename=?", (filename,)).fetchone()
    if not row or (account["role"] != "teacher" and row["college_id"] != account["college_id"]):
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/export")
@role_required("teacher")
def export():
    q = request.args.get("q", "").strip()
    dept = request.args.get("department", "").strip()
    sql = """SELECT student,college_id,kid,department,semester,total,suggested,final,
                    topics,created FROM submissions WHERE 1=1"""
    args = []
    if q:
        sql += " AND (student LIKE ? OR college_id LIKE ? OR kid LIKE ? OR department LIKE ?)"
        args += [f"%{q}%"] * 4
    if dept:
        sql += " AND department=?"
        args.append(dept)
    sql += " ORDER BY department,student,id"
    with connect() as con:
        rows = con.execute(sql, args).fetchall()
    headers = ["Student Name", "College ID", "KID", "Department", "Semester",
        "Total Marks", "AI Suggested Marks", "Teacher Final Marks", "Expected Topics", "Submission Date"]
    data = [[spreadsheet_value(value) for value in headers]]
    data.extend([[spreadsheet_value(value) for value in row] for row in rows])
    if request.args.get("format") == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "GradePilot Marks"
        for line in data:
            sheet.append(line)
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        output = io.BytesIO()
        workbook.save(output)
        return Response(output.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=gradepilot_marksheet.xlsx"})
    output = io.StringIO()
    csv.writer(output).writerows(data)
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=gradepilot_marksheet.csv"})


@app.route("/delete/<int:item_id>", methods=["POST"])
@role_required("teacher")
def delete(item_id):
    with connect() as con:
        row = con.execute("SELECT filename FROM submissions WHERE id=?", (item_id,)).fetchone()
        if row:
            try:
                (UPLOAD_DIR / row["filename"]).unlink(missing_ok=True)
            except OSError:
                app.logger.exception("Could not remove upload %s", row["filename"])
            con.execute("DELETE FROM submissions WHERE id=?", (item_id,))
            flash("Submission record हटा दिया गया।", "success")
    return redirect(url_for("index"))


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(RESOURCE_ROOT / "static", "manifest.webmanifest",
                              mimetype="application/manifest+json")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(RESOURCE_ROOT / "static", "icon.svg", mimetype="image/svg+xml")


@app.route("/sw.js")
def service_worker():
    response = send_from_directory(RESOURCE_ROOT / "static", "sw.js",
                                   mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/offline")
def offline():
    return render_template("offline.html")


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
