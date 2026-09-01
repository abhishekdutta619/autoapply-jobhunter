from __future__ import annotations

import logging
import threading

from fastapi import APIRouter, Depends, HTTPException

from app import hunter
from app.api.deps import require_owner
from app.db.models import User

log = logging.getLogger("api.hunter")
router = APIRouter(prefix="/api/hunter", tags=["hunter"])

# Single in-process flag, not a real job queue. Fine for one person running
# this locally; if this ever needs to run unattended/multi-user, replace
# with a proper task queue (e.g. Celery/RQ) instead of scaling this up.
_run_lock = threading.Lock()
_run_in_progress = False


def _run_hunter_in_background() -> None:
    global _run_in_progress
    try:
        hunter.run()
    except Exception:  # noqa: BLE001 - log and clear the flag either way
        log.exception("Hunter run triggered from dashboard failed")
    finally:
        with _run_lock:
            _run_in_progress = False


@router.post("/trigger")
def trigger_hunter_run(user: User = Depends(require_owner)) -> dict[str, bool]:
    global _run_in_progress
    with _run_lock:
        if _run_in_progress:
            raise HTTPException(status_code=409, detail="A Hunter run is already in progress")
        _run_in_progress = True

    thread = threading.Thread(target=_run_hunter_in_background, daemon=True)
    thread.start()
    return {"triggered": True}


@router.get("/status")
def hunter_status(user: User = Depends(require_owner)) -> dict[str, bool]:
    with _run_lock:
        return {"running": _run_in_progress}
