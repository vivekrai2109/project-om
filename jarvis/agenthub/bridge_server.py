from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import asyncio

from fastapi import Body, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .approval_queue import list_pending_approvals
from .backend import check_backend
from .commander import JarvisCommander
from .contracts import OwnerCommand, new_id
from .memory_control import load_memory_control_state
from .response_envelope import JarvisResponseEnvelope
from .runtime_actions import approve_runtime_action, reject_runtime_action
from .speech import get_capture_state, get_microphone_config, speech_mode_status
from .voice import get_listen_state


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@dataclass
class BridgeContext:
    project_path: str
    policy_profile: str
    commander: JarvisCommander
    events: "BridgeEventHub"


class BridgeEventHub:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections)
        stale: list[WebSocket] = []
        for websocket in targets:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        if stale:
            async with self._lock:
                for websocket in stale:
                    self._connections.discard(websocket)


def _permission_level_for_risk(risk_level: str) -> str:
    normalized = str(risk_level or "low").strip().lower()
    if normalized in {"low", "none"}:
        return "L1"
    if normalized == "medium":
        return "L2"
    if normalized == "high":
        return "L3"
    return "L4"


def _normalize_model_rationale_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        pieces: list[str] = []
        selected_model = str(value.get("selected_model") or value.get("resolved_model") or "").strip()
        if selected_model:
            pieces.append(f"Selected {selected_model}.")
        compute_mode = str(value.get("compute_mode") or "").strip()
        if compute_mode:
            pieces.append(f"Compute mode is {compute_mode}.")
        reason = str(value.get("reason") or value.get("summary") or "").strip()
        if reason:
            pieces.append(reason)
        path = str(value.get("intent_path") or "").strip()
        if path:
            pieces.append(f"Routing path: {path}.")
        return " ".join(piece for piece in pieces if piece)
    return ""


def _tool_events_from_envelope(envelope: JarvisResponseEnvelope) -> list[dict[str, str]]:
    timestamp = _now_iso()
    events: list[dict[str, str]] = []
    for item in envelope.workflow_trace:
        detail = str(item.get("detail") or item.get("step") or "").strip()
        events.append(
            {
                "time": str(item.get("ts") or timestamp),
                "type": str(item.get("status") or "info"),
                "message": detail,
            }
        )
    for item in envelope.tool_calls:
        name = str(item.get("name") or "tool").strip()
        status = str(item.get("status") or "info").strip()
        detail = str(item.get("detail") or item.get("message") or name).strip()
        events.append({"time": timestamp, "type": status, "message": detail})
    if not events and envelope.reply_text:
        events.append({"time": timestamp, "type": "info", "message": "Command completed."})
    return events[:20]


def _memory_status_payload() -> dict[str, object]:
    state = load_memory_control_state()
    return {
        "memory_enabled": state.memory_enabled,
        "training_enabled": state.training_enabled,
        "profile_learning_enabled": state.profile_learning_enabled,
        "internet_learning_enabled": state.internet_learning_enabled,
        "compute_mode": state.compute_mode,
        "pinned_model": state.pinned_model or None,
    }


def _approval_payload(envelope: JarvisResponseEnvelope) -> dict[str, object]:
    approval_request = dict(envelope.metadata.get("approval_request") or {})
    return {
        "required": bool(envelope.approval_required),
        "risk_level": envelope.risk_level,
        "reason": str(approval_request.get("plan_summary") or "").strip(),
        "action_summary": str(approval_request.get("action_summary") or "").strip(),
        "approval_id": str(approval_request.get("approval_id") or "").strip(),
        "expected_result": str(approval_request.get("expected_result") or approval_request.get("plan_summary") or "").strip(),
        "permission_level": _permission_level_for_risk(envelope.risk_level),
    }


def _bridge_envelope(
    envelope: JarvisResponseEnvelope,
    *,
    conversation_id: str,
    turn_id: str,
    user_message: str,
) -> dict[str, Any]:
    model_rationale = _normalize_model_rationale_text(envelope.metadata.get("model_rationale"))
    return {
        "conversation_id": conversation_id,
        "turn_id": turn_id,
        "state": envelope.state,
        "agent": envelope.agent,
        "model": envelope.model,
        "provider": envelope.provider,
        "model_rationale": model_rationale,
        "confidence": envelope.confidence,
        "task": str(envelope.metadata.get("plan", {}).get("goal") or user_message).strip(),
        "user_message": user_message,
        "assistant_message": envelope.reply_text,
        "requires_approval": envelope.approval_required,
        "approval": _approval_payload(envelope),
        "tool_events": _tool_events_from_envelope(envelope),
        "memory_status": _memory_status_payload(),
        "error": envelope.error,
        "decision_path": list(envelope.decision_path),
        "safety_flags": list(envelope.safety_flags),
    }


def _final_response_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "conversation_id": envelope.get("conversation_id", ""),
        "turn_id": envelope.get("turn_id", ""),
        "state": envelope.get("state", "idle"),
        "agent": envelope.get("agent", ""),
        "model": envelope.get("model", ""),
        "assistant_message": envelope.get("assistant_message", ""),
        "requires_approval": bool(envelope.get("requires_approval", False)),
    }


