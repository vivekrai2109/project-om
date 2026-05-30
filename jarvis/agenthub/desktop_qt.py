from __future__ import annotations

from dataclasses import asdict
import json
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .agents import AgentProfile, get_agent
from .approval_queue import create_pending_approval, list_pending_approvals, resolve_pending_approval
from .backend import check_backend
from .backend_client import resolve_model_name
from .config import BASE_DIR, data_dir, load_config
from .interview import add_turn, coaching_summary, create_session, list_sessions, load_session, session_summary
from .memory import load_memory, project_id
from .router import pick_agent
from .speech import (
    get_capture_state,
    get_microphone_config,
    get_speech_mode_config,
    set_capture_state,
    set_speech_mode_config,
    speech_mode_status,
    transcribe_microphone_input,
)
from .streaming import stream_task
from .tts import speak_text, speech_supported, stop_speaking
from .voice import get_listen_state, route_transcript, set_listen_state
from .runtime_actions import maybe_execute_runtime_action
from .assistant_core import handle_assistant_core


QML_DIR = Path(__file__).resolve().parent / "qml"
MAIN_QML = QML_DIR / "Main.qml"
UI_SETTINGS_PATH = data_dir() / "desktop_cinematic_settings.json"


def _omnira_dynamic_profile() -> AgentProfile:
    return AgentProfile(
        name="assistant",
        description="Neutral assistant prompt for OMNIRA dynamic routing.",
        system_prompt=(
            "You are Jarvis, a concise and helpful personal assistant. "
            "Respond naturally to general conversation. "
            "When the user asks for technical or project work, provide the task clearly so the backend can route it to the right specialist."
        ),
    )


