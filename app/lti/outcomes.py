"""LTI 1.1 Basic Outcomes — grade passback (replaceResult POX).

Ported from LAMBA's lti_service.py, which is a correct, Moodle-tested
implementation. The signing here is the OUTBOUND direction (we sign a
request TO the LMS), distinct from validation.py which verifies inbound
launches. Kept in its own module so it can be lifted whole into another
tool.

Score convention: callers pass 0..1 (already normalized). The POX carries
resultScore as a 0..1 float per the spec."""

import base64
import hashlib
import hmac
import time
import urllib.parse
import uuid
from xml.sax.saxutils import escape

import httpx

from .. import config


def _oauth_escape(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~-._")


def _normalize_url(url: str) -> str:
    p = urllib.parse.urlparse(url)
    scheme = p.scheme.lower()
    netloc = p.hostname.lower() if p.hostname else ""
    port = p.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{netloc}:{port}"
    return f"{scheme}://{netloc}{p.path or '/'}"


def _sign(method: str, url: str, params: dict, consumer_secret: str) -> str:
    encoded = sorted((_oauth_escape(k), _oauth_escape(v)) for k, v in params.items())
    normalized_params = "&".join(f"{k}={v}" for k, v in encoded)
    base_string = "&".join([
        method.upper(),
        _oauth_escape(_normalize_url(url)),
        _oauth_escape(normalized_params),
    ])
    signing_key = f"{_oauth_escape(consumer_secret)}&"
    digest = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1)
    return base64.b64encode(digest.digest()).decode()


def _outcome_xml(sourcedid: str, score_0_1: float, comment: str) -> str:
    message_id = str(uuid.uuid4())
    score = max(0.0, min(1.0, float(score_0_1)))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<imsx_POXEnvelopeRequest xmlns="http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">
    <imsx_POXHeader>
        <imsx_POXRequestHeaderInfo>
            <imsx_version>V1.0</imsx_version>
            <imsx_messageIdentifier>{escape(message_id)}</imsx_messageIdentifier>
        </imsx_POXRequestHeaderInfo>
    </imsx_POXHeader>
    <imsx_POXBody>
        <replaceResultRequest>
            <resultRecord>
                <sourcedGUID>
                    <sourcedId>{escape(sourcedid)}</sourcedId>
                </sourcedGUID>
                <result>
                    <resultScore>
                        <language>en</language>
                        <textString>{score}</textString>
                    </resultScore>
                    <resultData>
                        <text>{escape(comment)}</text>
                    </resultData>
                </result>
            </resultRecord>
        </replaceResultRequest>
    </imsx_POXBody>
</imsx_POXEnvelopeRequest>"""


def send_grade(sourcedid: str, outcome_url: str, score_0_1: float,
               comment: str = "") -> dict:
    """Send one replaceResult to the LMS. Returns {success, status_code, detail}."""
    xml = _outcome_xml(sourcedid, score_0_1, comment)
    body_hash = base64.b64encode(hashlib.sha1(xml.encode()).digest()).decode()

    oauth_params = {
        "oauth_consumer_key": config.LTI_CONSUMER_KEY,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_version": "1.0",
        "oauth_body_hash": body_hash,
    }
    oauth_params["oauth_signature"] = _sign("POST", outcome_url, oauth_params, config.LTI_SECRET)

    auth_header = "OAuth " + ", ".join(
        f'{k}="{_oauth_escape(v)}"' for k, v in sorted(oauth_params.items())
    )
    headers = {"Authorization": auth_header, "Content-Type": "application/xml"}

    try:
        resp = httpx.post(outcome_url, content=xml.encode(), headers=headers, timeout=30)
    except httpx.HTTPError as e:
        return {"success": False, "status_code": None, "detail": f"connection error: {e}"}

    ok = resp.status_code == 200 and "imsx_codemajor>success" in resp.text.lower()
    detail = "ok" if ok else f"http {resp.status_code}: {resp.text[:200]}"
    return {"success": ok, "status_code": resp.status_code, "detail": detail}
