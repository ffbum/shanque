from .presentation import render_page
from datetime import date

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    request,
    url_for,
)

from .db import execute, first
from .gantt import build_chart
from .model import (
    days,
    STATUSES,
    join,
    members,
    now,
    project_staff,
    summary,
    tasks,
    today,
    visible_projects,
)

bp = Blueprint("work", __name__)


def field(name, limit=160, required=True):
    value = request.form.get(name, "").strip()
    if (required and not value) or len(value) > limit:
        abort(400, "请填写必填项，并检查输入内容的长度。")
    return value


def day_field(name, required=True):
    value = field(name, 10, required)
    if not value:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        abort(400, "请选择有效日期。")


def ids(name):
    try:
        return {int(v) for v in request.form.getlist(name) if v}
    except ValueError:
        abort(400, "人员选择无效。")


def validate_staff(selected, pid=None):
    available = {u["id"] for u in project_staff(pid)}
    if not selected <= available:
        abort(400, "请选择项目所属团队内有效的主管或成员。")


def project_access(pid, write=False):
    if not g.team or not first(
        "SELECT project_id FROM project_team WHERE project_id=? AND team_id=?", (pid, g.team["id"])
    ):
        abort(403, "该项目不属于当前团队。")
    p = first("SELECT * FROM project WHERE id=?", (pid,))
    if not p:
        abort(404)
    u = g.user
    m = first(
        "SELECT lead FROM membership WHERE project_id=? AND person_id=?", (pid, u["id"])
    )
    if u["role"] == "成员" and not m:
        abort(403, "你没有该项目的访问权限。")
    manage = u["role"] == "主管" or (u["role"] == "成员" and m and m["lead"])
    if write and not manage:
        abort(403, "此操作需由主管或本项目负责人办理。")
    return p, bool(manage)


def supervisor():
    if g.user["role"] != "主管":
        abort(403, "此操作需由项目主管办理。")


def mutable(p):
    if p["closed_at"]:
        abort(409, "项目已结项，仍可更新已有任务的完成情况。")


def saved(pid, message="已保存"):
    flash(message)
    return redirect(url_for("work.project", pid=pid))


@bp.get("/")
def overview():
    projects = [summary(p) for p in visible_projects(g.user)]
    projects.sort(key=lambda p: (bool(p["closed_at"]), not p["risk"], p["id"]))
    milestones = sorted(
        [(m, p) for p in projects for m in p["upcoming"]],
        key=lambda pair: pair[0]["planned"],
    )
    filters = [("全部项目", len(projects))]
    filters.extend((state, sum(p["state"] == state for p in projects))
                   for state in ("正常推进", "需关注", "已结项"))
    metrics = [
        ("进行中项目", sum(not p["closed_at"] for p in projects)),
        ("已逾期节点", sum(len(p["overdue"]) for p in projects)),
        ("7 天内到期节点", sum(days(m["planned"]) <= 7 for m, _ in milestones)),
    ]
    return render_page("overview.html", projects=projects, up=milestones, filters=filters, metrics=metrics)


@bp.get("/gantt")
def gantt():
    projects = [summary(p) for p in visible_projects(g.user)]
    projects.sort(key=lambda p: (bool(p["closed_at"]), not p["risk"], p["id"]))
    return render_page("gantt.html", projects=projects, chart=build_chart(projects, today()))


