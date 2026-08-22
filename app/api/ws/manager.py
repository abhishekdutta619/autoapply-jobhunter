from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger("api.executor_ws")


class ExecutorConnectionManager:
    """Tracks live dashboard connections per job_id and lets any part of
    the app broadcast a log line to whoever's watching that job.

    This is transport only. Nothing in app/executor/runner.py calls
    broadcast_log() yet - the Executor's actual Playwright step-by-step
    logic hasn't been run against real applications (per the project's
    own roadmap), so wiring live telemetry into it is a separate,
    more careful change than standing up the API layer.
    """

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)
        self._kill_requested: set[int] = set()

    async def connect(self, job_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[job_id].append(websocket)

    def disconnect(self, job_id: int, websocket: WebSocket) -> None:
        if websocket in self._connections.get(job_id, []):
            self._connections[job_id].remove(websocket)
        # Design choice worth revisiting once runner.py actually polls this:
        # a dropped/closed dashboard tab clears the kill request for that
        # job_id. That's usually right (no one's watching this job anymore,
        # so there's nothing to "kill" on their behalf) but means a brief
        # network blip right after clicking Kill could silently un-cancel
        # a run that's still mid-flight. If that turns out to matter once
        # this is wired into the real Executor loop, make kill requests
        # persist until the run itself acknowledges and clears them,
        # instead of clearing on disconnect.
        self._kill_requested.discard(job_id)

    async def broadcast_log(self, job_id: int, level: str, message: str) -> None:
        """Call this from runner.py, once it's ready to stream real progress.
        Matches ExecutionLogEntry in job.model.ts: {jobId, timestamp, level, message}."""
        import datetime as _dt

        payload = {
            "jobId": job_id,
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        dead: list[WebSocket] = []
        for ws in self._connections.get(job_id, []):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 - a dropped dashboard tab shouldn't kill the run
                dead.append(ws)
        for ws in dead:
            self.disconnect(job_id, ws)

    def request_kill(self, job_id: int) -> None:
        """Set from the dashboard's kill-switch button. runner.py can poll
        `manager.is_kill_requested(job_id)` between steps to abort a run
        early - not wired into the Playwright loop yet, by design."""
        self._kill_requested.add(job_id)
        log.warning("Kill switch requested for job_id=%s", job_id)

    def is_kill_requested(self, job_id: int) -> bool:
        return job_id in self._kill_requested


manager = ExecutorConnectionManager()
