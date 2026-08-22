from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import executor_ws, hunter, jobs
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates tables if missing, patches missing columns (e.g. rationale) if not
    yield


app = FastAPI(title="AutoApply JobHunter API", lifespan=lifespan)

# Angular dev server runs on :4200 by default (see dashboard/proxy.conf.json,
# which proxies /api and /ws through to here so the frontend never needs to
# know this port - but CORS is still set explicitly in case ng serve isn't
# used, e.g. hitting this API directly during backend development).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(hunter.router)
app.include_router(executor_ws.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
