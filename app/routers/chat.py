"""Student-facing chat. The page renders the conversation so far; the send
endpoint streams the assistant reply from LAMB and persists both turns.

This is the file most teams will rewrite to make the tool their own — it is
kept short and obvious on purpose."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from .. import db, lamb_client, sessions

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/waiting", response_class=HTMLResponse)
def waiting(request: Request):
    sessions.resolve_session(request)
    return templates.TemplateResponse(request, "waiting.html")


@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    session = sessions.resolve_session(request)
    activity = db.get_activity(session["resource_link_id"], session["consumer_guid"])
    history = db.get_messages(session["user_id"], session["resource_link_id"],
                              session["consumer_guid"])
    return templates.TemplateResponse(request, "chat.html", {
        "session_token": session["token"],
        "assistant_name": activity["assistant_name"] if activity else "Assistant",
        "activity_title": activity["title"] if activity else "Chat",
        "history": history,
    })


@router.post("/chat/send")
async def chat_send(request: Request):
    session = sessions.resolve_session(request)
    activity = db.get_activity(session["resource_link_id"], session["consumer_guid"])
    if activity is None:
        return HTMLResponse("Activity not configured.", status_code=409)

    body = await request.json()
    user_message = (body.get("message") or "").strip()
    if not user_message:
        return HTMLResponse("Empty message.", status_code=400)

    uid, rlid, guid = session["user_id"], session["resource_link_id"], session["consumer_guid"]
    db.add_message(uid, rlid, guid, "user", user_message)

    history = db.get_messages(uid, rlid, guid)
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    def generate():
        collected = []
        try:
            for delta in lamb_client.stream_chat(activity["assistant_model"], messages):
                collected.append(delta)
                yield delta
        finally:
            if collected:
                db.add_message(uid, rlid, guid, "assistant", "".join(collected))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
