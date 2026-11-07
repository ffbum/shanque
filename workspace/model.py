from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .db import execute, first, rows
from flask import g

STATUSES = ("未开始", "进行中", "受阻", "已完成")
TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def today():
    return datetime.now(TZ).date()


def days(value):
    return (date.fromisoformat(value[:10]) - today()).days


def delta(a, b):
    return (date.fromisoformat(a[:10]) - date.fromisoformat(b[:10])).days


def people(active=False):
    return rows(
        "SELECT id,login,name,role,active,admin FROM person "
        + ("WHERE active=1 " if active else "")
        + "ORDER BY id"
    )


def user_teams(uid):
    return rows(
        "SELECT t.id,t.name,m.role FROM team t JOIN team_member m ON m.team_id=t.id "
        "WHERE m.person_id=? ORDER BY t.id", (uid,)
    )


def team_people(tid):
    return rows(
        "SELECT p.id,p.login,p.name,p.active,p.admin,m.role FROM person p "
        "JOIN team_member m ON m.person_id=p.id WHERE m.team_id=? ORDER BY p.id", (tid,)
    )


def project_staff(pid=None):
    if pid is None:
        return [u for u in team_people(g.team["id"]) if u["active"] and u["role"] != "总监"] if g.team else []
    return rows(
        """SELECT p.id,p.name,p.login,p.active,'成员' AS role FROM person p
           WHERE p.active=1 AND EXISTS(
               SELECT 1 FROM team_member m JOIN project_team pt ON pt.team_id=m.team_id
               WHERE pt.project_id=? AND m.person_id=p.id AND m.role!='总监')
           ORDER BY p.id""", (pid,)
    )


def members(pid):
    return rows(
        "SELECT p.id,p.name,p.active,m.lead FROM membership m JOIN person p "
        "ON p.id=m.person_id WHERE m.project_id=? ORDER BY m.lead DESC,p.id",
        (pid,),
    )


def join(pid, uid):
    execute(
        "INSERT OR IGNORE INTO membership(project_id,person_id) VALUES (?,?)",
        (pid, uid),
    )


def visible_projects(user):
    if not g.team:
        return []
    if user["role"] in ("总监", "主管"):
        return rows("SELECT p.* FROM project p JOIN project_team pt ON pt.project_id=p.id "
                    "WHERE pt.team_id=? ORDER BY p.id", (g.team["id"],))
    return rows(
        "SELECT p.* FROM project p JOIN membership m ON m.project_id=p.id "
        "JOIN project_team pt ON pt.project_id=p.id WHERE pt.team_id=? AND m.person_id=? ORDER BY p.id",
        (g.team["id"], user["id"]),
    )


def tasks(pid=None, uid=None):
    query = """SELECT t.*,p.name AS project_name,p.project_type AS project_type,m.name AS milestone_name,
                      m.planned AS planned,m.achieved AS milestone_achieved,u.name AS finisher
               FROM task t JOIN project p ON t.project_id=p.id
               LEFT JOIN milestone m ON t.milestone_id=m.id LEFT JOIN person u ON u.id=t.done_by"""
    args = ()
    if pid is not None:
        query += " WHERE t.project_id=?"
        args = (pid,)
    elif uid is not None:
        query += (
            " JOIN assignment a ON a.task_id=t.id JOIN membership visible "
            "ON visible.project_id=t.project_id AND visible.person_id=a.person_id WHERE a.person_id=?"
        )
        args = (uid,)
    result = rows(query + " ORDER BY t.due,t.id", args)
    if uid is not None:
        contexts = defaultdict(list)
        for link in rows(
            "SELECT pt.project_id,m.team_id,m.role FROM project_team pt "
            "JOIN team_member m ON pt.team_id=m.team_id WHERE m.person_id=? ORDER BY m.team_id", (uid,)
        ):
            contexts[link["project_id"]].append(link)
        result = [t for t in result if t["project_id"] in contexts]
        for t in result:
            choices = contexts[t["project_id"]]
            t["team_id"] = next((c["team_id"] for c in choices if g.team and c["team_id"] == g.team["id"]),
                                choices[0]["team_id"])
            t["can_update"] = any(c["role"] != "总监" for c in choices)
    if result:
        assignments = defaultdict(list)
        sql = "SELECT a.task_id,u.id,u.name FROM assignment a JOIN person u ON a.person_id=u.id JOIN task t ON a.task_id=t.id"
        if pid is not None:
            sql += " WHERE t.project_id=?"
        elif uid is not None:
            sql += " WHERE EXISTS(SELECT 1 FROM assignment b WHERE b.task_id=t.id AND b.person_id=?)"
        for a in rows(sql + " ORDER BY u.id", args):
            assignments[a["task_id"]].append(a)
        for t in result:
            t["assignees"] = assignments[t["id"]]
            t["assignee_ids"] = [a["id"] for a in t["assignees"]]
    return result


def summary(p):
    pid = p["id"]
    p["members"] = members(pid)
    p["leads"] = [u for u in p["members"] if u["lead"]]
    ts = tasks(pid=pid)
    ms = rows(
        "SELECT m.*,u.name AS actor_name FROM milestone m LEFT JOIN person u "
        "ON u.id=m.actor WHERE project_id=? ORDER BY planned,m.id",
        (pid,),
    )
    previous = p["start_date"]
    for m in ms:
        m["stage_start"] = previous
        previous = m["planned"]
        linked = [t for t in ts if t["milestone_id"] == m["id"]]
        m["tasks"] = linked
        m["remaining"] = [t for t in linked if t["status"] != "已完成"]
        m["key"] = next((t for t in linked if t["is_key"]), None)
    pending = [m for m in ms if not m["achieved"]]
    overdue = [m for m in pending if days(m["planned"]) < 0]
    upcoming = [m for m in pending if days(m["planned"]) >= 0]
    blocked = [t for t in ts if t["status"] == "受阻"]
    late = [t for t in ts if t["status"] != "已完成" and days(t["due"]) < 0]
    risk = bool(
        overdue
        or late
        or blocked
        or any(m["forecast"] and m["forecast"] > m["planned"] for m in pending)
    )
    state = "已结项" if p["closed_at"] else ("需关注" if risk else "正常推进")
    p.update(
        tasks=ts,
        milestones=ms,
        pending=pending,
        overdue=overdue,
        upcoming=upcoming,
        blocked=blocked,
        late=late,
        done=sum(t["status"] == "已完成" for t in ts),
        state=state,
        risk=risk,
        reached=len(ms) - len(pending),
    )
    if p["progress_by"]:
        p["editor"] = first("SELECT name FROM person WHERE id=?", (p["progress_by"],))[
            "name"
        ]
    return p
