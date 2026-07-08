"""Inbound LTI 1.1 launch validation — OAuth 1.0a, HMAC-SHA1.

Three checks, all mandatory, all rejecting on failure:

1. The signature: recomputed over the exact form fields and the public URL
   of the launch endpoint, compared in constant time.
2. The timestamp: must be within LTI_TIMESTAMP_WINDOW_SECONDS of now.
3. The nonce: must never have been seen inside the nonce TTL (replay
   protection, backed by the lti_nonces table).

A tool that skips any of these will accept forged launches — anyone on the
network can claim to be an Instructor with three lines of curl. Do not
weaken this module when adapting the template."""

import base64
import hashlib
import hmac
import time
import urllib.parse

from .. import config, settings_store
from ..db import check_and_store_nonce


def compute_signature(params: dict, http_method: str, base_url: str,
                      consumer_secret: str, token_secret: str = "") -> str:
    """OAuth 1.0a signature base string + HMAC-SHA1, per RFC 5849 §3.4."""
    filtered = {k: v for k, v in params.items() if k != "oauth_signature"}
    sorted_params = sorted(filtered.items())
    encoded_params = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)

    base_string = "&".join([
        http_method.upper(),
        urllib.parse.quote(base_url, safe=""),
        urllib.parse.quote(encoded_params, safe=""),
    ])

    signing_key = f"{consumer_secret}&{token_secret}"
    digest = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    return base64.b64encode(digest.digest()).decode()


def validate_launch(form: dict, launch_url: str) -> tuple[bool, str]:
    """Full launch validation. Returns (ok, reason). Reason is safe to log
    but deliberately vague in HTTP responses."""
    consumer_key = settings_store.get("lti_consumer_key")
    secret = settings_store.get("lti_secret")
    if not consumer_key or not secret:
        return False, "tool not configured (set LTI credentials at /admin)"

    if form.get("lti_message_type") != "basic-lti-launch-request":
        return False, "not a basic-lti-launch-request"
    if form.get("oauth_consumer_key") != consumer_key:
        return False, "unknown oauth_consumer_key"
    if form.get("oauth_signature_method") != "HMAC-SHA1":
        return False, "unsupported oauth_signature_method"

    try:
        ts = int(form.get("oauth_timestamp", "0"))
    except ValueError:
        return False, "malformed oauth_timestamp"
    if abs(time.time() - ts) > config.LTI_TIMESTAMP_WINDOW_SECONDS:
        return False, "oauth_timestamp outside the allowed window"

    nonce = form.get("oauth_nonce", "")
    if not nonce:
        return False, "missing oauth_nonce"

    expected = compute_signature(form, "POST", launch_url, secret)
    received = form.get("oauth_signature", "")
    if not hmac.compare_digest(expected, received):
        return False, "signature mismatch"

    # Only consume the nonce after the signature verifies, so an attacker
    # cannot burn legitimate nonces with unsigned requests.
    if not check_and_store_nonce(nonce):
        return False, "oauth_nonce replayed"

    return True, "ok"


def is_instructor(roles_str: str) -> bool:
    """LTI 1.1 role strings vary wildly between LMSes; substring matching on
    the lowercased value is the pragmatic standard."""
    if not roles_str:
        return False
    roles = roles_str.lower()
    return any(indicator in roles for indicator in (
        "instructor", "teacher", "contentdeveloper",
        "administrator", "teachingassistant",
    ))
