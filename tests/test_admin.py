"""Admin console tests against a live server.

Run:  .venv/bin/python tests/test_admin.py
Needs ADMIN_USERNAME / ADMIN_PASSWORD matching the server's .env.
"""

import os
import sys

import httpx

BASE = os.getenv("TOOL_BASE", "http://localhost:8080")
USER = os.getenv("ADMIN_USERNAME", "admin")
PW = os.getenv("ADMIN_PASSWORD", "s3cret-admin")

results = []


def check(name, cond):
    results.append((name, cond))
    print(("PASS" if cond else "FAIL"), name)


# 1. /admin without login -> redirect to login
with httpx.Client(follow_redirects=False) as c:
    r = c.get(f"{BASE}/admin")
    check("anon /admin -> 303 login", r.status_code == 303 and "/admin/login" in r.headers.get("location", ""))

# 2. Bad credentials -> 401
with httpx.Client(follow_redirects=False) as c:
    r = c.post(f"{BASE}/admin/login", data={"username": USER, "password": "wrong"})
    check("bad creds -> 401", r.status_code == 401)

# 3. Settings POST without admin session -> 401
with httpx.Client(follow_redirects=False) as c:
    r = c.post(f"{BASE}/admin/settings", data={"lamb_api_base": "http://evil"})
    check("unauth settings -> 401", r.status_code == 401)

# 4. Good login -> cookie, then /admin shows the LTI launch URL
with httpx.Client(follow_redirects=False) as c:
    r = c.post(f"{BASE}/admin/login", data={"username": USER, "password": PW})
    check("login -> 303 + cookie", r.status_code == 303 and "admin_session" in r.cookies)
    r2 = c.get(f"{BASE}/admin")
    check("admin page shows LTI launch URL", r2.status_code == 200 and "/lti/launch" in r2.text)

    # 5. Save settings (change LAMB base), confirm it persists in the form
    r3 = c.post(f"{BASE}/admin/settings", data={
        "lamb_api_base": "http://localhost:9099",
        "lti_consumer_key": "lamb",
        "lamb_api_key": "",   # blank = keep existing
        "lti_secret": "",     # blank = keep existing
    })
    check("save settings -> 303", r3.status_code == 303)
    r4 = c.get(f"{BASE}/admin")
    check("saved value visible", "http://localhost:9099" in r4.text)

    # 6. Secret shown as set, never echoed
    check("secret not echoed", "test-secret-123" not in r4.text)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
