"""End-to-end LTI launch tests against a live server. No LMS and no LAMB
required — we act as the LMS (sign a launch) and only exercise the launch +
session + rejection paths.

Run:  .venv/bin/python tests/test_lti_launch.py
"""

import base64
import hashlib
import hmac
import os
import sys
import time
import urllib.parse
import uuid

import httpx

BASE = os.getenv("TOOL_BASE", "http://localhost:8080")
CONSUMER_KEY = os.getenv("LTI_CONSUMER_KEY", "lamb")
SECRET = os.getenv("LTI_SECRET", "test-secret-123")
LAUNCH_URL = f"{os.getenv('PUBLIC_BASE_URL', BASE)}/lti/launch"


def sign(params, url, secret):
    filtered = {k: v for k, v in params.items() if k != "oauth_signature"}
    enc = urllib.parse.urlencode(sorted(filtered.items()), quote_via=urllib.parse.quote)
    base = "&".join(["POST", urllib.parse.quote(url, safe=""), urllib.parse.quote(enc, safe="")])
    digest = hmac.new(f"{secret}&".encode(), base.encode(), hashlib.sha1)
    return base64.b64encode(digest.digest()).decode()


def launch_params(roles, **extra):
    p = {
        "lti_message_type": "basic-lti-launch-request",
        "lti_version": "LTI-1p0",
        "oauth_consumer_key": CONSUMER_KEY,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
        "resource_link_id": "res-link-1",
        "context_id": "course-1",
        "context_title": "Test Course",
        "tool_consumer_instance_guid": "moodle.test",
        "user_id": "user-abc",
        "roles": roles,
        "lis_person_name_full": "Test Person",
        "lis_person_contact_email_primary": "test@example.com",
        "lis_result_sourcedid": "sourced-xyz",
        "lis_outcome_service_url": "http://moodle.test/outcomes",
    }
    p.update(extra)
    p["oauth_signature"] = sign(p, LAUNCH_URL, SECRET)
    return p


results = []


def check(name, cond):
    results.append((name, cond))
    print(("PASS" if cond else "FAIL"), name)


# 1. Valid instructor launch -> 303 to /setup (no activity yet)
with httpx.Client(follow_redirects=False) as c:
    r = c.post(f"{BASE}/lti/launch", data=launch_params("Instructor"))
    check("instructor launch -> 303", r.status_code == 303)
    check("instructor -> /setup", "/setup" in r.headers.get("location", ""))

# 2. Forged signature -> 401
with httpx.Client(follow_redirects=False) as c:
    bad = launch_params("Instructor")
    bad["oauth_signature"] = "totally-wrong"
    r = c.post(f"{BASE}/lti/launch", data=bad)
    check("forged signature -> 401", r.status_code == 401)

# 3. Forged role escalation without re-signing -> 401
with httpx.Client(follow_redirects=False) as c:
    tampered = launch_params("Learner")
    tampered["roles"] = "Instructor"  # change a signed field, don't re-sign
    r = c.post(f"{BASE}/lti/launch", data=tampered)
    check("tampered role -> 401", r.status_code == 401)

# 4. Replayed nonce -> first ok, second 401
with httpx.Client(follow_redirects=False) as c:
    p = launch_params("Instructor")
    r1 = c.post(f"{BASE}/lti/launch", data=p)
    r2 = c.post(f"{BASE}/lti/launch", data=p)  # identical nonce+sig
    check("replay: first ok", r1.status_code == 303)
    check("replay: second -> 401", r2.status_code == 401)

# 5. Stale timestamp -> 401
with httpx.Client(follow_redirects=False) as c:
    p = launch_params("Instructor", oauth_timestamp=str(int(time.time()) - 10000))
    p["oauth_signature"] = sign(p, LAUNCH_URL, SECRET)
    r = c.post(f"{BASE}/lti/launch", data=p)
    check("stale timestamp -> 401", r.status_code == 401)

# 6. Student launch before setup -> 303 to /waiting
with httpx.Client(follow_redirects=False) as c:
    r = c.post(f"{BASE}/lti/launch", data=launch_params("Learner"))
    check("student before setup -> /waiting", "/waiting" in r.headers.get("location", ""))

# 7. Session works: instructor reaches /setup HTML with the token
with httpx.Client(follow_redirects=False) as c:
    r = c.post(f"{BASE}/lti/launch", data=launch_params("Instructor"))
    token = r.headers["location"].split("session=")[1]
    r2 = c.get(f"{BASE}/setup", headers={"X-Session-Token": token})
    check("setup page reachable with session", r2.status_code == 200 and "set up" in r2.text.lower())

# 8. No session -> 401 on protected page
with httpx.Client() as c:
    r = c.get(f"{BASE}/setup")
    check("no session -> 401", r.status_code == 401)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