def _state_payload(context: BridgeContext) -> dict[str, Any]:
    listen = get_listen_state()
    mic = get_microphone_config()
    capture = get_capture_state()
    speech = speech_mode_status()
    backend_ok, backend_detail = check_backend()
    return {
        "conversation_id": new_id("conversation"),
        "shell": {
            "active_state": "idle",
            "active_agent": "commander",
            "active_model": "",
            "backend_online": backend_ok,
            "backend_detail": backend_detail,
        },
        "voice": {
            "listen_enabled": listen.enabled,
            "listen_mode": listen.mode,
            "capture_active": capture.active,
            "capture_provider": capture.provider,
            "microphone": {
                "device": mic.device,
                "sample_rate": mic.sample_rate,
                "chunk_ms": mic.chunk_ms,
                "mode": mic.mode,
            },
            "speech": speech,
        },
        "memory_status": _memory_status_payload(),
        "approval_queue": {"count": len(list_pending_approvals())},
        "project_path": context.project_path,
        "policy_profile": context.policy_profile,
        "bridge_version": "v0.2",
        "websocket_url": "ws://127.0.0.1:8010/api/v1/events",
    }


def create_app(*, project_path: str | None = None, policy_profile: str = "personal") -> FastAPI:
    resolved_project = str(Path(project_path or Path.cwd()).resolve())
    commander = JarvisCommander(project_path=resolved_project, profile=policy_profile, stage_approvals=True)
    context = BridgeContext(
        project_path=resolved_project,
        policy_profile=policy_profile,
        commander=commander,
        events=BridgeEventHub(),
    )

    app = FastAPI(title="Jarvis Cinematic Bridge", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        ok, detail = check_backend()
        return {
            "ok": True,
            "bridge": "online",
            "backend_online": ok,
            "backend_detail": detail,
            "project_path": context.project_path,
            "policy_profile": context.policy_profile,
        }

    @app.get("/api/v1/state")
    def state() -> JSONResponse:
        return JSONResponse(_state_payload(context))

    @app.websocket("/api/v1/events")
    async def events(websocket: WebSocket) -> None:
        await context.events.connect(websocket)
        await context.events.broadcast({"type": "state_changed", "state": "idle", "timestamp": _now_iso()})
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await context.events.disconnect(websocket)

    @app.post("/api/v1/command")
    async def command(payload: dict = Body(...)) -> JSONResponse:
        user_message = str(payload.get("message", "")).strip()
        if not user_message:
            return JSONResponse({"error": {"message": "empty message"}}, status_code=400)
        conversation_id = str(payload.get("conversation_id") or new_id("conversation")).strip()
        turn_id = new_id("turn")
        await context.events.broadcast({"type": "state_changed", "state": "thinking", "timestamp": _now_iso()})
        await context.events.broadcast(
            {
                "type": "tool_event",
                "event": {
                    "time": _now_iso(),
                    "type": "info",
                    "message": f"Routing command: {user_message}",
                },
            }
        )
        command_context = {
            "channel": "tauri_cinematic_shell",
            "conversation_id": conversation_id,
        }
        response = context.commander.handle_owner_command(
            OwnerCommand(
                text=user_message,
                source="tauri_shell",
                context=command_context,
                metadata={"bridge": "cinematic", "conversation_id": conversation_id},
            )
        )
        envelope = _bridge_envelope(
            response,
            conversation_id=conversation_id,
            turn_id=turn_id,
            user_message=user_message,
        )
        for event in envelope["tool_events"]:
            await context.events.broadcast({"type": "tool_event", "event": event})
        assistant_message = str(envelope.get("assistant_message") or "")
        if assistant_message:
            await context.events.broadcast(
                {
                    "type": "partial_response",
                    "text": assistant_message[: min(assistant_message.__len__(), 120)],
                    "timestamp": _now_iso(),
                }
            )
        if envelope["requires_approval"]:
            await context.events.broadcast({"type": "approval_required", "approval": envelope["approval"]})
        await context.events.broadcast({"type": "final_response", "envelope": _final_response_payload(envelope)})
        await context.events.broadcast(
            {
                "type": "state_changed",
                "state": envelope["state"],
                "timestamp": _now_iso(),
            }
        )
        return JSONResponse(envelope)

    @app.get("/api/v1/approvals")
    def approvals() -> JSONResponse:
        items = []
        for item in list_pending_approvals():
            items.append(
                {
                    "approval_id": item.id,
                    "risk_level": item.risk,
                    "action_summary": item.task,
                    "reason": item.source,
                }
            )
        return JSONResponse({"items": items})

    @app.post("/api/v1/approvals/approve")
    def approve(payload: dict = Body(...)) -> JSONResponse:
        approval_id = str(payload.get("approval_id", "")).strip()
        note = str(payload.get("note", "")).strip()
        if not approval_id:
            return JSONResponse({"error": {"message": "missing approval_id"}}, status_code=400)
        result = approve_runtime_action(approval_id, context.project_path, profile=context.policy_profile, note=note)
        return JSONResponse({"ok": True, "message": result.message, "action": result.action})

    @app.post("/api/v1/approvals/reject")
    def reject(payload: dict = Body(...)) -> JSONResponse:
        approval_id = str(payload.get("approval_id", "")).strip()
        note = str(payload.get("note", "")).strip()
        if not approval_id:
            return JSONResponse({"error": {"message": "missing approval_id"}}, status_code=400)
        result = reject_runtime_action(approval_id, note=note)
        return JSONResponse({"ok": True, "message": result.message, "action": result.action})

    return app


def start(*, host: str = "127.0.0.1", port: int = 8010, project_path: str | None = None, policy_profile: str = "personal") -> None:
    import uvicorn

    uvicorn.run(
        create_app(project_path=project_path, policy_profile=policy_profile),
        host=host,
        port=port,
    )