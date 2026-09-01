from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import auth, executor_ws, hunter, jobs
from app.config import settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates tables if missing, patches missing columns (e.g. rationale) if not
    yield


app = FastAPI(title="AutoApply JobHunter API", lifespan=lifespan)

# Must be added before CORSMiddleware below (Starlette wraps middleware in
# reverse order of add_middleware calls, so this ends up running first for
# every request) - Authlib's OAuth dance stores short-lived state in
# request.session during the redirect round trip, and login itself sets
# request.session["user_id"] on success (see app/api/routes/auth.py).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    same_site="lax",
)

# Angular dev server runs on :4200 by default (see dashboard/proxy.conf.json,
# which proxies /api and /ws through to here so the frontend never needs to
# know this port - but CORS is still set explicitly in case ng serve isn't
# used, e.g. hitting this API directly during backend development).
# allow_credentials=True is required for that direct-hit case to carry the
# session cookie; requests through the ng serve proxy are same-origin from
# the browser's perspective and don't need it, but it's harmless either way.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(jobs.router)
app.include_router(hunter.router)
app.include_router(executor_ws.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
