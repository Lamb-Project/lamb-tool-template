# lamb-tool-template

A minimal, well-built starting point for an educational tool that:

- is launched from your LMS (Moodle / Atenea) as an **LTI 1.1** activity,
- talks to a **LAMB assistant** as its AI engine, over LAMB's OpenAI-compatible API,
- shows students a **chatbot** and passes **grades** back to the LMS.

Clone it, change the parts you care about, deploy it. Everything is
GPL-3.0; contributors who build on this can later fold their tool back into
the LAMB ecosystem as an extension.

> This is a **template**, not a finished product. The chat UI, the grading
> policy, and the conversation flow are deliberately small and obvious so
> you can replace them. Where the code makes a security decision (LTI
> signature validation, session handling, keeping the LAMB key server-side)
> it is not negotiable — see [SECURITY](#security).

## What you get

| Piece | File | Yours to change? |
|---|---|---|
| Admin console (config + LTI URL) | `app/routers/admin.py` | As you add settings |
| LTI 1.1 launch + OAuth validation | `app/lti/validation.py` | Rarely — it's the security boundary |
| Grade passback (Basic Outcomes) | `app/lti/outcomes.py` | The *policy* yes, the signing no |
| LAMB API client | `app/lamb_client.py` | If you call LAMB differently |
| Student chat | `app/routers/chat.py`, `app/templates/chat.html`, `app/static/chat.js` | **Yes — this is the point** |
| Instructor setup + dashboard | `app/routers/instructor.py`, `app/templates/setup.html`, `app/templates/dashboard.html` | Yes |
| Storage (SQLite, no ORM) | `app/db.py` | As your data grows |

## Quick start

```bash
git clone https://github.com/Lamb-Project/lamb-tool-template
cd lamb-tool-template
cp .env.example .env         # then fill it in — there are no working defaults
docker compose up --build    # tool on http://localhost:8080
```

To run without Docker:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```

You cannot launch the tool by visiting it in a browser — an LTI tool is
*launched by an LMS*. For local development without a real Moodle, use the
bundled test LMS: see [`docs/dev-harness.md`](docs/dev-harness.md).

## Configuration

Configuration is split in two:

**Boot config — environment (`.env`)**, needed before the tool can serve:

- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — protect the admin console.
- `PUBLIC_BASE_URL` — the URL the LMS uses to reach this tool. Behind a
  reverse proxy this must be the *public* URL, because the OAuth signature
  is computed over it.

**Runtime config — the admin console (`/admin`)**, set after the tool is up:

- **LAMB API base URL + API key** — your LAMB instance and the key this tool
  uses to reach it. The key is held **server-side only** and never reaches
  the browser.
- **LTI consumer key + shared secret** — must match the External Tool
  configuration you create in Moodle/Atenea.

Log in at `/admin` with the credentials from `.env`, fill in those four
values, and the page shows you the **LTI launch URL** to register in your
LMS. Until they're set, the tool safely rejects all launches.

> For Docker/CI you may pre-seed the four runtime values from the
> environment on first boot (see the commented block in
> [`.env.example`](.env.example)); once saved via `/admin`, the stored value
> wins. See [`.env.example`](.env.example) for the full annotated list.

## Deploying to Atenea / Moodle

See [`docs/atenea-setup.md`](docs/atenea-setup.md) for the External Tool
configuration, step by step.

## How it works

One page, launch to grade: [`docs/anatomy.md`](docs/anatomy.md).

## Growing this into a LAMB extension

The contract for folding a tool built on this template back into the LAMB
ecosystem: [`docs/EXTENDING.md`](docs/EXTENDING.md).

## Security

This template does the things LTI tools most often get wrong, correctly —
copy the posture, don't weaken it:

- **Inbound launches are verified and rejected on failure.** The OAuth 1.0a
  HMAC-SHA1 signature is recomputed and compared; the timestamp must be
  fresh; the nonce must be unused (replay protection). An unverified launch
  is a forged one.
- **Sessions are server-side and persisted.** A random token in SQLite,
  accepted from cookie / header / query so it survives the LMS iframe. A
  restart does not log anyone out.
- **The LAMB key never leaves the server.** The browser talks to this tool;
  this tool talks to LAMB.
- **No working default secrets.** The app refuses to start until you set
  real ones.

## Running the tests

```bash
# with the tool running on :8080 and its .env loaded
.venv/bin/python tests/test_lti_launch.py
```

The tests act as the LMS (they sign their own launches) and cover the
launch/validation/session paths — valid launch, forged signature, tampered
role, replayed nonce, stale timestamp, missing session. They need neither a
real LMS nor a running LAMB.

## License

GPL-3.0 — see [LICENSE](LICENSE). Built by the LAMB Project
(UPC × UPV/EHU). Contributions welcome.
