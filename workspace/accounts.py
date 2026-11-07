from .presentation import render_page
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl import Workbook, load_workbook
from werkzeug.security import check_password_hash, generate_password_hash

from .db import execute, first
from .model import people
from .views import field

users = Blueprint("users", __name__)


@users.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = first(
            "SELECT * FROM person WHERE login=? AND active=1", (field("login", 80),)
        )
        if not u or not check_password_hash(
            u["password"], request.form.get("password", "")
        ):
            flash("账号或密码不正确，或账号已停用。")
            return render_page("login.html"), 401
        session.clear()
        session.update(uid=u["id"], version=u["version"])
        return redirect(url_for("work.overview"))
    return render_page("login.html")


@users.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("users.login"))


def admin():
    if not g.user["admin"]:
        abort(403, "此操作需由账号管理员办理。")


def password_hash(value):
    if not 8 <= len(value) <= 128:
        abort(400, "密码长度应为 8 至 128 位。")
    return generate_password_hash(value)


@users.route("/password", methods=["GET", "POST"])
def password():
    if request.method == "POST":
        u = first("SELECT password FROM person WHERE id=?", (g.user["id"],))
        if not check_password_hash(u["password"], request.form.get("old", "")):
            abort(400, "当前密码不正确。")
        execute(
            "UPDATE person SET password=?,version=version+1 WHERE id=?",
            (password_hash(request.form.get("password", "")), g.user["id"]),
        )
        session.clear()
        flash("密码已更新，请重新登录")
        return redirect(url_for("users.login"))
    return render_page("password.html")


@users.get("/accounts")
def accounts():
    admin()
    return render_page("accounts.html", staff=people())


def new_user(login, name, role, pw):
    if (
        not login
        or len(login) > 80
        or not name
        or len(name) > 80
        or role not in ("主管", "总监", "成员")
    ):
        abort(400, "请检查账号、姓名和角色（主管、总监或成员）。")
    if first("SELECT id FROM person WHERE login=?", (login,)):
        abort(409, "账号已存在：" + login)
    execute(
        "INSERT INTO person(login,name,role,password) VALUES(?,?,?,?)",
        (login, name, role, password_hash(pw)),
    )


@users.post("/accounts/save")
def save():
    admin()
    uid = request.form.get("id", type=int)
    name = field("name", 80)
    pw = request.form.get("password", "")
    if not uid:
        new_user(field("login", 80), name, request.form.get("role", "成员"), pw)
    else:
        role = request.form.get("role", "成员")
        if role not in ("总监", "主管", "成员"):
            abort(400)
        u = first("SELECT * FROM person WHERE id=?", (uid,))
        if not u:
            abort(404)
        active = int(request.form.get("active") == "1")
        if u["admin"] and not active:
            abort(409, "请保留指定账号管理员的登录权限。")
        execute(
            "UPDATE person SET name=?,role=?,active=?,version=version+1 WHERE id=?",
            (name, role, active, uid),
        )
        if pw:
            execute("UPDATE person SET password=? WHERE id=?", (password_hash(pw), uid))
        if uid == g.user["id"]:
            session["version"] = u["version"] + 1
    flash("人员账号已保存")
    return redirect(url_for("users.accounts"))


@users.post("/accounts/admin")
def set_admin():
    admin()
    uid = request.form.get("id", type=int)
    value = request.form.get("admin")
    if value not in ("0", "1"):
        abort(400)
    user = first("SELECT * FROM person WHERE id=?", (uid,))
    if not user:
        abort(404)
    enabled = int(value)
    if enabled and not user["active"]:
        abort(409, "请先启用该账户。")
    if not enabled and user["admin"] and user["active"]:
        if not first("SELECT id FROM person WHERE admin=1 AND active=1 AND id<>?", (uid,)):
            abort(409, "系统至少需要保留一位启用的管理员。")
    execute("UPDATE person SET admin=? WHERE id=?", (enabled, uid))
    flash("管理员权限已更新")
    return redirect(url_for("work.overview" if uid == g.user["id"] and not enabled else "users.accounts"))


@users.post("/accounts/password")
def reset_password():
    admin()
    uid = request.form.get("id", type=int)
    user = first("SELECT id,version FROM person WHERE id=?", (uid,))
    if not user:
        abort(404)
    hashed = password_hash(request.form.get("password", ""))
    execute("UPDATE person SET password=?,version=version+1 WHERE id=?", (hashed, uid))
    if uid == g.user["id"]:
        session["version"] = user["version"] + 1
    flash("密码已更新")
    return redirect(url_for("users.accounts"))


@users.get("/accounts/template.xlsx")
def template():
    admin()
    book = Workbook()
    book.active.append(["账号", "姓名", "初始密码"])
    data = BytesIO()
    book.save(data)
    data.seek(0)
    return send_file(data, download_name="用户账户导入模板.xlsx", as_attachment=True)


@users.post("/accounts/import")
def upload():
    admin()
    file = request.files.get("file")
    if not file:
        abort(400, "请选择 Excel 文件。")
    try:
        data = BytesIO(file.read())
        with ZipFile(data) as archive:
            if sum(i.file_size for i in archive.infolist()) > 12 * 1024 * 1024:
                abort(400, "工作簿过大，请分批导入。")
        book = load_workbook(data, read_only=True, data_only=True)
        try:
            sheet = book.active
            lines = iter(sheet.values)
            header = tuple(next(lines, ()))
            if header not in (("账号", "姓名", "初始密码"), ("账号", "姓名", "角色", "初始密码")):
                abort(400, "列名与导入模板不一致，请使用此页提供的模板。")
            count = 0
            for line in lines:
                if not any(line):
                    continue
                if len(line) != len(header) or count >= 500:
                    abort(400, "每批最多导入 500 人，请检查文件格式。")
                values = [str(cell).strip() if cell is not None else "" for cell in line]
                if len(values) == 3:
                    values.insert(2, "成员")
                new_user(*values)
                count += 1
        finally:
            book.close()
    except (ValueError, BadZipFile, KeyError, OSError):
        abort(400, "文件读取失败，请使用有效的 xlsx 工作簿。")
    flash(f"已导入 {count} 个账号")
    return redirect(url_for("users.accounts"))