class JarvisBridge(QObject):
    conversationTextChanged = Signal()
    backendStatusChanged = Signal()
    backendDetailChanged = Signal()
    assistantStateChanged = Signal()
    sceneTitleChanged = Signal()
    sceneHintChanged = Signal()
    stateNarrativeChanged = Signal()
    listenStatusChanged = Signal()
    micStatusChanged = Signal()
    speakerStatusChanged = Signal()
    activeAgentChanged = Signal()
    activeModelChanged = Signal()
    omniraStatusChanged = Signal()
    memoryStatusChanged = Signal()
    workflowStatusChanged = Signal()
    workflowTraceJsonChanged = Signal()
    visualOutputJsonChanged = Signal()
    lastUserTranscriptChanged = Signal()
    lastAssistantReplyChanged = Signal()
    sessionsJsonChanged = Signal()
    selectedSessionIdChanged = Signal()
    selectedSessionTitleChanged = Signal()
    sessionDetailChanged = Signal()
    approvalStatusChanged = Signal()
    approvalHistoryChanged = Signal()
    pendingApprovalsJsonChanged = Signal()
    voiceCaptureStatusChanged = Signal()
    speakerMutedChanged = Signal()
    microphoneMutedChanged = Signal()
    textFallbackVisibleChanged = Signal()
    launchModeChanged = Signal()
    startMinimizedChanged = Signal()
    busyChanged = Signal()
    streamStarted = Signal()
    streamDelta = Signal(str)
    streamFinished = Signal()
    streamErrored = Signal(str)
    voiceTranscriptReady = Signal(str, str)
    voiceCaptureFailed = Signal(str)
    windowCommandRequested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._project_path = str(BASE_DIR)
        self._project_id = project_id(self._project_path)
        self._config = load_config()
        self._conversation_text = (
            "SYSTEM\n"
            "Cinematic shell online. Voice-first command center synchronized with the Jarvis runtime.\n\n"
        )
        self._backend_status = "MODEL CORE // CHECKING"
        self._backend_detail = "Waiting for backend health probe."
        self._assistant_state = "boot"
        self._scene_title = "Booting cinematic shell"
        self._scene_hint = "Synchronizing voice, memory, workflow, and model control layers."
        self._state_narrative = "Jarvis is aligning the cinematic shell with the Python control plane."
        self._listen_status = "AUTO LISTEN // OFF"
        self._mic_status = "MIC // READY"
        self._speaker_status = "SPEAKER // READY"
        self._active_agent = "router"
        self._active_model = self._config.model
        self._omnira_status = "OMNIRA // STANDBY"
        self._memory_status = "MEMORY // COLD"
        self._workflow_status = "WORKFLOW // IDLE"
        self._workflow_trace: list[dict[str, str]] = []
        self._visual_output_json = "[]"
        self._last_user_transcript = "Awaiting voice command."
        self._last_assistant_reply = "Jarvis response channel is ready."
        self._sessions_json = "[]"
        self._selected_session_id = ""
        self._selected_session_title = "No session selected"
        self._session_detail = "Session details will appear here once a local conversation is selected."
        self._approval_status = "APPROVAL HISTORY // EMPTY"
        self._approval_history = "No recorded approvals yet."
        self._pending_approvals_json = "[]"
        self._voice_capture_status = "VOICE // READY"
        self._speaker_muted = False
        self._microphone_muted = False
        self._text_fallback_visible = False
        self._launch_mode = "manual"
        self._start_minimized = True
        self._assistant_chunks: list[str] = []
        self.listen_thread: threading.Thread | None = None
        self.listen_stop_event = threading.Event()
        self._busy = False
        self._interrupt_requested = False
        self._response_interrupted = False

        self._load_ui_settings()
        self._seed_visual_outputs()

        self.streamStarted.connect(self._begin_stream_reply)
        self.streamDelta.connect(self._append_stream_delta)
        self.streamFinished.connect(self._finish_stream_reply)
        self.streamErrored.connect(self._handle_stream_error)
        self.voiceTranscriptReady.connect(self._handle_voice_transcript)
        self.voiceCaptureFailed.connect(self._handle_voice_capture_error)

        self.refresh_status()
        if self._launch_mode == "auto-listen" and not self._microphone_muted:
            self.setListenEnabled(True)

    @Property(str, notify=conversationTextChanged)
    def conversationText(self) -> str:
        return self._conversation_text

    @Property(str, notify=backendStatusChanged)
    def backendStatus(self) -> str:
        return self._backend_status

    @Property(str, notify=backendDetailChanged)
    def backendDetail(self) -> str:
        return self._backend_detail

    @Property(str, notify=assistantStateChanged)
    def assistantState(self) -> str:
        return self._assistant_state

    @Property(str, notify=sceneTitleChanged)
    def sceneTitle(self) -> str:
        return self._scene_title

    @Property(str, notify=sceneHintChanged)
    def sceneHint(self) -> str:
        return self._scene_hint

    @Property(str, notify=stateNarrativeChanged)
    def stateNarrative(self) -> str:
        return self._state_narrative

    @Property(str, notify=listenStatusChanged)
    def listenStatus(self) -> str:
        return self._listen_status

    @Property(str, notify=micStatusChanged)
    def micStatus(self) -> str:
        return self._mic_status

    @Property(str, notify=speakerStatusChanged)
    def speakerStatus(self) -> str:
        return self._speaker_status

    @Property(str, notify=activeAgentChanged)
    def activeAgent(self) -> str:
        return self._active_agent

    @Property(str, notify=activeModelChanged)
    def activeModel(self) -> str:
        return self._active_model

    @Property(str, notify=omniraStatusChanged)
    def omniraStatus(self) -> str:
        return self._omnira_status

    @Property(str, notify=memoryStatusChanged)
    def memoryStatus(self) -> str:
        return self._memory_status

    @Property(str, notify=workflowStatusChanged)
    def workflowStatus(self) -> str:
        return self._workflow_status

    @Property(str, notify=workflowTraceJsonChanged)
    def workflowTraceJson(self) -> str:
        return json.dumps(self._workflow_trace)

    @Property(str, notify=visualOutputJsonChanged)
    def visualOutputJson(self) -> str:
        return self._visual_output_json

    @Property(str, notify=lastUserTranscriptChanged)
    def lastUserTranscript(self) -> str:
        return self._last_user_transcript

    @Property(str, notify=lastAssistantReplyChanged)
    def lastAssistantReply(self) -> str:
        return self._last_assistant_reply

    @Property(str, notify=sessionsJsonChanged)
    def sessionsJson(self) -> str:
        return self._sessions_json

    @Property(str, notify=selectedSessionIdChanged)
    def selectedSessionId(self) -> str:
        return self._selected_session_id

    @Property(str, notify=selectedSessionTitleChanged)
    def selectedSessionTitle(self) -> str:
        return self._selected_session_title

    @Property(str, notify=sessionDetailChanged)
    def sessionDetail(self) -> str:
        return self._session_detail

    @Property(str, notify=approvalStatusChanged)
    def approvalStatus(self) -> str:
        return self._approval_status

    @Property(str, notify=approvalHistoryChanged)
    def approvalHistory(self) -> str:
        return self._approval_history

    @Property(str, notify=pendingApprovalsJsonChanged)
    def pendingApprovalsJson(self) -> str:
        return self._pending_approvals_json

    @Property(str, notify=voiceCaptureStatusChanged)
    def voiceCaptureStatus(self) -> str:
        return self._voice_capture_status

    @Property(bool, notify=speakerMutedChanged)
    def speakerMuted(self) -> bool:
        return self._speaker_muted

    @Property(bool, notify=microphoneMutedChanged)
    def microphoneMuted(self) -> bool:
        return self._microphone_muted

    @Property(bool, notify=textFallbackVisibleChanged)
    def textFallbackVisible(self) -> bool:
        return self._text_fallback_visible

    @Property(str, notify=launchModeChanged)
    def launchMode(self) -> str:
        return self._launch_mode

    @Property(bool, notify=startMinimizedChanged)
    def startMinimized(self) -> bool:
        return self._start_minimized

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot()
    def refreshStatus(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        self._config = load_config()
        ok, msg = check_backend()
        self._backend_status = f"MODEL CORE // {'ONLINE' if ok else 'OFFLINE'}"
        self._backend_detail = msg
        self.backendStatusChanged.emit()
        self.backendDetailChanged.emit()

        self._active_model = self._config.model
        self.activeModelChanged.emit()
        if self._config.backend == "omnira":
            self._omnira_status = "OMNIRA // CONNECTED" if ok else "OMNIRA // OFFLINE"
        else:
            self._omnira_status = "OMNIRA // ADAPTER READY"
        self.omniraStatusChanged.emit()

        listen_state = get_listen_state()
        if self._microphone_muted and listen_state.enabled:
            set_listen_state(False, mode="push-to-talk")
            listen_state = get_listen_state()
        self._listen_status = "AUTO LISTEN // ON" if listen_state.enabled else "AUTO LISTEN // OFF"
        self.listenStatusChanged.emit()

        self._refresh_mic_status()
        self._refresh_speaker_status()
        self._refresh_memory_status()
        self._refresh_sessions()
        self._refresh_approval_status()
        self._refresh_pending_approvals()
        self._refresh_visual_outputs()

        if self._assistant_state == "boot":
            self._set_state(self._fallback_state())

        if not self._workflow_trace:
            self._push_trace("shell.online", "ok", msg)
        self._append_system_line(msg)

    @Slot(bool)
    def setListenEnabled(self, enabled: bool) -> None:
        if self._microphone_muted and enabled:
            self._set_voice_capture_status("VOICE // MIC MUTED")
            self._append_system_line("Live listen blocked because the microphone is muted.")
            self._set_state("muted")
            return

        state = set_listen_state(enabled, mode="continuous" if enabled else "push-to-talk")
        self._listen_status = "AUTO LISTEN // ON" if state.enabled else "AUTO LISTEN // OFF"
        self.listenStatusChanged.emit()
        if enabled:
            self._start_listen_loop()
            self._set_workflow_status("WORKFLOW // LIVE LISTEN ACTIVE")
            self._push_trace("voice.autolisten", "ok", "Continuous microphone intake enabled")
        else:
            self._stop_listen_loop()
            self._set_workflow_status("WORKFLOW // MANUAL VOICE MODE")
            self._push_trace("voice.autolisten", "ok", "Continuous microphone intake disabled")
        self._set_state("listening" if state.enabled else self._fallback_state())
        self._refresh_visual_outputs()

    @Slot()
    def captureVoicePrompt(self) -> None:
        if self._busy:
            return
        if self._microphone_muted:
            self._set_voice_capture_status("VOICE // MIC MUTED")
            self._append_system_line("Push-to-talk blocked because the microphone is muted.")
            self._set_state("muted")
            return
        self._set_voice_capture_status("VOICE // LISTENING")
        self._push_trace("voice.ptt", "running", "Push-to-talk capture armed")
        set_capture_state(True, provider="windows_dictation", mode="push-to-talk")
        self._refresh_mic_status()
        self._set_state("listening")
        worker = threading.Thread(target=self._capture_voice_once, daemon=True)
        worker.start()

    @Slot()
    def toggleSpeakerMuted(self) -> None:
        self._speaker_muted = not self._speaker_muted
        if self._speaker_muted:
            stop_speaking()
            self._set_voice_capture_status("VOICE // SPEAKER MUTED")
            self._push_trace("voice.speaker", "warning", "Speaker muted")
        else:
            self._set_voice_capture_status("VOICE // READY")
            self._push_trace("voice.speaker", "ok", "Speaker unmuted")
        self._refresh_speaker_status()
        self._save_ui_settings()
        self.speakerMutedChanged.emit()
        self._set_state(self._fallback_state())
        self._refresh_visual_outputs()

    @Slot()
    def toggleMicrophoneMuted(self) -> None:
        self._microphone_muted = not self._microphone_muted
        if self._microphone_muted:
            self._stop_listen_loop()
            set_listen_state(False, mode="push-to-talk")
            self._listen_status = "AUTO LISTEN // OFF"
            self.listenStatusChanged.emit()
            self._set_voice_capture_status("VOICE // MIC MUTED")
            self._push_trace("voice.microphone", "warning", "Microphone muted")
        else:
            self._set_voice_capture_status("VOICE // READY")
            self._push_trace("voice.microphone", "ok", "Microphone unmuted")
        self._refresh_mic_status()
        self._save_ui_settings()
        self.microphoneMutedChanged.emit()
        self._set_state(self._fallback_state())
        self._refresh_visual_outputs()

    @Slot()
    def toggleTextFallback(self) -> None:
        self._text_fallback_visible = not self._text_fallback_visible
        self.textFallbackVisibleChanged.emit()
        self._save_ui_settings()

    @Slot()
    def interruptResponse(self) -> None:
        stop_speaking()
        if not self._busy:
            self._set_voice_capture_status("VOICE // READY")
            return
        self._interrupt_requested = True
        self._response_interrupted = True
        self._set_voice_capture_status("VOICE // INTERRUPTING")
        self._set_workflow_status("WORKFLOW // INTERRUPTING")
        self._push_trace("workflow.interrupt", "warning", "User requested interruption")
        self._refresh_visual_outputs()

    @Slot(str)
    def setLaunchMode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        if normalized not in {"manual", "auto-listen"}:
            return
        self._launch_mode = normalized
        self.launchModeChanged.emit()
        self._save_ui_settings()

    @Slot(bool)
    def setStartMinimized(self, enabled: bool) -> None:
        self._start_minimized = bool(enabled)
        self.startMinimizedChanged.emit()
        self._save_ui_settings()

    @Slot(str)
    def createSession(self, title: str) -> None:
        session_title = " ".join(title.strip().split()) or "Primary Conversation"
        session = create_session(session_title)
        self._refresh_sessions(select_session_id=session.id)
        self.loadSession(session.id)
        self._append_system_line(f"Created local session: {session.title}")

    @Slot()
    def refreshSessions(self) -> None:
        self._refresh_sessions(select_session_id=self._selected_session_id or None)
        self._append_system_line("Session matrix refreshed from local storage.")

    @Slot(str)
    def loadSession(self, session_id: str) -> None:
        target = session_id.strip()
        if not target:
            return
        try:
            session = load_session(target)
            summary = session_summary(target)
            coaching = coaching_summary(target)
        except FileNotFoundError as exc:
            self._append_system_line(str(exc))
            self._set_state("error")
            return

        self._selected_session_id = session.id
        self._selected_session_title = session.title
        payload = {
            "session": {
                "id": session.id,
                "created_at": session.created_at,
                "title": session.title,
                "turn_count": len(session.turns),
                "turns": [
                    {
                        "role": turn.role,
                        "text": turn.text,
                        "question_type": turn.question_type,
                    }
                    for turn in session.turns
                ],
            },
            "summary": summary,
            "coaching": coaching,
        }
        self._session_detail = json.dumps(payload, indent=2)
        self.selectedSessionIdChanged.emit()
        self.selectedSessionTitleChanged.emit()
        self.sessionDetailChanged.emit()
        self._refresh_sessions(select_session_id=session.id)

    @Slot()
    def enterApprovalMode(self) -> None:
        self._set_state("approval_required")
        self._set_workflow_status("WORKFLOW // AWAITING APPROVAL")
        self._push_trace("approval.mode", "warning", "Approval overlay engaged")

    @Slot()
    def clearSceneAlert(self) -> None:
        self._set_state(self._fallback_state())
        self._set_workflow_status("WORKFLOW // READY")
        self._append_system_line("Scene overlay returned to normal operation.")

    @Slot()
    def refreshApprovals(self) -> None:
        self._refresh_pending_approvals()
        self._refresh_approval_status()
        self._append_system_line("Approval history refreshed from local records.")

    @Slot(str, str)
    def requestApproval(self, task: str, note: str = "") -> None:
        normalized = " ".join(task.strip().split())
        if not normalized:
            self._append_system_line("Approval request ignored because no concrete task text was provided.")
            return
        approval = create_pending_approval(normalized, source="desktop.cinematic", note=note)
        self._refresh_pending_approvals()
        self._set_state("approval_required")
        self._set_workflow_status("WORKFLOW // APPROVAL REQUIRED")
        self._push_trace("approval.request", "warning", approval.task)
        self._append_system_line(f"Approval request staged: {approval.task}")
        self._refresh_visual_outputs()

    @Slot(str)
    def queueDesktopAction(self, action_name: str) -> None:
        action_map = {
            "copy": "Copy the selected desktop item to a new destination",
            "move": "Move the selected desktop item to another folder",
            "search": "Search my desktop and files for the requested item",
            "download": "Download the requested file or artifact to my machine",
            "open": "Open the requested desktop app or file",
            "recover": "Inspect the current desktop error and recover from the failure safely",
        }
        task = action_map.get(action_name.strip().lower())
        if not task:
            self._append_system_line(f"Unsupported desktop operator action: {action_name}")
            self._set_state("error")
            return
        self.requestApproval(task, "Desktop operator quick action")

    @Slot(str)
    def approvePending(self, approval_id: str) -> None:
        self._set_state("executing")
        self._set_workflow_status("WORKFLOW // EXECUTING APPROVED ACTION")
        self._push_trace("approval.execute", "running", approval_id)
        self._resolve_pending_approval(approval_id, "approved")

    @Slot(str)
    def rejectPending(self, approval_id: str) -> None:
        self._resolve_pending_approval(approval_id, "rejected")

    @Slot(str)
    def sendMessage(self, message: str) -> None:
        text = message.strip()
        if not text or self._busy:
            return

        self._set_last_user_transcript(text)
        self._append_section("YOU", text)
        self._append_to_selected_session("user", text)
        self._set_workflow_status("WORKFLOW // ROUTING REQUEST")
        self._push_trace("voice.command", "ok", text[:96])
        self._refresh_visual_outputs()
        self._set_state("thinking")

        local_command = self._detect_window_command(text)
        if local_command is not None:
            command, acknowledgement = local_command
            self._handle_local_window_command(command, acknowledgement, text)
            return

        assistant_result = handle_assistant_core(
            text,
            project_path=self._project_path,
            backend_status=self._backend_status,
            backend_detail=self._backend_detail,
            active_model=self._active_model,
        )
        if assistant_result.handled:
            self._set_last_assistant_reply(assistant_result.message)
            self._append_section("JARVIS", assistant_result.message)
            self._append_to_selected_session("assistant", assistant_result.message)
            self._set_workflow_status("WORKFLOW // ASSISTANT CORE")
            self._push_trace("assistant.core", "ok", assistant_result.intent or "assistant")
            if not self._speaker_muted:
                self._set_voice_capture_status("VOICE // SPEAKING")
                self._speak_reply_async(assistant_result.message)
            self._refresh_visual_outputs()
            self._set_state(self._fallback_state())
            return

        runtime_result = maybe_execute_runtime_action(
            text,
            self._project_path,
            profile="personal",
            approve_runtime=False,
            source="desktop.cinematic",
            note="Desktop cinematic command",
        )
        if runtime_result.handled:
            self._set_last_assistant_reply(runtime_result.message)
            self._append_section("JARVIS", runtime_result.message)
            self._append_to_selected_session("assistant", runtime_result.message)
            if runtime_result.approval_id:
                self._refresh_pending_approvals()
                self._refresh_approval_status()
                self._set_state("approval_required")
                self._set_workflow_status("WORKFLOW // APPROVAL REQUIRED")
                self._push_trace("runtime.action", "warning", f"{runtime_result.action} queued")
            else:
                self._set_workflow_status("WORKFLOW // ACTION EXECUTED")
                self._push_trace("runtime.action", "ok", runtime_result.action or "runtime")
                if not self._speaker_muted:
                    self._set_voice_capture_status("VOICE // SPEAKING")
                    self._speak_reply_async(runtime_result.message)
            self._refresh_visual_outputs()
            self._set_state(self._fallback_state())
            return

        self._busy = True
        self._interrupt_requested = False
        self._response_interrupted = False
        self.busyChanged.emit()

        worker = threading.Thread(target=self._run_stream, args=(text,), daemon=True)
        worker.start()

    def _run_stream(self, text: str) -> None:
        try:
            cfg = load_config()
            dynamic_routing = False
            if cfg.backend == "omnira":
                agent_name = "omnira-prime"
                agent = _omnira_dynamic_profile()
                model_name = resolve_model_name(agent.name, agent.model, cfg, dynamic_routing=True) or "dynamic"
                dynamic_routing = True
            else:
                agent_name = pick_agent(text)
                agent = get_agent(agent_name)
                model_name = resolve_model_name(agent.name, agent.model, cfg)
            self._active_agent = agent_name
            self._active_model = model_name
            self.activeAgentChanged.emit()
            self.activeModelChanged.emit()
            self._set_workflow_status(f"WORKFLOW // {agent_name.upper()} ACTIVE")
            self._push_trace("router.pick", "ok", f"{agent_name} -> {model_name}")
            self._set_state("executing")
            self.streamStarted.emit()
            for chunk in stream_task(text, agent, self._project_path, source="desktop.cinematic", dynamic_routing=dynamic_routing):
                if self._interrupt_requested:
                    self._response_interrupted = True
                    break
                self.streamDelta.emit(chunk)
            self.streamFinished.emit()
        except Exception as exc:
            self.streamErrored.emit(str(exc))

    @Slot()
    def _begin_stream_reply(self) -> None:
        self._set_state("speaking")
        self._set_workflow_status("WORKFLOW // RESPONSE STREAMING")
        self._push_trace("backend.stream", "running", f"{self._config.backend} -> {self._active_model}")
        self._assistant_chunks = []
        self._conversation_text += "JARVIS\n"
        self.conversationTextChanged.emit()

    @Slot(str)
    def _append_stream_delta(self, chunk: str) -> None:
        self._assistant_chunks.append(chunk)
        self._conversation_text += chunk
        self.conversationTextChanged.emit()

    @Slot()
    def _finish_stream_reply(self) -> None:
        self._conversation_text += "\n\n"
        self.conversationTextChanged.emit()
        assistant_text = "".join(self._assistant_chunks).strip()
        if assistant_text:
            self._set_last_assistant_reply(assistant_text)
            self._append_to_selected_session("assistant", assistant_text)
            if self._response_interrupted:
                self._set_voice_capture_status("VOICE // INTERRUPTED")
                self._push_trace("backend.stream", "warning", "Response interrupted before completion")
            elif self._speaker_muted:
                self._set_voice_capture_status("VOICE // SPEAKER MUTED")
                self._push_trace("voice.speaker", "warning", "Reply generated but speaker is muted")
            else:
                self._set_voice_capture_status("VOICE // SPEAKING")
                self._speak_reply_async(assistant_text)
                self._push_trace("backend.stream", "ok", f"Completed {len(assistant_text)} chars")
        else:
            self._push_trace("backend.stream", "warning", "No assistant text returned")

        self._set_workflow_status("WORKFLOW // INTERRUPTED" if self._response_interrupted else "WORKFLOW // READY")
        self._refresh_memory_status()
        self._refresh_visual_outputs()
        self._set_state(self._fallback_state())
        self._busy = False
        self.busyChanged.emit()

    @Slot(str)
    def _handle_stream_error(self, message: str) -> None:
        self._append_system_line(f"Response failed: {message}")
        self._set_workflow_status("WORKFLOW // ERROR")
        self._push_trace("backend.error", "error", message)
        self._set_state("error")
        self._busy = False
        self.busyChanged.emit()
        self._refresh_visual_outputs()

    def _set_state(self, state: str) -> None:
        title, hint, narrative = self._describe_state(state)
        changed = state != self._assistant_state
        self._assistant_state = state
        self._scene_title = title
        self._scene_hint = hint
        self._state_narrative = narrative
        if changed:
            self.assistantStateChanged.emit()
        self.sceneTitleChanged.emit()
        self.sceneHintChanged.emit()
        self.stateNarrativeChanged.emit()

    def _describe_state(self, state: str) -> tuple[str, str, str]:
        if state == "boot":
            return (
                "Booting cinematic shell",
                "Synchronizing voice, memory, workflow, and model layers.",
                "Jarvis is aligning the command center with the Python control plane.",
            )
        if state == "idle":
            return (
                "Core stable",
                "Jarvis is present and awaiting a voice command.",
                "The command center is quiet, but model, memory, and workflow surfaces remain online.",
            )
        if state == "listening":
            return (
                "Listening field open",
                "Microphone intake is active and voice capture is ready.",
                "The AI core shifts into intake mode and holds the command center open for speech.",
            )
        if state == "thinking":
            return (
                "Reasoning loop engaged",
                "Routing the request through agent selection and backend planning.",
                "Jarvis is selecting the right runtime path before response generation begins.",
            )
        if state == "executing":
            return (
                "Workflow executing",
                "A live backend or supervised action is in flight.",
                "The command center emphasizes runtime trace and control while work progresses.",
            )
        if state == "speaking":
            return (
                "Speaking response",
                "The reply channel is active and the voice core is responding.",
                "The shell increases signal density while Jarvis streams and speaks the response.",
            )
        if state == "muted":
            return (
                "Muted supervision",
                "One or more voice channels are muted.",
                "The command center remains live, but voice intake or speech output is intentionally suppressed.",
            )
        if state == "approval_required":
            return (
                "Approval required",
                "A supervised action is paused for explicit confirmation.",
                "Jarvis is holding the workflow at the approval gate until you decide.",
            )
        if state == "error":
            return (
                "Error state detected",
                "A backend, workflow, or voice channel fault occurred.",
                "The command center shifts into error emphasis so the failure stays visible and recoverable.",
            )
        return (
            "Core stable",
            "Jarvis is ready.",
            "The command center is ready for the next state transition.",
        )

    def _append_section(self, label: str, body: str) -> None:
        self._conversation_text += f"{label}\n{body}\n\n"
        self.conversationTextChanged.emit()

    def _append_system_line(self, body: str) -> None:
        self._conversation_text += f"SYSTEM\n{body}\n\n"
        self.conversationTextChanged.emit()

    def _refresh_mic_status(self) -> None:
        if self._microphone_muted:
            self._mic_status = "MIC // MUTED"
        else:
            mic_config = get_microphone_config()
            capture_state = get_capture_state()
            speech_config = get_speech_mode_config()
            device_label = str(mic_config.device).upper()
            capture_label = "LIVE" if capture_state.active else "READY"
            speech_label = speech_config.language_mode.upper()
            self._mic_status = f"MIC // {device_label} // {capture_label} // {speech_label}"
        self.micStatusChanged.emit()

    def _refresh_speaker_status(self) -> None:
        if not speech_supported():
            self._speaker_status = "SPEAKER // UNSUPPORTED"
        elif self._speaker_muted:
            self._speaker_status = "SPEAKER // MUTED"
        else:
            self._speaker_status = "SPEAKER // READY"
        self.speakerStatusChanged.emit()

    def _refresh_memory_status(self) -> None:
        memory_text = load_memory(self._project_id)
        if not memory_text.strip():
            self._memory_status = "MEMORY // COLD"
        else:
            entry_count = max(1, memory_text.count("### Run Summary"))
            self._memory_status = f"MEMORY // {entry_count} SUMMARIES // {len(memory_text)} CHARS"
        self.memoryStatusChanged.emit()

    def _set_voice_capture_status(self, value: str) -> None:
        self._voice_capture_status = value
        self.voiceCaptureStatusChanged.emit()

    def _set_last_user_transcript(self, text: str) -> None:
        self._last_user_transcript = text.strip() or "Awaiting voice command."
        self.lastUserTranscriptChanged.emit()

    def _set_last_assistant_reply(self, text: str) -> None:
        self._last_assistant_reply = text.strip() or "Jarvis response channel is ready."
        self.lastAssistantReplyChanged.emit()

    def _set_workflow_status(self, value: str) -> None:
        self._workflow_status = value
        self.workflowStatusChanged.emit()

    def _push_trace(self, step: str, status: str, detail: str) -> None:
        self._workflow_trace.insert(
            0,
            {
                "ts": time.strftime("%H:%M:%S"),
                "step": step,
                "status": status,
                "detail": detail,
            },
        )
        self._workflow_trace = self._workflow_trace[:10]
        self.workflowTraceJsonChanged.emit()

    def _seed_visual_outputs(self) -> None:
        self._visual_output_json = json.dumps(
            [
                {
                    "kind": "card",
                    "title": "Response Surface",
                    "body": "Cards, diagrams, tables, metrics, and workflow output will appear here when Jarvis runs work.",
                },
                {
                    "kind": "timeline",
                    "title": "Workflow Timeline",
                    "items": ["Shell online", "Awaiting voice command"],
                },
                {
                    "kind": "tree",
                    "title": "Task Tree",
                    "items": ["Voice intent pending", "Agent routing pending", "Execution pending"],
                },
                {
                    "kind": "metrics",
                    "title": "Runtime Metrics",
                    "metrics": [
                        {"label": "State", "value": "IDLE"},
                        {"label": "Backend", "value": self._config.backend.upper()},
                        {"label": "Model", "value": self._config.model},
                    ],
                },
            ]
        )

    def _refresh_visual_outputs(self) -> None:
        timeline = [f"{item['ts']}  {item['step']}  {item['status']}" for item in self._workflow_trace[:4]] or ["Awaiting command"]
        table_rows = [
            ["Agent", self._active_agent],
            ["Model", self._active_model],
            ["Backend", self._backend_status],
            ["OMNIRA", self._omnira_status],
            ["Speech", get_speech_mode_config().language_mode.upper()],
        ]
        metrics = [
            {"label": "State", "value": self._assistant_state.upper()},
            {"label": "Voice", "value": self._voice_capture_status.replace("VOICE // ", "")},
            {"label": "Memory", "value": self._memory_status.replace("MEMORY // ", "")},
        ]
        tree_items = [
            self._workflow_status,
            self._scene_hint,
            f"Approval pending: {len(json.loads(self._pending_approvals_json))}",
        ]
        payload = [
            {
                "kind": "card",
                "title": "Response Surface",
                "body": self._last_assistant_reply,
            },
            {
                "kind": "timeline",
                "title": "Workflow Timeline",
                "items": timeline,
            },
            {
                "kind": "tree",
                "title": "Task Tree",
                "items": tree_items,
            },
            {
                "kind": "table",
                "title": "Runtime Table",
                "rows": table_rows,
            },
            {
                "kind": "metrics",
                "title": "Voice Metrics",
                "metrics": metrics,
            },
        ]
        self._visual_output_json = json.dumps(payload)
        self.visualOutputJsonChanged.emit()

    def _speak_reply_async(self, text: str) -> None:
        if self._speaker_muted:
            self._set_voice_capture_status("VOICE // SPEAKER MUTED")
            return
        if not speech_supported():
            self._set_voice_capture_status("VOICE // NO TTS")
            return

        def worker() -> None:
            if not speak_text(text):
                self._set_voice_capture_status("VOICE // TTS FAILED")
                return
            fallback = "VOICE // LIVE LISTEN" if get_listen_state().enabled else "VOICE // READY"
            self._set_voice_capture_status(fallback)

        threading.Thread(target=worker, daemon=True).start()

    def _detect_window_command(self, transcript: str) -> tuple[str, str] | None:
        lowered = " ".join(transcript.lower().split())
        if not lowered:
            return None

        if "unmute speaker" in lowered or "speaker on" in lowered:
            return ("unmute-speaker", "Speaker channel restored.")
        if "mute speaker" in lowered or "speaker off" in lowered:
            return ("mute-speaker", "Speaker channel muted.")
        if "unmute mic" in lowered or "microphone on" in lowered or "unmute microphone" in lowered:
            return ("unmute-mic", "Microphone channel restored.")
        if "mute mic" in lowered or "mute microphone" in lowered or "microphone off" in lowered:
            return ("mute-mic", "Microphone channel muted.")
        if "auto listen on" in lowered or "enable auto listen" in lowered:
            return ("auto-listen-on", "Auto listen enabled.")
        if "auto listen off" in lowered or "disable auto listen" in lowered:
            return ("auto-listen-off", "Auto listen disabled.")
        if any(token in lowered for token in ["test voice", "speaker test", "jarvis speak", "say something jarvis"]):
            return ("voice-test", "Jarvis voice channel is online.")
        if any(token in lowered for token in ["english mode", "switch to english", "english listening mode"]):
            return ("speech-mode:english", "English mode selected.")
        if any(token in lowered for token in ["hinglish mode", "switch to hinglish", "mixed language mode"]):
            return ("speech-mode:hinglish", "Hinglish mode selected.")
        if any(token in lowered for token in ["hindi mode", "switch to hindi", "hindi listening mode"]):
            return ("speech-mode:hindi", "Hindi mode selected.")
        if any(token in lowered for token in ["maximize jarvis", "fullscreen jarvis", "full screen jarvis", "maximize window"]):
            return ("maximize", "Opening Jarvis in full cinematic mode.")
        if any(token in lowered for token in ["restore jarvis", "restore window", "normal size"]):
            return ("restore", "Restoring Jarvis to standard command center size.")
        if any(token in lowered for token in ["minimize jarvis", "collapse jarvis", "hide jarvis", "minimize window"]):
            return ("minimize", "Collapsing Jarvis to the corner orb.")
        if any(token in lowered for token in ["center jarvis", "move jarvis center", "move to center"]):
            return ("move:center", "Moving Jarvis to the center.")
        if any(token in lowered for token in ["top left", "upper left"]):
            return ("move:top-left", "Moving Jarvis to the top left.")
        if any(token in lowered for token in ["top right", "upper right"]):
            return ("move:top-right", "Moving Jarvis to the top right.")
        if any(token in lowered for token in ["bottom left", "lower left"]):
            return ("move:bottom-left", "Moving Jarvis to the bottom left.")
        if any(token in lowered for token in ["bottom right", "lower right"]):
            return ("move:bottom-right", "Moving Jarvis to the bottom right.")
        return None

    def _handle_local_window_command(self, command: str, acknowledgement: str, transcript: str) -> None:
        if command == "mute-speaker" and not self._speaker_muted:
            self.toggleSpeakerMuted()
        elif command == "unmute-speaker" and self._speaker_muted:
            self.toggleSpeakerMuted()
        elif command == "mute-mic" and not self._microphone_muted:
            self.toggleMicrophoneMuted()
        elif command == "unmute-mic" and self._microphone_muted:
            self.toggleMicrophoneMuted()
        elif command == "auto-listen-on":
            self.setListenEnabled(True)
        elif command == "auto-listen-off":
            self.setListenEnabled(False)
        elif command.startswith("speech-mode:"):
            language_mode = command.split(":", 1)[1]
            set_speech_mode_config(language_mode=language_mode)
            status = speech_mode_status()
            acknowledgement = f"{language_mode.title()} mode selected. {status['detail']}"
            self._refresh_mic_status()
        else:
            self.windowCommandRequested.emit(command)

        self._set_last_user_transcript(transcript)
        self._set_last_assistant_reply(acknowledgement)
        self._append_section("YOU", transcript)
        self._append_section("JARVIS", acknowledgement)
        self._set_workflow_status("WORKFLOW // LOCAL WINDOW CONTROL")
        self._push_trace("window.control", "ok", command)
        self._set_state("executing")
        self._refresh_visual_outputs()
        if command != "mute-speaker":
            self._set_voice_capture_status("VOICE // SPEAKING")
            self._speak_reply_async(acknowledgement)
        self._set_state(self._fallback_state())

    def _capture_voice_once(self) -> None:
        try:
            result = transcribe_microphone_input(duration_s=6, provider="windows_dictation")
            route = route_transcript(result.transcript)
            self.voiceTranscriptReady.emit(route.normalized_task, "push-to-talk")
        except Exception as exc:
            self.voiceCaptureFailed.emit(str(exc))

    def _start_listen_loop(self) -> None:
        if self.listen_thread is not None and self.listen_thread.is_alive():
            return
        self.listen_stop_event.clear()
        set_capture_state(True, provider="windows_dictation", mode="continuous")
        self._refresh_mic_status()
        self._set_voice_capture_status("VOICE // LIVE LISTEN")
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

    def _stop_listen_loop(self) -> None:
        self.listen_stop_event.set()
        set_capture_state(False, provider="windows_dictation", mode="continuous")
        self._refresh_mic_status()
        if not self._microphone_muted:
            self._set_voice_capture_status("VOICE // READY")

    def _listen_loop(self) -> None:
        while not self.listen_stop_event.is_set():
            if self._busy or self._microphone_muted:
                time.sleep(0.4)
                continue
            try:
                result = transcribe_microphone_input(duration_s=4, provider="windows_dictation", allow_empty=True)
            except Exception as exc:
                self.voiceCaptureFailed.emit(str(exc))
                time.sleep(1.0)
                continue
            if self.listen_stop_event.is_set():
                break
            transcript = " ".join(result.transcript.split())
            if not transcript:
                continue
            route = route_transcript(transcript)
            self.voiceTranscriptReady.emit(route.normalized_task, "live-listen")

    @Slot(str, str)
    def _handle_voice_transcript(self, transcript: str, source: str) -> None:
        set_capture_state(
            get_listen_state().enabled,
            provider="windows_dictation",
            mode="continuous" if get_listen_state().enabled else "push-to-talk",
        )
        self._refresh_mic_status()
        label = "VOICE // LIVE" if source == "live-listen" else "VOICE // CAPTURED"
        self._set_voice_capture_status(f"{label} // {transcript[:64]}")
        local_command = self._detect_window_command(transcript)
        if local_command is not None:
            command, acknowledgement = local_command
            self._handle_local_window_command(command, acknowledgement, transcript)
            return
        self._set_last_user_transcript(transcript)
        self._push_trace("voice.transcript", "ok", transcript[:96])
        self.sendMessage(transcript)

    @Slot(str)
    def _handle_voice_capture_error(self, message: str) -> None:
        if not get_listen_state().enabled:
            set_capture_state(False, provider="windows_dictation", mode="push-to-talk")
            self._refresh_mic_status()
            self._set_voice_capture_status("VOICE // FAILED")
        self._append_system_line(f"Voice capture warning: {message}")
        self._push_trace("voice.error", "error", message)
        self._set_workflow_status("WORKFLOW // VOICE ERROR")
        self._set_state("error")
        self._refresh_visual_outputs()

    def _append_to_selected_session(self, role: str, text: str) -> None:
        session_id = self._selected_session_id.strip()
        if not session_id:
            return
        try:
            add_turn(session_id, role, text)
        except FileNotFoundError as exc:
            self._append_system_line(str(exc))
            self._set_state("error")
            return
        self._sync_selected_session_detail()

    def _sync_selected_session_detail(self) -> None:
        session_id = self._selected_session_id.strip()
        if not session_id:
            return
        try:
            session = load_session(session_id)
            summary = session_summary(session_id)
            coaching = coaching_summary(session_id)
        except FileNotFoundError as exc:
            self._append_system_line(str(exc))
            self._set_state("error")
            return

        self._selected_session_title = session.title
        payload = {
            "session": {
                "id": session.id,
                "created_at": session.created_at,
                "title": session.title,
                "turn_count": len(session.turns),
                "turns": [
                    {
                        "role": turn.role,
                        "text": turn.text,
                        "question_type": turn.question_type,
                    }
                    for turn in session.turns
                ],
            },
            "summary": summary,
            "coaching": coaching,
        }
        self._session_detail = json.dumps(payload, indent=2)
        self.selectedSessionTitleChanged.emit()
        self.sessionDetailChanged.emit()
        self._refresh_sessions(select_session_id=session.id)

    def _refresh_sessions(self, select_session_id: str | None = None) -> None:
        sessions = list_sessions(limit=50)
        payload: list[dict[str, object]] = []
        for session in sessions:
            payload.append(
                {
                    "id": session.id,
                    "title": session.title,
                    "turn_count": len(session.turns),
                    "created_at": session.created_at,
                    "selected": session.id == (select_session_id or self._selected_session_id),
                }
            )
        self._sessions_json = json.dumps(payload)
        self.sessionsJsonChanged.emit()

        if select_session_id:
            self._selected_session_id = select_session_id
            self.selectedSessionIdChanged.emit()

        if not sessions and not self._selected_session_id:
            self._selected_session_title = "No session selected"
            self._session_detail = "Session details will appear here once a local conversation is selected."
            self.selectedSessionTitleChanged.emit()
            self.sessionDetailChanged.emit()

    def _refresh_pending_approvals(self) -> None:
        payload = [asdict(item) for item in list_pending_approvals()]
        self._pending_approvals_json = json.dumps(payload)
        self.pendingApprovalsJsonChanged.emit()

    def _refresh_approval_status(self) -> None:
        approval_dir = data_dir() / "approvals"
        pending_count = len(list_pending_approvals())
        if not approval_dir.exists():
            self._approval_status = f"APPROVALS // {pending_count} PENDING // 0 HISTORY"
            self._approval_history = "No recorded approvals yet."
            self.approvalStatusChanged.emit()
            self.approvalHistoryChanged.emit()
            return

        items = sorted(approval_dir.glob("*.md"), reverse=True)
        if not items:
            self._approval_status = f"APPROVALS // {pending_count} PENDING // 0 HISTORY"
            self._approval_history = "No recorded approvals yet."
        else:
            latest = items[0]
            latest_text = latest.read_text(encoding="utf-8")
            preview_lines = [line.strip() for line in latest_text.splitlines() if line.strip()][:8]
            self._approval_status = f"APPROVALS // {pending_count} PENDING // {len(items)} HISTORY"
            self._approval_history = "\n".join(preview_lines)
        self.approvalStatusChanged.emit()
        self.approvalHistoryChanged.emit()

    def _resolve_pending_approval(self, approval_id: str, decision: str) -> None:
        try:
            item = resolve_pending_approval(approval_id, decision)
        except FileNotFoundError as exc:
            self._append_system_line(str(exc))
            self._set_state("error")
            return
        self._refresh_pending_approvals()
        self._refresh_approval_status()
        self._append_system_line(f"Approval {item.status}: {item.task}")
        self._push_trace("approval.result", "ok", f"{item.status}: {item.task}")
        if item.status == "approved":
            result = maybe_execute_runtime_action(
                item.task,
                self._project_path,
                profile="personal",
                approve_runtime=True,
                source="desktop.cinematic.approval",
                note=item.note,
                stage_approval=False,
            )
            self._append_system_line(result.message)
        self._set_workflow_status("WORKFLOW // READY")
        self._set_state(self._fallback_state())
        self._refresh_visual_outputs()

    def _fallback_state(self) -> str:
        if self._microphone_muted or self._speaker_muted:
            return "muted"
        if self._listen_status == "AUTO LISTEN // ON":
            return "listening"
        return "idle"

    def _load_ui_settings(self) -> None:
        defaults = {
            "speaker_muted": False,
            "microphone_muted": False,
            "text_fallback_visible": False,
            "launch_mode": "auto-listen",
            "start_minimized": False,
        }
        if UI_SETTINGS_PATH.exists():
            try:
                data = json.loads(UI_SETTINGS_PATH.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
        merged = {**defaults, **data}
        self._speaker_muted = bool(merged["speaker_muted"])
        self._microphone_muted = bool(merged["microphone_muted"])
        self._text_fallback_visible = bool(merged["text_fallback_visible"])
        self._launch_mode = str(merged["launch_mode"] or "manual")
        self._start_minimized = bool(merged["start_minimized"])

    def _save_ui_settings(self) -> None:
        payload = {
            "speaker_muted": self._speaker_muted,
            "microphone_muted": self._microphone_muted,
            "text_fallback_visible": self._text_fallback_visible,
            "launch_mode": self._launch_mode,
            "start_minimized": self._start_minimized,
        }
        UI_SETTINGS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def start_cinematic_desktop() -> None:
    QQuickStyle.setStyle("Fusion")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()
    bridge = JarvisBridge()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))

    if not engine.rootObjects():
        raise RuntimeError(f"Failed to load QML shell: {MAIN_QML}")

    app.exec()
