"""Configuration. Everything comes from the environment (.env via docker
compose, or exported in your shell). Missing required values stop the app
at import time — a half-configured LTI tool fails in confusing ways later,
so we fail loudly now."""

import os


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name} — copy .env.example to .env and fill it in."
        )
    return value


LAMB_API_BASE = _required("LAMB_API_BASE").rstrip("/")
LAMB_API_KEY = _required("LAMB_API_KEY")
LTI_CONSUMER_KEY = _required("LTI_CONSUMER_KEY")
LTI_SECRET = _required("LTI_SECRET")
PUBLIC_BASE_URL = _required("PUBLIC_BASE_URL").rstrip("/")

TOOL_DB_PATH = os.getenv("TOOL_DB_PATH", "data/tool.db")
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))

# OAuth 1.0 replay protection: how far a launch timestamp may drift, and
# how long we remember nonces (must be >= the drift window).
LTI_TIMESTAMP_WINDOW_SECONDS = 300
LTI_NONCE_TTL_SECONDS = 900
