"""HTTP API. The dashboard talks to this."""
import os

from flask import Flask, abort, jsonify, request, send_from_directory

import config
import db
from checker import run_check
from safety import UnsafeURL, validate_url


def create_app() -> Flask:
    app = Flask(__name__)
    db.init()

    def monitor_json(row):
        return {k: row[k] for k in row.keys()}

    @app.get("/")
    def home():
        return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "index.html")

    @app.post("/api/monitors")
    def add_monitor():
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()[:80]
        try:
            interval = int(data.get("interval_min", 60))
        except (TypeError, ValueError):
            return jsonify(error="interval_min must be a number"), 400
        if not name:
            return jsonify(error="Give the monitor a name"), 400
        if not config.MIN_INTERVAL_MIN <= interval <= config.MAX_INTERVAL_MIN:
            return jsonify(error=f"Interval must be between {config.MIN_INTERVAL_MIN} minutes and 24 hours"), 400
        try:
            url = validate_url(data.get("url"))
        except UnsafeURL as e:
            return jsonify(error=str(e)), 400
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO monitors (name, url, interval_min, created_at) VALUES (?,?,?,?)",
                (name, url, interval, db.now()),
            )
            row = conn.execute("SELECT * FROM monitors WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(monitor_json(row)), 201

    @app.get("/api/monitors")
    def list_monitors():
        with db.connect() as conn:
            rows = conn.execute("SELECT * FROM monitors ORDER BY id DESC").fetchall()
        return jsonify([monitor_json(r) for r in rows])

    @app.delete("/api/monitors/<int:mid>")
    def delete_monitor(mid):
        with db.connect() as conn:
            conn.execute("DELETE FROM monitors WHERE id=?", (mid,))
        return "", 204

    @app.post("/api/monitors/<int:mid>/check")
    def check_now(mid):
        try:
            return jsonify(run_check(mid))
        except KeyError:
            abort(404)

    @app.get("/api/monitors/<int:mid>/snapshots")
    def snapshots(mid):
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT id, content_hash, title, created_at, length(text) AS chars FROM snapshots"
                " WHERE monitor_id=? ORDER BY id DESC",
                (mid,),
            ).fetchall()
        return jsonify([{k: r[k] for k in r.keys()} for r in rows])

    @app.get("/api/monitors/<int:mid>/checks")
    def checks(mid):
        with db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM checks WHERE monitor_id=? ORDER BY id DESC LIMIT 200", (mid,)
            ).fetchall()
        return jsonify([{k: r[k] for k in r.keys()} for r in rows])

    @app.get("/shots/<int:mid>/<int:sid>.png")
    def shot(mid, sid):
        return send_from_directory(config.SHOTS_DIR / str(mid), f"{sid}.png")

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
