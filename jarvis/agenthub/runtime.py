from __future__ import annotations

from pathlib import Path

from .approval_queue import list_pending_approvals
from .backend import check_backend
from .config import load_config
from .control_state import load_runtime_control_state, set_runtime_control_mode
from .contracts import RuntimeStatus
from .events import LocalEventBus
from .memory import load_memory, project_id
from .resource_manager import ResourceManager
from .speech import speech_mode_status
from .tts import speech_supported


class JarvisRuntime:
    def __init__(
        self,
        *,
        project_path: str,
        event_bus: LocalEventBus | None = None,
        resource_manager: ResourceManager | None = None,
    ) -> None:
        self._project_path = project_path
        self._project_id = project_id(project_path)
        self._event_bus = event_bus or LocalEventBus()
        self._resource_manager = resource_manager or ResourceManager()
        self._config = load_config()
        self._active_tasks: set[str] = set()
        self._control_state = load_runtime_control_state()
        self._status = RuntimeStatus(active_model=self._config.model)

    @property
    def event_bus(self) -> LocalEventBus:
        return self._event_bus

    def start(self) -> RuntimeStatus:
        status = self.refresh_status()
        self._event_bus.publish("jarvis.started", status.to_dict())
        return status

    def refresh_status(self, *, active_agent: str = "", active_model: str = "") -> RuntimeStatus:
        self._control_state = load_runtime_control_state()
        omnira_online, omnira_detail = check_backend()
        speech_detail = speech_mode_status()
        voice_online = bool(speech_supported()) and str(speech_detail.get("availability", "")).lower() in {"ready", "limited", "degraded"}
        pending_approvals = len(list_pending_approvals())
        memory_online = True
        try:
            load_memory(self._project_id)
        except Exception:
            memory_online = False

        snapshot = self._resource_manager.collect(
            omnira_online=omnira_online,
            active_model=active_model or self._config.model,
            active_tasks=len(self._active_tasks),
            pending_approvals=pending_approvals,
        )
        warnings = list(snapshot.warnings)
        if not voice_online:
            warnings.append("voice_offline")
        commands_blocked = self._control_state.mode in {"paused", "stopped", "killed"}
        if commands_blocked:
            warnings.append(f"control_{self._control_state.mode}")
        self._status = RuntimeStatus(
            jarvis_alive=True,
            control_mode=self._control_state.mode,
            commands_blocked=commands_blocked,
            control_updated_at=self._control_state.updated_at,
            control_note=self._control_state.note,
            voice_online=voice_online,
            omnira_online=omnira_online,
            active_model=active_model or self._config.model,
            active_agent=active_agent,
            memory_online=memory_online,
            tools_ready=not commands_blocked,
            active_tasks=len(self._active_tasks),
            pending_approvals=pending_approvals,
            cpu_percent=snapshot.cpu_percent,
            ram_percent=snapshot.ram_percent,
            warnings=warnings,
            last_error="" if omnira_online else omnira_detail,
            metadata={
                "backend": snapshot.active_backend,
                "omnira_detail": omnira_detail,
                "speech": speech_detail,
                "routing_hints": self._resource_manager.routing_hints(snapshot),
            },
        )
        return self._status

    def heartbeat(self) -> RuntimeStatus:
        status = self.refresh_status(active_agent=self._status.active_agent, active_model=self._status.active_model)
        self._event_bus.publish("jarvis.heartbeat", status.to_dict())
        if status.warnings:
            self._event_bus.publish("resource.warning", {"warnings": list(status.warnings)})
        return status

    def control_action_for_text(self, text: str) -> str | None:
        normalized = " ".join(str(text or "").strip().lower().split())
        if normalized in {"start", "start jarvis", "resume", "resume jarvis"}:
            return "active"
        if normalized in {"pause", "pause jarvis"}:
            return "paused"
        if normalized in {"stop", "stop jarvis"}:
            return "stopped"
        if normalized in {"kill", "kill jarvis"}:
            return "killed"
        if normalized in {"jarvis status", "status jarvis", "control status"}:
            return "status"
        return None

    def set_control_mode(self, mode: str, *, source: str = "owner", note: str = "") -> RuntimeStatus:
        next_state = set_runtime_control_mode(mode, source=source, note=note)
        self._control_state = next_state
        if next_state.mode in {"stopped", "killed"}:
            self._active_tasks.clear()
        self._event_bus.publish(f"jarvis.control.{next_state.mode}", next_state.to_dict())
        return self.refresh_status(active_agent=self._status.active_agent, active_model=self._status.active_model)

    def can_accept_command(self, text: str, intent: str) -> tuple[bool, str]:
        self._control_state = load_runtime_control_state()
        mode = self._control_state.mode
        if mode == "active":
            return True, ""
        control_action = self.control_action_for_text(text)
        if control_action is not None:
            return True, ""
        if intent in {"backend_status", "resource_status", "model_status"}:
            return True, ""
        return False, f"Jarvis is {mode}. Use start, resume, status, pause, stop, or kill commands to control runtime state."

    def begin_task(self, task_id: str) -> None:
        self._active_tasks.add(task_id)
        self._event_bus.publish("task.started", {"task_id": task_id}, task_id=task_id)

    def finish_task(self, task_id: str, *, success: bool, error: str = "") -> None:
        self._active_tasks.discard(task_id)
        if success:
            self._event_bus.publish("task.completed", {"task_id": task_id}, task_id=task_id)
            return
        self._event_bus.publish("task.failed", {"task_id": task_id, "error": error}, task_id=task_id)

    def status(self) -> RuntimeStatus:
        return self.refresh_status(active_agent=self._status.active_agent, active_model=self._status.active_model)