@bp.route("/projects/new", methods=["GET", "POST"])
@bp.route("/projects/<int:pid>/edit", methods=["GET", "POST"])
def edit_project(pid=None):
    if pid is None:
        supervisor()
        p = None
    else:
        p, _ = project_access(pid, True)
        mutable(p)
    staff = project_staff(pid)
    if request.method == "POST":
        name, desc = field("name", 80), field("description", 2000, False)
        project_type = request.form.get("project_type")
        if project_type not in ("科研", "工程", "固投", "自研", "预研"):
            abort(400, "请选择项目类型：科研、工程、固投、自研或预研。")
        start = day_field("start_date", False) if "start_date" in request.form else (p or {}).get("start_date")
        end = day_field("end_date", False) if "end_date" in request.form else (p or {}).get("end_date")
        if bool(start) != bool(end) or (start and start > end):
            abort(400, "请同时填写项目开始日期和结束日期，结束日期须在开始日期当天或之后。")
        if start and pid and first(
            "SELECT id FROM milestone WHERE project_id=? AND planned<?", (pid, start)
        ):
            abort(400, "项目开始日期不能晚于首个节点的计划日。")
        if not p:
            pid = execute(
                "INSERT INTO project(name,description,start_date,end_date,project_type) VALUES (?,?,?,?,?)", (name, desc,start,end,project_type)
            ).lastrowid
            execute("INSERT INTO project_team VALUES(?,?)", (pid, g.team["id"]))
        else:
            execute(
                "UPDATE project SET name=?,description=?,start_date=?,end_date=?,project_type=? WHERE id=?", (name, desc,start,end,project_type, pid)
            )
        if g.user["role"] == "主管":
            leads = ids("leads")
            if not leads:
                abort(400, "请至少选择一位项目负责人。")
            validate_staff(leads, pid)
            execute("UPDATE membership SET lead=0 WHERE project_id=?", (pid,))
            for uid in leads:
                join(pid, uid)
                execute(
                    "UPDATE membership SET lead=1 WHERE project_id=? AND person_id=?",
                    (pid, uid),
                )
        return saved(pid)
    return render_page(
        "edit.html",
        kind="project",
        p=p,
        staff=staff,
        selected=[u["id"] for u in members(pid) if u["lead"]] if p else [],
    )


@bp.get("/projects/<int:pid>")
def project(pid):
    p, manage = project_access(pid)
    return render_page(
        "project.html", p=summary(p), manage=manage, staff=project_staff(pid)
    )


@bp.post("/projects/<int:pid>/progress")
def progress(pid):
    supervisor()
    project_access(pid)
    execute(
        "UPDATE project SET progress=?,progress_at=?,progress_by=? WHERE id=?",
        (field("progress", 600, False), now(), g.user["id"], pid),
    )
    flash("最近进展已更新")
    return redirect(url_for("work.overview"))


@bp.post("/projects/<int:pid>/members")
def membership(pid):
    p, _ = project_access(pid, True)
    mutable(p)
    remove = request.form.get("remove", type=int)
    if remove:
        member = first(
            "SELECT lead FROM membership WHERE project_id=? AND person_id=?",
            (pid, remove),
        )
        if not member or member["lead"]:
            abort(409, "请先由主管调整项目负责人。")
        outstanding = first(
            "SELECT t.id FROM task t JOIN assignment a ON a.task_id=t.id WHERE t.project_id=? AND a.person_id=? AND t.status!='已完成'",
            (pid, remove),
        )
        if outstanding:
            abort(409, "该成员还有未完成任务，请先调整待办人。")
        execute(
            "DELETE FROM membership WHERE project_id=? AND person_id=?", (pid, remove)
        )
    else:
        selected = ids("members")
        validate_staff(selected, pid)
        for uid in selected:
            join(pid, uid)
    return saved(pid, "项目成员已更新")


def check_task_revision(task):
    # Mutating routes hold BEGIN IMMEDIATE from before_request through commit.
    if request.form.get("revision") != task["revision"]:
        g.conflict_project = task["project_id"]
        abort(409, "任务已更新，或此页面版本已过期。本次提交未保存，请打开最新任务，核对后重新提交。")


def child(table, pid, key):
    if table not in ("task", "milestone"):
        raise ValueError(table)
    item = first(f"SELECT * FROM {table} WHERE project_id=? AND id=?", (pid, key))
    if not item:
        abort(404)
    return item


