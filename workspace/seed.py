"""Initialize an empty installation with one administrator."""
from getpass import getpass
from werkzeug.security import generate_password_hash
from .db import connection, execute, first

def seed():
    db = connection()
    db.execute("BEGIN IMMEDIATE")
    if first("SELECT id FROM person LIMIT 1"):
        db.commit()
        return
    password = getpass("首次部署，请设置 manager 管理员密码（8 至 128 位）：")
    if not 8 <= len(password) <= 128 or password != getpass("再次输入管理员密码："):
        raise ValueError("密码长度不符或两次输入不一致。")
    execute("INSERT INTO person(login,name,role,admin,password) VALUES(?,?,?,?,?)",
            ("manager", "管理员", "主管", 1, generate_password_hash(password)))
    db.commit()
