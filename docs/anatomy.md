# Anatomy of a request — launch to grade

The whole tool is one lifecycle. Follow it once and the code map falls into
place.

```
  ┌────────┐   POST /lti/launch (signed)   ┌──────────────────────┐
  │  LMS   │ ─────────────────────────────▶│  app/routers/        │
  │(Moodle)│                                │    lti_launch.py     │
  └────────┘                                └──────────┬───────────┘
       ▲                                               │
       │                                     validate signature,
       │                                     timestamp, nonce
       │                                     (app/lti/validation.py)
       │                                               │
       │                                     upsert user + enrollment,
       │                                     capture lis_result_sourcedid
       │                                     + lis_outcome_service_url
       │                                     (app/db.py)
       │                                               │
       │                                     mint session
       │                                     (app/sessions.py)
       │                                               │
       │                          303 redirect with ?session=… + cookie
       │                                               │
       │                    ┌──────────────────────────┴───────────┐
       │              instructor                                student
       │                    │                                       │
       │            /setup (first time)                          /chat
       │            /dashboard                                      │
       │            (app/routers/instructor.py)          POST /chat/send
       │                    │                            streams from LAMB
       │                    │                            (app/lamb_client.py)
       │                    │                                       │
       │       POST /grades/send                          both turns saved
       │       replaceResult, signed                       (app/db.py)
       └───────────────────┘
         (app/lti/outcomes.py)
```

## Step by step

1. **Launch.** The LMS POSTs a signed `basic-lti-launch-request` to
   `/lti/launch`. `validation.validate_launch()` recomputes the OAuth
   signature over the exact fields and the public launch URL, checks the
   timestamp window, and consumes the nonce. Any failure → 401, no session.

2. **Provision.** A valid launch upserts the user (keyed on
   `user_id + tool_consumer_instance_guid`, so two Moodles never collide)
   and the enrollment. The grade-passback plumbing —
   `lis_result_sourcedid` and `lis_outcome_service_url` — arrives *only on
   the launch*, so it is captured here.

3. **Session + redirect.** A random session token is stored in SQLite and
   returned both as a cookie and on the redirect URL. Instructors go to
   `/setup` (or `/dashboard` if the activity is already configured);
   students go to `/chat` (or `/waiting` if it isn't).

4. **Setup (instructor).** `/setup` lists the assistants this tool's LAMB
   key can see (`GET /v1/models`) and stores the choice against the
   `resource_link_id`. That binding is what makes this activity *this*
   assistant.

5. **Chat (student).** `/chat/send` appends the student turn, replays the
   whole conversation to LAMB with `stream: true`, relays the deltas to the
   browser, and saves the assistant turn when the stream ends.

6. **Grade (instructor).** The dashboard proposes a score (the example
   policy: enough turns → complete), the instructor sets the final grade,
   and `/grades/send` signs a `replaceResult` for each and posts it to the
   LMS outcome URL captured at step 2.

## Where the security lives

- `app/routers/admin.py` — the config console, guarded by the `.env`
  credentials; sits outside the launch path and holds the runtime settings
  (LAMB URL + key, LTI consumer key + secret) in the database.
- `app/lti/validation.py` — the inbound boundary. Never launch without it.
- `app/lti/outcomes.py` — the outbound signing. Grades are signed the same
  way launches are verified.
- `app/sessions.py` — everything past the launch is gated on a session
  (LTI sessions and the admin session both live here).
- `app/lamb_client.py` — the only place the LAMB key is read.
