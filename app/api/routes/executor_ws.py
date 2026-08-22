from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.ws.manager import manager

router = APIRouter(tags=["executor-ws"])


@router.websocket("/ws/executor/{job_id}")
async def executor_telemetry(websocket: WebSocket, job_id: int) -> None:
    await manager.connect(job_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            # Matches JobSocketService.killSwitch(): {"action": "kill", "jobId": ...}
            if data.get("action") == "kill":
                manager.request_kill(job_id)
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)
