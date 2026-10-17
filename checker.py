"""Runs one check of one monitor and records what happened."""
import time

import config
import db
from fetcher import FetchFailed, classify, fetch_page
from normalize import content_hash, normalize
from safety import UnsafeURL, validate_url


def _log(conn, monitor_id, outcome, started, detail=""):
    conn.execute(
        "INSERT INTO checks (monitor_id, checked_at, outcome, duration_ms, detail) VALUES (?,?,?,?,?)",
        (monitor_id, db.now(), outcome, int((time.monotonic() - started) * 1000), detail),
    )


def _fail(conn, monitor, state, reason, started):
    conn.execute(
        "UPDATE monitors SET status=?, last_checked=?, last_error=?, consecutive_failures=consecutive_failures+1 WHERE id=?",
        (state, db.now(), reason, monitor["id"]),
    )
    _log(conn, monitor["id"], state, started, reason)
    return {"outcome": state, "changed": False, "detail": reason}


def run_check(monitor_id: int, fetch=fetch_page) -> dict:
    """Fetch the page once.

    A new snapshot (text + screenshot) is stored ONLY when the content hash
    differs from the latest one. Outages and CAPTCHAs never create snapshots.
    `fetch` can be swapped out in tests.
    """
    started = time.monotonic()
    with db.connect() as conn:
        monitor = conn.execute("SELECT * FROM monitors WHERE id=?", (monitor_id,)).fetchone()
        if monitor is None:
            raise KeyError(monitor_id)

        try:
            validate_url(monitor["url"])
            result = fetch(monitor["url"])
            validate_url(result.final_url)  # a redirect must not lead somewhere private
        except UnsafeURL as e:
            return _fail(conn, monitor, "blocked", str(e), started)
        except FetchFailed as e:
            return _fail(conn, monitor, "error", str(e), started)

        state, reason = classify(result)
        if state != "ok":
            return _fail(conn, monitor, state, reason, started)

        text = normalize(result.text)
        digest = content_hash(text)
        last = conn.execute(
            "SELECT content_hash FROM snapshots WHERE monitor_id=? ORDER BY id DESC LIMIT 1",
            (monitor_id,),
        ).fetchone()

        changed = last is not None and last["content_hash"] != digest
        outcome = "unchanged"
        if last is None or changed:
            outcome = "changed" if changed else "baseline"
            cur = conn.execute(
                "INSERT INTO snapshots (monitor_id, content_hash, text, title, created_at) VALUES (?,?,?,?,?)",
                (monitor_id, digest, text, result.title, db.now()),
            )
            shot_dir = config.SHOTS_DIR / str(monitor_id)
            shot_dir.mkdir(parents=True, exist_ok=True)
            (shot_dir / f"{cur.lastrowid}.png").write_bytes(result.screenshot)

        conn.execute(
            "UPDATE monitors SET status='ok', last_checked=?, last_error=NULL, consecutive_failures=0,"
            " last_changed=CASE WHEN ? THEN ? ELSE last_changed END WHERE id=?",
            (db.now(), changed, db.now(), monitor_id),
        )
        _log(conn, monitor_id, outcome, started)
        return {"outcome": outcome, "changed": changed, "detail": ""}
