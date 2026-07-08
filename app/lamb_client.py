"""Client for LAMB's OpenAI-compatible API.

Two calls are all this template needs:
  - list_models(): populate the instructor's assistant picker.
  - stream_chat(): relay a streamed completion to the student's browser.

The LAMB API key lives here, server-side, and NEVER reaches the browser.
Assistants are addressed by their model id, which LAMB shapes as
"lamb_assistant.<id>"."""

import json
from typing import Iterator

import httpx

from . import settings_store


class NotConfigured(RuntimeError):
    """Raised when the admin has not yet set the LAMB URL + key."""


def _lamb():
    base = settings_store.get("lamb_api_base")
    key = settings_store.get("lamb_api_key")
    if not base or not key:
        raise NotConfigured("LAMB URL and API key are not set — configure the tool at /admin.")
    return base.rstrip("/"), {"Authorization": f"Bearer {key}"}


def list_models() -> list[dict]:
    """Return [{id, name}] for the assistants this key may see."""
    base, headers = _lamb()
    url = f"{base}/v1/models"
    resp = httpx.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    models = []
    for m in data:
        mid = m.get("id", "")
        # LAMB's /v1/models exposes no display name — derive one from the id
        # (strip the "lamb_assistant." prefix) so the picker reads cleanly.
        display = m.get("name") or mid.replace("lamb_assistant.", "assistant ")
        models.append({"id": mid, "name": display})
    return models


def stream_chat(model: str, messages: list[dict]) -> Iterator[str]:
    """Yield assistant text deltas from a streamed chat completion.

    Only model/messages/stream are sent — that is exactly what LAMB's
    facade forwards today, and all a chatbot needs."""
    base, headers = _lamb()
    url = f"{base}/v1/chat/completions"
    payload = {"model": model, "messages": messages, "stream": True}
    with httpx.stream("POST", url, headers=headers, json=payload, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0]["delta"].get("content")
                if delta:
                    yield delta
            except (json.JSONDecodeError, KeyError, IndexError):
                continue
