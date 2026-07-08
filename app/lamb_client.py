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

from . import config

_HEADERS = {"Authorization": f"Bearer {config.LAMB_API_KEY}"}


def list_models() -> list[dict]:
    """Return [{id, name}] for the assistants this key may see."""
    url = f"{config.LAMB_API_BASE}/v1/models"
    resp = httpx.get(url, headers=_HEADERS, timeout=30)
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
    url = f"{config.LAMB_API_BASE}/v1/chat/completions"
    payload = {"model": model, "messages": messages, "stream": True}
    with httpx.stream("POST", url, headers=_HEADERS, json=payload, timeout=120) as resp:
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
