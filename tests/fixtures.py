"""Synthetic fixtures for automated tests only; never loaded by the server."""
from datetime import timedelta
from werkzeug.security import generate_password_hash
from workspace.db import connection, execute, first
from workspace.model import join, now, today

def seed_demo(*args, **kwargs):
    db = connection()
    db.execute("BEGIN IMMEDIATE")
    if first("SELECT id FROM person LIMIT 1"):
        db.commit()
        return
    pw = generate_password_hash("Demo12345!")
    users = [
        ("manager", "林悦", "主管", 1),
        ("director", "陈远", "总监", 0),
        ("lead", "沈舟", "成员", 0),
        ("member", "周宁", "成员", 0),
        ("lin", "林清", "成员", 0),
        ("xu", "许明", "成员", 0),
    ]
    for login, name, role, admin in users:
        execute(
            "INSERT INTO person(login,name,role,admin,password) VALUES(?,?,?,?,?)",
            (login, name, role, admin, pw),
        )
    samples = [
        (
            "智能检测产线升级",
            "视觉检测模块已完成联调，等待供应商补充标定报告。",
            "方案评审",
            "现场联调",
            -2,
            4,
        ),
        (
            "部门知识库建设",
            "首批工艺文档已完成分类，按计划推进试用。",
            "试用评审",
            "试点上线",
            3,
            10,
        ),
        (
            "设备点检数字化",
            "移动端点检表已定稿，本周开始班组试点。",
            "班组试运行",
            "试点验收",
            6,
            14,
        ),
        (
            "质量数据标准化",
            "数据字典已交付，遗留资料正在归档。",
            "标准评审",
            "成果交付",
            -9,
            -6,
        ),
    ]

    def offset(n):
        return (today() + timedelta(days=n)).isoformat()

    for i, (name, progress, stage, up, first_day, last_day) in enumerate(samples):
        pid = execute(
            "INSERT INTO project(name,description,progress,progress_by,progress_at,start_date,end_date,project_type) VALUES(?,?,?,?,?,?,?,?)",
            (name, progress, progress, 1, now(), offset(-20), offset(last_day), ('工程','自研','自研','工程')[i]),
        ).lastrowid
        for uid in (3, 4, 5, 6):
            join(pid, uid)
        execute(
            "UPDATE membership SET lead=1 WHERE project_id=? AND person_id=?",
            (pid, 3 + i % 3),
        )
        if i == 0:
            execute(
                "UPDATE membership SET lead=1 WHERE project_id=? AND person_id=5",
                (pid,),
            )
        mids = []
        for j, (title, n) in enumerate(
            [("项目启动", -16), (stage, first_day), (up, last_day)]
        ):
            achieved = offset(n) + "T15:00:00+08:00" if j == 0 or i == 3 else None
            mid = execute(
                "INSERT INTO milestone(project_id,name,planned,forecast,achieved,actor) VALUES(?,?,?,?,?,?)",
                (
                    pid,
                    title,
                    offset(n),
                    offset(n + 3) if i == 0 and j == 1 else None,
                    achieved,
                    3 if achieved else None,
                ),
            ).lastrowid
            mids.append(mid)
        for j, (title, state) in enumerate(
            [
                ("确认实施范围", "已完成"),
                ("整理基础资料", "已完成"),
                (
                    "完成" + stage,
                    "已完成" if i == 3 else ("受阻" if i == 0 else "进行中"),
                ),
                ("准备" + up + "材料", "已完成" if i == 3 else "未开始"),
                ("归档会议记录", "未开始"),
            ]
        ):
            mid = (
                mids[min(j, 2)]
                if j < 2
                else (mids[1] if j == 2 else (mids[2] if j == 3 else None))
            )
            done = state == "已完成"
            tid = execute(
                "INSERT INTO task(project_id,milestone_id,name,due,start_date,is_key,status,note,done_at,done_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    pid,
                    mid,
                    title,
                    offset((-15, -8, first_day, last_day, 9)[j]),
                    offset((-18, -16, -15, -12, -6)[j]),
                    int(j == 2),
                    state,
                    "等待供应商提供标定报告" if state == "受阻" else "",
                    offset(-9) if done else None,
                    3 if done else None,
                ),
            ).lastrowid
            execute("INSERT INTO assignment VALUES(?,?)", (tid, 3 + j % 4))
            if j == 2:
                execute("INSERT INTO assignment VALUES(?,4)", (tid,))
        if i == 3:
            execute(
                "UPDATE project SET closed_at=?,closed_by=1 WHERE id=?",
                (offset(-5), pid),
            )
    db.commit()
