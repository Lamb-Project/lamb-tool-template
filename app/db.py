"""SQLite storage. Plain sqlite3 from the standard library — no ORM, so the
whole persistence story is readable in this one file.

Multi-LMS safety: every LMS-scoped table carries `consumer_guid`
(tool_consumer_instance_guid from the launch), so two Moodles can host the
same tool without their resource_link ids colliding."""

import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lti_user_id TEXT NOT NULL,
    consumer_guid TEXT NOT NULL DEFAULT '',
    username TEXT,
    full_name TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (lti_user_id, consumer_guid)
);

CREATE TABLE IF NOT EXISTS activities (
    resource_link_id TEXT NOT NULL,
    consumer_guid TEXT NOT NULL DEFAULT '',
    context_id TEXT,
    context_title TEXT,
    title TEXT NOT NULL,
    assistant_model TEXT NOT NULL,
    assistant_name TEXT,
    grading_enabled INTEGER NOT NULL DEFAULT 0,
    min_turns INTEGER NOT NULL DEFAULT 3,
    created_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (resource_link_id, consumer_guid)
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    resource_link_id TEXT NOT NULL,
    consumer_guid TEXT NOT NULL DEFAULT '',
    is_instructor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lti_nonces (
    nonce TEXT PRIMARY KEY,
    seen_at INTEGER NOT NULL
);

-- Runtime configuration set on the /admin page (see settings_store.py).
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Admin console sessions (separate from LTI sessions).
CREATE TABLE IF NOT EXISTS admin_sessions (
    token TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- Grade-passback plumbing captured at launch time, per user per activity.
CREATE TABLE IF NOT EXISTS enrollments (
    user_id INTEGER NOT NULL REFERENCES users(id),
    resource_link_id TEXT NOT NULL,
    consumer_guid TEXT NOT NULL DEFAULT '',
    lis_result_sourcedid TEXT,
    lis_outcome_service_url TEXT,
    first_launch_at TEXT NOT NULL,
    last_launch_at TEXT NOT NULL,
    PRIMARY KEY (user_id, resource_link_id, consumer_guid)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    resource_link_id TEXT NOT NULL,
    consumer_guid TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_thread
    ON messages (user_id, resource_link_id, consumer_guid, id);

CREATE TABLE IF NOT EXISTS grades (
    user_id INTEGER NOT NULL REFERENCES users(id),
    resource_link_id TEXT NOT NULL,
    consumer_guid TEXT NOT NULL DEFAULT '',
    proposed_score REAL,
    score REAL,
    feedback TEXT,
    sent_to_lms INTEGER NOT NULL DEFAULT 0,
    sent_at TEXT,
    PRIMARY KEY (user_id, resource_link_id, consumer_guid)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.TOOL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    os.makedirs(os.path.dirname(config.TOOL_DB_PATH) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(_SCHEMA)


# --- users -------------------------------------------------------------------

def upsert_user(lti_user_id: str, consumer_guid: str, username: str,
                full_name: str, email: str) -> int:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (lti_user_id, consumer_guid, username, full_name, email, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (lti_user_id, consumer_guid) DO UPDATE SET
                 username = excluded.username,
                 full_name = excluded.full_name,
                 email = excluded.email""",
            (lti_user_id, consumer_guid, username, full_name, email, now_iso()),
        )
        row = conn.execute(
            "SELECT id FROM users WHERE lti_user_id = ? AND consumer_guid = ?",
            (lti_user_id, consumer_guid),
        ).fetchone()
        return row["id"]


# --- nonces (OAuth replay protection) ---------------------------------------

def check_and_store_nonce(nonce: str) -> bool:
    """True if the nonce is fresh; False if it was already used (replay)."""
    now = int(time.time())
    with get_conn() as conn:
        conn.execute("DELETE FROM lti_nonces WHERE seen_at < ?",
                     (now - config.LTI_NONCE_TTL_SECONDS,))
        try:
            conn.execute("INSERT INTO lti_nonces (nonce, seen_at) VALUES (?, ?)",
                         (nonce, now))
            return True
        except sqlite3.IntegrityError:
            return False


# --- admin sessions -----------------------------------------------------------

def create_admin_session(token: str, expires_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO admin_sessions (token, created_at, expires_at) VALUES (?, ?, ?)",
            (token, now_iso(), expires_at),
        )


def get_admin_session(token: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM admin_sessions WHERE token = ?", (token,)
        ).fetchone()


def delete_admin_session(token: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))


# --- activities ---------------------------------------------------------------

def get_activity(resource_link_id: str, consumer_guid: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM activities WHERE resource_link_id = ? AND consumer_guid = ?",
            (resource_link_id, consumer_guid),
        ).fetchone()


def save_activity(resource_link_id: str, consumer_guid: str, context_id: str,
                  context_title: str, title: str, assistant_model: str,
                  assistant_name: str, grading_enabled: bool, min_turns: int,
                  created_by: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO activities
                 (resource_link_id, consumer_guid, context_id, context_title, title,
                  assistant_model, assistant_name, grading_enabled, min_turns,
                  created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (resource_link_id, consumer_guid) DO UPDATE SET
                 title = excluded.title,
                 assistant_model = excluded.assistant_model,
                 assistant_name = excluded.assistant_name,
                 grading_enabled = excluded.grading_enabled,
                 min_turns = excluded.min_turns""",
            (resource_link_id, consumer_guid, context_id, context_title, title,
             assistant_model, assistant_name, int(grading_enabled), min_turns,
             created_by, now_iso()),
        )


# --- enrollments (grade plumbing) ---------------------------------------------

def upsert_enrollment(user_id: int, resource_link_id: str, consumer_guid: str,
                      lis_result_sourcedid: str, lis_outcome_service_url: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO enrollments
                 (user_id, resource_link_id, consumer_guid,
                  lis_result_sourcedid, lis_outcome_service_url,
                  first_launch_at, last_launch_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (user_id, resource_link_id, consumer_guid) DO UPDATE SET
                 lis_result_sourcedid = COALESCE(NULLIF(excluded.lis_result_sourcedid, ''),
                                                 enrollments.lis_result_sourcedid),
                 lis_outcome_service_url = COALESCE(NULLIF(excluded.lis_outcome_service_url, ''),
                                                    enrollments.lis_outcome_service_url),
                 last_launch_at = excluded.last_launch_at""",
            (user_id, resource_link_id, consumer_guid,
             lis_result_sourcedid, lis_outcome_service_url, now_iso(), now_iso()),
        )


# --- messages -----------------------------------------------------------------

def add_message(user_id: int, resource_link_id: str, consumer_guid: str,
                role: str, content: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO messages (user_id, resource_link_id, consumer_guid, role, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, resource_link_id, consumer_guid, role, content, now_iso()),
        )


def get_messages(user_id: int, resource_link_id: str, consumer_guid: str, limit: int = 200):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT role, content, created_at FROM messages
               WHERE user_id = ? AND resource_link_id = ? AND consumer_guid = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, resource_link_id, consumer_guid, limit),
        ).fetchall()
        return list(reversed(rows))


# --- grades + participant roster ------------------------------------------------

def participants(resource_link_id: str, consumer_guid: str):
    """Roster for the instructor dashboard: everyone who launched, their turn
    count, and their grade row if any."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT u.id AS user_id, u.full_name, u.email,
                      e.lis_result_sourcedid,
                      (SELECT COUNT(*) FROM messages m
                        WHERE m.user_id = u.id
                          AND m.resource_link_id = e.resource_link_id
                          AND m.consumer_guid = e.consumer_guid
                          AND m.role = 'user') AS user_turns,
                      g.proposed_score, g.score, g.feedback, g.sent_to_lms, g.sent_at
               FROM enrollments e
               JOIN users u ON u.id = e.user_id
               LEFT JOIN grades g ON g.user_id = e.user_id
                 AND g.resource_link_id = e.resource_link_id
                 AND g.consumer_guid = e.consumer_guid
               WHERE e.resource_link_id = ? AND e.consumer_guid = ?
               ORDER BY u.full_name""",
            (resource_link_id, consumer_guid),
        ).fetchall()


def set_grade(user_id: int, resource_link_id: str, consumer_guid: str,
              score: float, feedback: str, proposed_score=None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO grades (user_id, resource_link_id, consumer_guid,
                                   proposed_score, score, feedback, sent_to_lms)
               VALUES (?, ?, ?, ?, ?, ?, 0)
               ON CONFLICT (user_id, resource_link_id, consumer_guid) DO UPDATE SET
                 proposed_score = COALESCE(excluded.proposed_score, grades.proposed_score),
                 score = excluded.score,
                 feedback = excluded.feedback,
                 sent_to_lms = 0""",
            (user_id, resource_link_id, consumer_guid, proposed_score, score, feedback),
        )


def mark_grade_sent(user_id: int, resource_link_id: str, consumer_guid: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE grades SET sent_to_lms = 1, sent_at = ?
               WHERE user_id = ? AND resource_link_id = ? AND consumer_guid = ?""",
            (now_iso(), user_id, resource_link_id, consumer_guid),
        )


def gradable_rows(resource_link_id: str, consumer_guid: str):
    """Grades with a final score, not yet sent, whose enrollment has passback
    plumbing (sourcedid + outcome URL)."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT g.user_id, g.score, g.feedback,
                      e.lis_result_sourcedid, e.lis_outcome_service_url
               FROM grades g
               JOIN enrollments e ON e.user_id = g.user_id
                 AND e.resource_link_id = g.resource_link_id
                 AND e.consumer_guid = g.consumer_guid
               WHERE g.resource_link_id = ? AND g.consumer_guid = ?
                 AND g.score IS NOT NULL AND g.sent_to_lms = 0
                 AND e.lis_result_sourcedid IS NOT NULL
                 AND e.lis_outcome_service_url IS NOT NULL""",
            (resource_link_id, consumer_guid),
        ).fetchall()
