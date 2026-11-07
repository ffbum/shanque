"""Shared page data for the React client and legacy HTML callers."""
from datetime import date
from pathlib import Path

from flask import Blueprint, current_app, g, get_flashed_messages, jsonify, render_template, request, send_from_directory, session

frontend = Blueprint("frontend", __name__)
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def wants_json():
    return "application/json" in request.headers.get("Accept", "")


def context():
    from .model import today
    return dict(user=g.get("user"), team=g.get("team"), teams=g.get("teams", []),
                csrf=session.get("csrf"), today=today().isoformat(),
                server_mode=current_app.config.get("SERVER_MODE", False))


def json_dates(value):
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_dates(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_dates(item) for item in value]
    return value


def render_page(template, **data):
    if wants_json():
        return jsonify(data=json_dates(data), context=context(), messages=get_flashed_messages())
    if current_app.config["FRONTEND_ENABLED"]:
        return send_from_directory(DIST, "index.html")
    return render_template(template, **data)


@frontend.get("/api/session")
def session_info():
    return jsonify(context())


@frontend.get("/assets/<path:filename>")
def assets(filename):
    return send_from_directory(DIST, filename)
