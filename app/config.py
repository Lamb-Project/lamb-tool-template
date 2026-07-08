"""Configuration.

Two tiers:
  - BOOT config (here, from the environment): things needed before the app
    can serve anything, or that describe the deployment topology — the admin
    credentials, the public URL, the database path. Missing required boot
    values stop the app at import time.
  - RUNTIME config (app/settings_store.py, in the database): the LAMB URL +
    key and the LTI consumer key + secret, set by the admin through the
    /admin page. These can change without redeploying and are NOT required
    at boot — an unconfigured tool simply rejects launches until the admin
    fills them in.

For convenience (docker, CI, tests) the runtime values MAY be pre-seeded
from the environment on first boot — see settings_store.seed_from_env().
Once set via the admin page, the stored value wins over the environment."""

import os


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name} — copy .env.example to .env and fill it in."
        )
    return value


# --- boot config (required) --------------------------------------------------
ADMIN_USERNAME = _required("ADMIN_USERNAME")
ADMIN_PASSWORD = _required("ADMIN_PASSWORD")
# Public URL of THIS tool as the LMS reaches it. Required behind a reverse
# proxy: the OAuth signature is computed over the URL the LMS used, and the
# admin page shows "{PUBLIC_BASE_URL}/lti/launch" as the tool URL to register.
PUBLIC_BASE_URL = _required("PUBLIC_BASE_URL").rstrip("/")

# --- boot config (optional) --------------------------------------------------
TOOL_DB_PATH = os.getenv("TOOL_DB_PATH", "data/tool.db")
SESSION_HOURS = int(os.getenv("SESSION_HOURS", "8"))
ADMIN_SESSION_HOURS = int(os.getenv("ADMIN_SESSION_HOURS", "12"))

# OAuth 1.0 replay protection: how far a launch timestamp may drift, and how
# long we remember nonces (must be >= the drift window).
LTI_TIMESTAMP_WINDOW_SECONDS = 300
LTI_NONCE_TTL_SECONDS = 900

# The LTI launch endpoint the admin registers in the LMS.
LTI_LAUNCH_URL = f"{PUBLIC_BASE_URL}/lti/launch"
