"""lamb-tool-template — a minimal LAMB-connected, LTI 1.1 educational tool.

Request lifecycle (see docs/anatomy.md):
  LMS  --POST /lti/launch-->  validate  -->  user + session  -->  redirect
       student  --> /chat  (streams from LAMB)
       instructor --> /setup (first time) or /dashboard
       instructor --> POST /grades/send  --> replaceResult to the LMS
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .routers import lti_launch, chat, instructor

app = FastAPI(title="lamb-tool-template", docs_url=None, redoc_url=None)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


app.include_router(lti_launch.router)
app.include_router(chat.router)
app.include_router(instructor.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