@bp.route("/projects/<int:pid>/milestones/new", methods=["GET", "POST"])
@bp.route("/projects/<int:pid>/milestones/<int:mid>/edit", methods=["GET", "POST"])
def milestone(pid, mid=None):
    supervisor()
    p, _ = project_access(pid)
    mutable(p)
    m = child("milestone", pid, mid) if mid else None
    if m and m["achieved"]:
        abort(409, "该节点已经达成。")
    candidates = [t for t in tasks(pid=pid) if mid and t["milestone_id"] == mid]
    if request.method == "POST":
        if request.form.get("delete"):
            execute("UPDATE task SET is_key=0 WHERE milestone_id=?", (mid,))
            execute("DELETE FROM milestone WHERE id=?", (mid,))
            return saved(pid, "节点已删除，关联任务保留在项目中")
        values = (field("name", 80), day_field("planned"), day_field("forecast", False))
        if p["start_date"] and values[1] < p["start_date"]:
            abort(400, "节点计划日不能早于项目开始日期。")
        if mid:
            execute(
                "UPDATE milestone SET name=?,planned=?,forecast=? WHERE id=?",
                (*values, mid),
            )
        else:
            mid = execute(
                "INSERT INTO milestone(name,planned,forecast,project_id) VALUES(?,?,?,?)",
                (*values, pid),
            ).lastrowid
        key = field("key", 20, False)
        execute("UPDATE task SET is_key=0 WHERE milestone_id=?", (mid,))
        if key:
            t = child("task", pid, key)
            if t["milestone_id"] != mid:
                abort(400, "请从本节点关联任务中指定节点任务。")
            execute("UPDATE task SET is_key=1 WHERE id=?", (t["id"],))
            if t["status"] == "已完成":
                execute(
                    "UPDATE milestone SET achieved=?,actor=? WHERE id=?",
                    (t["done_at"], t["done_by"], mid),
                )
        return saved(pid)
    return render_page(
        "edit.html", kind="milestone", p=p, item=m, candidates=candidates
    )


@bp.post("/projects/<int:pid>/milestones/<int:mid>/confirm")
def confirm(pid, mid):
    project_access(pid, True)
    m = child("milestone", pid, mid)
    if not m["achieved"]:
        if request.form.get("force") != "1" and first(
            "SELECT id FROM task WHERE milestone_id=? AND is_key=1", (mid,)
        ):
            abort(409, "请通过完成节点任务来达成该节点。")
        stamp, actor = now(), g.user["id"]
        changed = execute(
            """UPDATE task SET status='已完成', done_at=?, done_by=?,
                      note=CASE WHEN note='' THEN '随节点强制完成'
                                ELSE '随节点强制完成。原说明：' || note END
               WHERE project_id=? AND milestone_id=? AND status!='已完成'""",
            (stamp, actor, pid, mid),
        ).rowcount
        execute(
            "UPDATE milestone SET achieved=?,actor=? WHERE id=?",
            (stamp, actor, mid),
        )
        return saved(pid, f"节点已达成，已同步完成 {changed} 项关联任务")
    return saved(pid, "节点已达成")


