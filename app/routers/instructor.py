"""Instructor-facing surfaces: first-launch setup, the dashboard (roster +
grading), and grade passback to the LMS.

Grade policy in this template is deliberately simple and pluggable:
  - an optional auto-completion proposal: >= min_turns student turns -> 1.0
  - the instructor sets/overrides the final score before anything is sent
Replace propose_completion_score() with a rubric call, an assistant-as-
judge, or anything else — the approve-then-send flow stays the same."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .. import db, lamb_client, sessions
from ..lti import outcomes

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def propose_completion_score(user_turns: int, min_turns: int) -> float | None:
    if min_turns <= 0:
        return None
    return 1.0 if user_turns >= min_turns else round(user_turns / min_turns, 2)


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request):
    session = sessions.require_instructor(request)
    try:
        models = lamb_client.list_models()
        error = None
    except Exception as e:  # surface LAMB connectivity problems to the instructor
        models, error = [], f"Could not reach LAMB: {e}"
    activity = db.get_activity(session["resource_link_id"], session["consumer_guid"])
    return templates.TemplateResponse(request, "setup.html", {
        "session_token": session["token"],
        "models": models,
        "error": error,
        "activity": activity,
    })


@router.post("/setup")
async def setup_save(request: Request):
    session = sessions.require_instructor(request)
    form = await request.form()
    model = form.get("assistant_model", "")
    models = {m["id"]: m["name"] for m in lamb_client.list_models()}
    if model not in models:
        return HTMLResponse("Pick a valid assistant.", status_code=400)

    db.save_activity(
        resource_link_id=session["resource_link_id"],
        consumer_guid=session["consumer_guid"],
        context_id=form.get("context_id", ""),
        context_title=form.get("context_title", ""),
        title=form.get("title") or "Chat activity",
        assistant_model=model,
        assistant_name=models[model],
        grading_enabled=form.get("grading_enabled") == "on",
        min_turns=int(form.get("min_turns") or 3),
        created_by=session["user_id"],
    )
    return JSONResponse({"ok": True, "redirect": f"/dashboard?session={session['token']}"})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    session = sessions.require_instructor(request)
    activity = db.get_activity(session["resource_link_id"], session["consumer_guid"])
    rows = db.participants(session["resource_link_id"], session["consumer_guid"])
    min_turns = activity["min_turns"] if activity else 3
    people = []
    for r in rows:
        people.append({
            **{k: r[k] for k in r.keys()},
            "proposed": propose_completion_score(r["user_turns"], min_turns),
        })
    return templates.TemplateResponse(request, "dashboard.html", {
        "session_token": session["token"],
        "activity": activity,
        "people": people,
    })


@router.post("/grades/set")
async def grades_set(request: Request):
    session = sessions.require_instructor(request)
    body = await request.json()
    db.set_grade(
        user_id=int(body["user_id"]),
        resource_link_id=session["resource_link_id"],
        consumer_guid=session["consumer_guid"],
        score=float(body["score"]),
        feedback=body.get("feedback", ""),
        proposed_score=body.get("proposed_score"),
    )
    return JSONResponse({"ok": True})


@router.post("/grades/send")
def grades_send(request: Request):
    """Push every approved-but-unsent grade to the LMS via replaceResult."""
    session = sessions.require_instructor(request)
    rows = db.gradable_rows(session["resource_link_id"], session["consumer_guid"])
    sent, failed = 0, []
    for r in rows:
        result = outcomes.send_grade(
            sourcedid=r["lis_result_sourcedid"],
            outcome_url=r["lis_outcome_service_url"],
            score_0_1=float(r["score"]),
            comment=r["feedback"] or "",
        )
        if result["success"]:
            db.mark_grade_sent(r["user_id"], session["resource_link_id"], session["consumer_guid"])
            sent += 1
        else:
            failed.append({"user_id": r["user_id"], "detail": result["detail"]})
    return JSONResponse({"sent": sent, "failed": failed})
