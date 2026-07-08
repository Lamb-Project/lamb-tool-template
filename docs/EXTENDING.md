# Growing a tool into a LAMB extension

This template exists so teaching-innovation teams don't rebuild the same
LTI + LAMB plumbing every time. A tool that starts here can later be folded
back into the LAMB ecosystem as an extension — with a bit of refactoring —
and its authors credited as contributors.

To keep that path open, hold to this contract as you build:

## Keep

- **Speak LAMB's OpenAI-compatible API.** Reach assistants through
  `/v1/models` and `/v1/chat/completions` (see `app/lamb_client.py`). Don't
  couple to LAMB's internal endpoints — they change; the OpenAI-compatible
  surface is the stable contract.
- **Keep the LTI layer at its module boundary.** `app/lti/validation.py`
  and `app/lti/outcomes.py` are the reusable, correct core. If you extend
  LTI behaviour, extend around them; don't inline LMS logic into your
  feature code.
- **Keep secrets server-side and config in the environment.** No key,
  consumer secret, or LAMB token in client code or committed files.
- **Stay GPL-3.0.** This template is GPL-3.0; a derived tool that wants to
  join the LAMB ecosystem stays GPL-3.0 so it can be merged.

## Expect to refactor

When a tool graduates from "standalone template deployment" to "LAMB
extension", expect to:

- **Move identity onto LAMB's LTI activity framework** rather than this
  tool's standalone launch, so the tool shares LAMB's organisation, user,
  and activity model instead of its own SQLite users.
- **Move storage** from this tool's local SQLite to the extension's place
  in LAMB's data model.
- **Swap the LAMB key** for whatever credential the integrated deployment
  uses (e.g. a creator API key issued by LAMB, rather than a shared token
  in `.env`).

Because the LTI validation, the outcomes signing, and the LAMB client are
already at clean module boundaries, that refactor touches wiring, not the
core of your feature.

## Contributing back

Open an issue or PR on the LAMB Project org describing what your tool does
and which parts are general enough to share. General-purpose improvements to
the template's core (LTI, sessions, the LAMB client) are especially
welcome — those help every team that starts here after you.
