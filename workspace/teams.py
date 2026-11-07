from .presentation import render_page
from flask import Blueprint, abort, flash, g, redirect, request, session, url_for

from .accounts import admin
from .db import execute, first, rows
from .model import people, team_people
from .views import field

teams = Blueprint("teams", __name__)
ROLES = ("成员", "主管", "总监")


def team_record(tid):
    team = first("SELECT * FROM team WHERE id=?", (tid,))
    if not team:
        abort(404)
    return team


@teams.post("/teams/switch")
def switch():
    tid = request.form.get("team_id", type=int)
    if not any(t["id"] == tid for t in g.teams):
        abort(403, "你尚未加入此团队。")
    session["team_id"] = tid
    target = request.form.get("next")
    if target not in ("work.overview", "work.gantt", "work.todo", "teams.members"):
        target = "work.overview"
    return redirect(url_for(target))


@teams.get("/teams")
def index():
    admin()
    items = rows("""SELECT t.*,
        (SELECT COUNT(*) FROM team_member m WHERE m.team_id=t.id) AS members,
        (SELECT COUNT(*) FROM project_team p WHERE p.team_id=t.id) AS projects
        FROM team t ORDER BY t.id""")
    return render_page("teams.html", teams=items, staff=people(True))


@teams.post("/teams/save")
def save():
    admin()
    tid = request.form.get("id", type=int)
    name = field("name", 80)
    if first("SELECT id FROM team WHERE name=? AND id!=?", (name, tid or 0)):
        abort(409, "团队名称已存在。")
    if tid:
        team_record(tid)
        execute("UPDATE team SET name=? WHERE id=?", (name, tid))
    else:
        uid = request.form.get("supervisor", type=int)
        if not first("SELECT id FROM person WHERE id=? AND active=1", (uid,)):
            abort(400, "请从用户账户中选择一位团队主管。")
        tid = execute("INSERT INTO team(name) VALUES(?)", (name,)).lastrowid
        execute("INSERT INTO team_member VALUES(?,?,'主管')", (tid, uid))
    flash("团队已保存")
    return redirect(url_for("teams.detail", tid=tid))


@teams.get("/teams/<int:tid>")
def detail(tid):
    admin()
    team = team_record(tid)
    projects = rows(
        "SELECT p.* FROM project p JOIN project_team pt ON pt.project_id=p.id "
        "WHERE pt.team_id=? ORDER BY p.id", (tid,)
    )
    available_projects = rows(
        "SELECT p.id,p.name FROM project p WHERE NOT EXISTS("
        "SELECT 1 FROM project_team pt WHERE pt.project_id=p.id AND pt.team_id=?) ORDER BY p.id", (tid,)
    )
    return render_page("team_detail.html", team=team, staff=team_people(tid),
                           available=available_people(tid), projects=projects,
                           available_projects=available_projects, roles=ROLES, can_manage=True)


def available_people(tid):
    return rows(
        "SELECT id,name,login FROM person p WHERE active=1 AND NOT EXISTS("
        "SELECT 1 FROM team_member m WHERE m.team_id=? AND m.person_id=p.id) ORDER BY id", (tid,)
    )


@teams.get("/team/members")
def members():
    if not g.team:
        abort(403, "请联系管理员加入团队。")
    can_manage = g.user["admin"] or g.user["role"] == "主管"
    return render_page("team_members.html", team=g.team, staff=team_people(g.team["id"]),
                           available=available_people(g.team["id"]) if can_manage else [],
                           roles=ROLES, can_manage=can_manage)


@teams.post("/teams/<int:tid>/members")
def save_member(tid):
    team_record(tid)
    if not g.user["admin"] and not (g.team and g.team["id"] == tid and g.user["role"] == "主管"):
        abort(403, "此操作需由管理员或当前团队主管办理。")
    uid = request.form.get("person_id", type=int)
    member = first("SELECT * FROM team_member WHERE team_id=? AND person_id=?", (tid, uid))
    if request.form.get("remove"):
        if not member:
            abort(404)
        if not g.user["admin"] and member["role"] != "成员":
            abort(403, "团队总监和主管由管理员调整。")
        if first(
            """SELECT p.id FROM project p JOIN project_team pt ON pt.project_id=p.id
               WHERE pt.team_id=? AND (
                 EXISTS(SELECT 1 FROM membership m WHERE m.project_id=p.id AND m.person_id=? AND m.lead=1)
                 OR EXISTS(SELECT 1 FROM task t JOIN assignment a ON a.task_id=t.id
                           WHERE t.project_id=p.id AND a.person_id=? AND t.status!='已完成'))
               AND NOT EXISTS(SELECT 1 FROM project_team other JOIN team_member tm ON tm.team_id=other.team_id
                              WHERE other.project_id=p.id AND tm.person_id=? AND tm.team_id!=?)""",
            (tid, uid, uid, uid, tid)
        ):
            abort(409, "此人员仍负责团队内项目或有未完成任务，请先调整项目负责人和待办人。")
        execute("DELETE FROM team_member WHERE team_id=? AND person_id=?", (tid, uid))
    else:
        if not first("SELECT id FROM person WHERE id=? AND active=1", (uid,)):
            abort(400, "请选择有效的用户账户。")
        role = request.form.get("role", "成员")
        if role not in ROLES:
            abort(400, "请选择有效的团队角色。")
        if not g.user["admin"] and (member or role != "成员"):
            abort(403, "团队角色由管理员设置。")
        execute("INSERT INTO team_member VALUES(?,?,?) "
                "ON CONFLICT(team_id,person_id) DO UPDATE SET role=excluded.role", (tid, uid, role))
    flash("团队人员已更新")
    return redirect(url_for("teams.detail", tid=tid) if request.form.get("source") == "team-admin"
                    and g.user["admin"] else url_for("teams.members"))


@teams.post("/teams/<int:tid>/projects")
def link_project(tid):
    admin()
    team_record(tid)
    pid = request.form.get("project_id", type=int)
    if not first("SELECT id FROM project WHERE id=?", (pid,)):
        abort(404)
    if request.form.get("remove"):
        if not first("SELECT team_id FROM project_team WHERE project_id=? AND team_id!=?", (pid, tid)):
            abort(409, "项目至少需要归属一个团队。")
        execute("DELETE FROM project_team WHERE project_id=? AND team_id=?", (pid, tid))
        if first(
            """SELECT m.person_id FROM membership m WHERE m.project_id=? AND (
                 m.lead=1 OR EXISTS(SELECT 1 FROM assignment a JOIN task t ON t.id=a.task_id
                                   WHERE a.person_id=m.person_id AND t.project_id=m.project_id AND t.status!='已完成'))
               AND NOT EXISTS(SELECT 1 FROM project_team pt JOIN team_member tm ON tm.team_id=pt.team_id
                              WHERE pt.project_id=m.project_id AND tm.person_id=m.person_id)""", (pid,)
        ):
            abort(409, "请先将项目负责人和未完任务待办人加入项目的其他团队，或重新分派工作。")
    else:
        execute("INSERT OR IGNORE INTO project_team VALUES(?,?)", (pid, tid))
    flash("团队项目已更新")
    return redirect(url_for("teams.detail", tid=tid))
