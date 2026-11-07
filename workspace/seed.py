"""Initialize an empty installation with one administrator."""
import os
from getpass import getpass
from pathlib import Path
from werkzeug.security import generate_password_hash
from .db import connection, execute, first

def seed():
    db = connection()
    db.execute("BEGIN IMMEDIATE")
    if first("SELECT id FROM person LIMIT 1"):
        db.commit()
        return
    password = os.environ.get("SHANQUE_ADMIN_PASSWORD")
    if password == "CHANGE_ME_BEFORE_STARTING":
        raise ValueError("请先在 compose.yaml 中设置 manager 初始密码。")
    if not password:
        password_file = os.environ.get("SHANQUE_ADMIN_PASSWORD_FILE")
        if password_file:
            password = Path(password_file).read_text(encoding="utf-8").rstrip("\r\n")
        else:
            password = getpass("首次部署，请设置 manager 管理员密码（8 至 128 位）：")
            if password != getpass("再次输入管理员密码："):
                raise ValueError("两次输入不一致。")
    if not 8 <= len(password) <= 128:
        raise ValueError("管理员密码长度应为 8 至 128 位。")
    execute("INSERT INTO person(login,name,role,admin,password) VALUES(?,?,?,?,?)",
            ("manager", "管理员", "主管", 1, generate_password_hash(password)))
    db.commit()
