"""Post-launch sessions.

LTI launches happen inside an LMS iframe, where third-party-cookie rules
make cookies unreliable. So a session token is accepted from three places,
in order: the `tool_session` cookie, the `X-Session-Token` header, and a
`?session=` query parameter. The token itself is 256 random bits stored
server-side in SQLite — possession is authentication, nothing is encoded
in it, and a restart does not log anyone out."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from . import config
from .db import get_conn, now_iso


def create_session(user_id: int, resource_link_id: str, consumer_guid: str,
                   is_instructor: bool) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(hours=config.SESSION_HOURS)
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO sessions
                 (token, user_id, resource_link_id, consumer_guid, is_instructor,
                  created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (token, user_id, resource_link_id, consumer_guid,
             int(is_instructor), now_iso(), expires.isoformat(timespec="seconds")),
        )
    return token


def resolve_session(request: Request):
    """Return the session row for this request, or raise 401."""
    token = (
        request.cookies.get("tool_session")
        or request.headers.get("X-Session-Token")
        or request.query_params.get("session")
    )
    if not token:
        raise HTTPException(status_code=401, detail="No session — launch this tool from your LMS.")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="Unknown session — relaunch from your LMS.")
    if row["expires_at"] < now_iso():
        raise HTTPException(status_code=401, detail="Session expired — relaunch from your LMS.")
    return row


def require_instructor(request: Request):
    session = resolve_session(request)
    if not session["is_instructor"]:
        raise HTTPException(status_code=403, detail="Instructor role required.")
    return session
