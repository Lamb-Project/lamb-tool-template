# Developing without a real Moodle

You don't need Atenea to build on this template. The LAMB Project ships a
local **test LMS** — a mock LTI 1.1 Tool Consumer that launches your tool
and receives the grades you pass back.

## The test LMS

[`lamb-lti-test-tool`](https://github.com/Lamb-Project/lamb-lti-test-tool)
stands in for Moodle: it builds a signed LTI launch, POSTs it to your tool,
and exposes an outcomes endpoint that logs the grades your tool sends.

```bash
git clone https://github.com/Lamb-Project/lamb-lti-test-tool
cd lamb-lti-test-tool
pip install -r requirements.txt
python app.py            # test LMS on http://localhost:8000
```

In its web UI, register a tool server pointing at this template's launch
endpoint (`http://localhost:8080/lti/launch`) with a consumer key and
secret. Put the **same** key and secret in this template's `.env`
(`LTI_CONSUMER_KEY` / `LTI_SECRET`) — the signature only verifies when both
sides share the secret.

Then launch as an instructor to reach `/setup`, and as a student to reach
`/chat`. Grades you send from the dashboard land in the test LMS's outcome
log.

## The self-contained test suite

For fast iteration on the launch/security layer, `tests/test_lti_launch.py`
is its own mock LMS — it signs launches in-process, so it needs nothing
running but this tool:

```bash
# tool running on :8080, .env loaded
.venv/bin/python tests/test_lti_launch.py
```

Use the test suite for the LTI/session logic; use `lamb-lti-test-tool` when
you want to click through the real launch → chat → grade flow in a browser,
or to exercise the actual `replaceResult` round-trip.

## The full-stack browser test

`tests/e2e_full.py` drives the entire loop with a real (headless) browser:
it registers this tool in `lamb-lti-test-tool`, launches as an instructor
(setup → pick a LAMB assistant → dashboard), launches as a student (chat →
send a message → assistant streams a reply from LAMB), grades the student,
and confirms the mock LMS received the grade via `replaceResult`.

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium         # ~150 MB, one-time

# with LAMB up, this tool up on :8090, and the mock LMS up:
uvicorn app:app --port 8001                    # in /opt/lamb-lti-test-tool
python tests/e2e_full.py                        # writes /tmp/e2e-*.png
```

Two things it configures for you:

- It **probes LAMB** and picks an assistant that actually answers (skipping
  image-generation assistants), so the chat has a text reply to show.
- It gives the chat a generous timeout — LAMB assistants call real LLMs and
  a full streamed reply can take a minute or more.

> **Port note:** the mock LMS defaults to `:8000`, which on a LAMB dev box
> collides with GLM's `llama-server`. Run it on `:8001`
> (`uvicorn app:app --port 8001`) — that's what `tests/e2e_full.py` expects.

## The one gotcha: PUBLIC_BASE_URL

The OAuth signature is computed over the URL the LMS used to reach your
tool. If the test LMS launches `http://localhost:8080/lti/launch`, then
`PUBLIC_BASE_URL=http://localhost:8080` in your `.env`. Behind Docker or a
proxy where the internal and external URLs differ, set `PUBLIC_BASE_URL` to
the **external** one, or every launch fails signature validation.