@bp.route("/projects/<int:pid>/tasks/new", methods=["GET", "POST"])
@bp.route("/projects/<int:pid>/tasks/<int:tid>/edit", methods=["GET", "POST"])
def edit_task(pid, tid=None):
    p, _ = project_access(pid, True)
    mutable(p)
    t = child("task", pid, tid) if tid else None
    if request.method == "POST":
        if t:
            check_task_revision(t)
        if request.form.get("delete"):
            if not t:
                abort(400, "请选择要删除的任务。")
            if t["is_key"] and g.user["role"] != "主管":
                abort(403, "节点任务由主管维护。")
            execute("DELETE FROM task WHERE id=?", (tid,))
            return saved(pid, "任务已删除")
        mid = request.form.get("milestone_id") or None
        node = child("milestone", pid, mid) if mid else None
        mid = node["id"] if node else None
        if t and t["is_key"] and mid != t["milestone_id"]:
            abort(409, "请先由主管取消节点任务指定，再调整任务归属。")
        assigned = ids("assignees")
        validate_staff(assigned, pid)
        if not assigned:
            abort(400, "请至少选择一位待办人。")
        due = day_field("due", required=not node) or node["planned"]
        if "start_date" in request.form:
            start = day_field("start_date")
        else:
            start = t["start_date"] if t else today().isoformat()
        if start and due < start:
            abort(400, "任务截止日期不能早于开始日期。")
        values = (field("name", 120), due, mid, start)
        if tid:
            execute(
                "UPDATE task SET name=?,due=?,milestone_id=?,start_date=? WHERE id=?", (*values, tid)
            )
            execute("DELETE FROM assignment WHERE task_id=?", (tid,))
        else:
            tid = execute(
                "INSERT INTO task(name,due,milestone_id,start_date,project_id) VALUES(?,?,?,?,?)",
                (*values, pid),
            ).lastrowid
        for uid in assigned:
            join(pid, uid)
            execute("INSERT INTO assignment VALUES(?,?)", (tid, uid))
        return saved(pid, "任务已保存")
    selected = next((x["assignee_ids"] for x in tasks(pid=pid) if x["id"] == tid), [])
    return render_page(
        "task_form.html" if request.args.get("fragment") == "1" else "task_edit.html",
        p=p,
        item=t,
        ms=summary(p)["milestones"],
        staff=project_staff(pid),
        selected=selected,
    )


@bp.post("/projects/<int:pid>/tasks/<int:tid>/status")
def status(pid, tid):
    t = child("task", pid, tid)
    uid = g.user["id"]
    if request.form.get("source") == "todo":
        permitted = first(
            """SELECT a.task_id,tm.team_id FROM assignment a JOIN membership m ON m.person_id=a.person_id
               JOIN project_team pt ON pt.project_id=m.project_id
               JOIN team_member tm ON tm.team_id=pt.team_id AND tm.person_id=a.person_id
               WHERE a.task_id=? AND a.person_id=? AND m.project_id=? AND tm.role!='总监'""", (tid, uid, pid)
        )
    else:
        _, manage = project_access(pid)
        permitted = g.user["role"] != "总监" and (manage or first(
            "SELECT task_id FROM assignment WHERE task_id=? AND person_id=?", (tid, uid)))
    if not permitted:
        abort(403, "只有待办人、项目负责人或主管可以更新此任务。")
    if request.form.get("source") == "todo":
        g.conflict_team = permitted["team_id"]
    check_task_revision(t)
    state = field("status")
    if state not in STATUSES:
        abort(400, "请选择有效状态。")
    note = field("note", 600, state == "受阻")
    if t["status"] == "已完成" and state != "已完成" and t["is_key"]:
        abort(409, "节点任务已经达成节点，无法重新打开。")
    if t["status"] != "已完成" or state != "已完成" or note != t["note"]:
        done_at = (t["done_at"] or now()) if state == "已完成" else None
        actor = (t["done_by"] or uid) if done_at else None
        execute(
            "UPDATE task SET status=?,note=?,done_at=?,done_by=? WHERE id=?",
            (state, note, done_at, actor, tid),
        )
        if done_at and t["is_key"]:
            execute(
                "UPDATE milestone SET achieved=?,actor=? WHERE id=? AND achieved IS NULL",
                (done_at, actor, t["milestone_id"]),
            )
    flash("任务状态已更新")
    return redirect(
        url_for("work.todo")
        if request.form.get("source") == "todo"
        else url_for("work.project", pid=pid)
    )


@bp.post("/projects/<int:pid>/close")
def close_project(pid):
    p, _ = project_access(pid, True)
    if first(
        "SELECT id FROM milestone WHERE project_id=? AND achieved IS NULL", (pid,)
    ):
        abort(409, "请先达成全部关键节点。")
    if not p["closed_at"]:
        execute(
            "UPDATE project SET closed_at=?,closed_by=? WHERE id=?",
            (now(), g.user["id"], pid),
        )
    return saved(pid, "项目已结项，剩余任务可继续办理")


@bp.get("/todo")
def todo():
    return render_page("todo.html", items=tasks(uid=g.user["id"]), source="todo")
