import hmac
import secrets
import sqlite3
from pathlib import Path

from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
    jsonify,
    get_flashed_messages,
)

from . import db, model


def create_app(config=None, *, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    root = Path(app.instance_path)
    root.mkdir(parents=True, exist_ok=True)
    keyfile = root / "local.key"
    if not keyfile.exists():
        try:
            with keyfile.open("xb") as f:
                f.write(secrets.token_bytes(32))
        except FileExistsError:
            pass
    app.config.update(
        SECRET_KEY=keyfile.read_bytes(),
        DATABASE=str(root / "workspace.sqlite3"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
    from .database_config import database_config
    app.config.update(database_config(overrides=config))
    from .presentation import DIST, frontend, wants_json, context
    app.config.setdefault("FRONTEND_ENABLED", DIST.joinpath("index.html").exists() and not app.testing)
    from .accounts import users
    from .views import bp
    from .teams import teams

    app.register_blueprint(bp)
    app.register_blueprint(users)
    app.register_blueprint(teams)
    app.register_blueprint(frontend)
    app.teardown_appcontext(db.close)
    with app.app_context():
        db.initialize()
        from .seed import seed

        seed()
        db.initialize_teams()

    @app.before_request
    def prepare():
        if request.endpoint is None:
            abort(404)
        if request.endpoint in ("static", "frontend.assets"):
            return
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        if request.method == "POST":
            if not hmac.compare_digest(
                session["csrf"].encode(), request.form.get("csrf", "").encode()
            ):
                abort(400, "页面已过期，请刷新后再提交。")
            if request.endpoint not in ("users.login", "users.logout"):
                try:
                    db.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as exc:
                    if exc.sqlite_errorcode & 255 == sqlite3.SQLITE_BUSY:
                        abort(503, "当前保存请求较多，请稍后重试。")
                    raise
        elif request.method == "GET":
            db.execute("BEGIN")
        uid = session.get("uid")
        g.user = (
            db.first(
                "SELECT id,name,role,admin,login,version FROM person WHERE id=? AND active=1 AND version=?",
                (uid, session.get("version")),
            )
            if uid
            else None
        )
        if not g.user and request.endpoint not in ("users.login", "frontend.session_info"):
            if uid:
                session.pop("uid", None)
                session.pop("version", None)
            if wants_json():
                return jsonify(message="请先登录。"), 401
            return redirect(url_for("users.login"))
        g.teams = model.user_teams(g.user["id"]) if g.user else []
        selected = request.args.get("team", type=int) if request.method == "GET" else None
        if selected is not None and not any(t["id"] == selected for t in g.teams):
            abort(403, "你尚未加入此团队。")
        selected = selected if selected is not None else session.get("team_id")
        g.team = next((t for t in g.teams if t["id"] == selected), g.teams[0] if g.teams else None)
        if g.user:
            g.user["role"] = g.team["role"] if g.team else None
            if g.team and session.get("team_id") != g.team["id"]:
                session["team_id"] = g.team["id"]
        if (request.method == "POST" and request.endpoint != "teams.switch"
                and request.form.get("source") != "todo" and "team_context" in request.form
                and request.form["team_context"] != str(g.team["id"] if g.team else "")):
            abort(409, "当前团队已切换，请刷新页面后再提交。")

    @app.after_request
    def finish(response):
        conn = g.get("db")
        if conn and conn.in_transaction:
            if response.status_code < 400:
                conn.commit()
            else:
                conn.rollback()
        if wants_json() and response.status_code in (301, 302, 303):
            response = jsonify(redirect=response.location, messages=get_flashed_messages(), context=context())
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(503)
    @app.errorhandler(413)
    @app.errorhandler(401)
    def problem(err):
        if wants_json():
            return jsonify(message=err.description, project=g.get("conflict_project"),
                           team=g.get("conflict_team")), err.code
        if app.config["FRONTEND_ENABLED"]:
            from .presentation import render_page
            return render_page("error.html", error=err), err.code
        return render_template("error.html", error=err), err.code

    app.jinja_env.globals.update(
        days=model.days, delta=model.delta, today=model.today, statuses=model.STATUSES
    )
    return app
