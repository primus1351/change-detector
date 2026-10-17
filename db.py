"""SQLite storage. One small file, no server to run."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT    NOT NULL,
    url                   TEXT    NOT NULL,
    interval_min          INTEGER NOT NULL,
    status                TEXT    NOT NULL DEFAULT 'pending',  -- pending | ok | error | blocked
    last_checked          TEXT,
    last_changed          TEXT,
    last_error            TEXT,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id  INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    content_hash TEXT   NOT NULL,
    text        TEXT    NOT NULL,
    title       TEXT,
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_monitor ON snapshots(monitor_id, id);

-- One row per check attempt, changed or not. Feeds the seismograph trace later.
CREATE TABLE IF NOT EXISTS checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id  INTEGER NOT NULL REFERENCES monitors(id) ON DELETE CASCADE,
    checked_at  TEXT    NOT NULL,
    outcome     TEXT    NOT NULL,   -- baseline | unchanged | changed | error | blocked
    duration_ms INTEGER,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_checks_monitor ON checks(monitor_id, id);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript(SCHEMA)


@contextmanager
def connect():
    db = sqlite3.connect(config.DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    try:
        yield db
        db.commit()
    finally:
        db.close()
