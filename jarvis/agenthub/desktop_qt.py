from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
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
from .backend_client import JarvisOMNIRAResponse, resolve_model_name
from .config import BASE_DIR, data_dir, load_config
from .interview import add_turn, coaching_summary, create_session, list_sessions, load_session, session_summary
from .memory import load_memory, project_id
from .memory_control import load_memory_control_state
from .router import pick_agent
from .speech import (
    get_capture_state,
    get_microphone_config,
    get_speech_mode_config,
    resolve_speech_provider,
    set_capture_state,
    set_speech_mode_config,
    speech_mode_status,
    transcribe_microphone_input,
)
from .streaming import stream_task
from .tts import speak_text, speech_supported, stop_speaking
from .voice import get_listen_state, live_listen_accepts_transcript, route_transcript, set_listen_state
from .runtime_actions import maybe_execute_runtime_action
from .assistant_core import handle_assistant_core, should_use_fast_assistant_route
from .commander import JarvisCommander
from .contracts import OwnerCommand
from .interaction_log import InteractionRecord, write_interaction_record
from .owner_profile import (
    aliases_text,
    bind_owner_name,
    learn_from_message,
    load_owner_profile,
    notes_text,
    preferences_text,
    replace_aliases,
    replace_notes,
    replace_preferences,
    set_response_style,
    summarize_owner_profile,
)
from .response_envelope import JarvisResponseEnvelope, build_response_envelope
from .secure_storage import iter_json_like_files, read_json_file
from .ui_state import DEFAULT_UI_MODE, DEFAULT_UI_STATE, mode_shows_operations, normalize_ui_mode, normalize_ui_state


QML_DIR = Path(__file__).resolve().parent / "qml"
MAIN_QML = QML_DIR / "Main.qml"
UI_SETTINGS_PATH = data_dir() / "desktop_cinematic_settings.json"


def _omnira_dynamic_profile(adaptive_context: str = "") -> AgentProfile:
    adaptive_suffix = f" Owner adaptation context: {adaptive_context}" if adaptive_context else ""
    return AgentProfile(
        name="assistant",
        description="Neutral assistant prompt for OMNIRA dynamic routing.",
        system_prompt=(
            "You are Jarvis, a concise and helpful personal assistant. "
            "Respond naturally to general conversation. "
            "When the user asks for technical or project work, provide the task clearly so the backend can route it to the right specialist."
            + adaptive_suffix
        ),
    )


def _omnira_fast_profile(adaptive_context: str = "") -> AgentProfile:
    adaptive_suffix = f" Owner adaptation context: {adaptive_context}" if adaptive_context else ""
    return AgentProfile(
        name="assistant-lite",
        description="Fast assistant prompt for lightweight OMNIRA turns.",
        system_prompt=(
            "You are Jarvis, a fast and concise personal assistant. "
            "Answer short conversational prompts directly. "
            "Do not expand into long explanations unless the user explicitly asks for depth."
            + adaptive_suffix
        ),
        model="omnira-lite-qwen-3b-v0.1",
    )


class JarvisBridge(QObject):
    conversationTextChanged = Signal()
    backendStatusChanged = Signal()
    backendDetailChanged = Signal()
    assistantStateChanged = Signal()
    uiStateChanged = Signal()
    uiModeChanged = Signal()
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
    responseEnvelopeJsonChanged = Signal()
    lastUserTranscriptChanged = Signal()
    lastAssistantReplyChanged = Signal()
    ownerProfileSummaryChanged = Signal()
    ownerPreferencesTextChanged = Signal()
    ownerAliasesTextChanged = Signal()
    ownerNotesTextChanged = Signal()
    ownerResponseStyleChanged = Signal()
    routeSummaryChanged = Signal()
    latencySummaryChanged = Signal()
    cockpitSummaryJsonChanged = Signal()
    speechModeSummaryChanged = Signal()
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
    operationsVisibleChanged = Signal()
    debugModeEnabledChanged = Signal()
    approvalModeVisibleChanged = Signal()
    wakeWordEnabledChanged = Signal()
    showOperationsByDefaultChanged = Signal()
    omniraEndpointChanged = Signal()
    launchModeChanged = Signal()
    startMinimizedChanged = Signal()
    ownerNameChanged = Signal()
    ownerKnownChanged = Signal()
    cameraConsentChanged = Signal()
    voiceLearningEnabledChanged = Signal()
    lowLatencyVoiceChanged = Signal()
    busyChanged = Signal()
    streamStarted = Signal()
    streamDelta = Signal(str)
    streamFinished = Signal()
    streamErrored = Signal(str)
    commanderResponseReady = Signal(str)
    commanderResponseErrored = Signal(str)
    voiceTranscriptReady = Signal(str, str)
    voiceCaptureProgress = Signal(str)
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
        self._assistant_state = DEFAULT_UI_STATE
        self._ui_mode = DEFAULT_UI_MODE
        self._operations_visible = False
        self._debug_mode_enabled = False
        self._wake_word_enabled = True
        self._show_operations_by_default = False
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
        self._response_envelope = build_response_envelope(state=self._assistant_state)
        self._last_user_transcript = "Awaiting voice command."
        self._last_assistant_reply = "Jarvis response channel is ready."
        self._owner_profile_summary = "No learned owner profile yet."
        self._owner_preferences_text = ""
        self._owner_aliases_text = ""
        self._owner_notes_text = ""
        self._route_summary = "ROUTE // STANDBY"
        self._latency_summary = "LATENCY // WAITING"
        self._cockpit_summary_json = "{}"
        self._speech_mode_summary = "SPEECH // ENGLISH // AUTO"
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
        self._omnira_endpoint = self._config.base_url
        self._owner_name = ""
        self._camera_consent = False
        self._voice_learning_enabled = False
        self._low_latency_voice = True
        self._owner_prompted = False
        self._owner_profile = load_owner_profile()
        self._owner_profile_summary = summarize_owner_profile(self._owner_profile) or "No learned owner profile yet."
        self._owner_preferences_text = preferences_text(self._owner_profile)
        self._owner_aliases_text = aliases_text(self._owner_profile)
        self._owner_notes_text = notes_text(self._owner_profile)
        self._assistant_chunks: list[str] = []
        self.listen_thread: threading.Thread | None = None
        self.listen_stop_event = threading.Event()
        self._busy = False
        self._interrupt_requested = False
        self._response_interrupted = False
        self._stream_started_at = 0.0
        self._stream_first_token_ms: int | None = None
        self._latest_stream_contract = JarvisOMNIRAResponse()
        self._commander = JarvisCommander(project_path=self._project_path, profile="personal", stage_approvals=True)

        self._load_ui_settings()
        self._seed_visual_outputs()

        self.streamStarted.connect(self._begin_stream_reply)
        self.streamDelta.connect(self._append_stream_delta)
        self.streamFinished.connect(self._finish_stream_reply)
        self.streamErrored.connect(self._handle_stream_error)
        self.commanderResponseReady.connect(self._handle_commander_response)
        self.commanderResponseErrored.connect(self._handle_commander_error)
        self.voiceTranscriptReady.connect(self._handle_voice_transcript)
        self.voiceCaptureProgress.connect(self._set_voice_capture_status)
        self.voiceCaptureFailed.connect(self._handle_voice_capture_error)

        self.refresh_status()
        self._prime_owner_onboarding()
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

    @Property(str, notify=uiStateChanged)
    def uiState(self) -> str:
        return self._assistant_state

    @Property(str, notify=uiModeChanged)
    def uiMode(self) -> str:
        return self._ui_mode

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

    @Property(str, notify=responseEnvelopeJsonChanged)
    def responseEnvelopeJson(self) -> str:
        return self._response_envelope.to_json()

    @Property(str, notify=lastUserTranscriptChanged)
    def lastUserTranscript(self) -> str:
        return self._last_user_transcript

    @Property(str, notify=lastAssistantReplyChanged)
    def lastAssistantReply(self) -> str:
        return self._last_assistant_reply

    @Property(str, notify=ownerProfileSummaryChanged)
    def ownerProfileSummary(self) -> str:
        return self._owner_profile_summary

    @Property(str, notify=ownerPreferencesTextChanged)
    def ownerPreferencesText(self) -> str:
        return self._owner_preferences_text

    @Property(str, notify=ownerAliasesTextChanged)
    def ownerAliasesText(self) -> str:
        return self._owner_aliases_text

    @Property(str, notify=ownerNotesTextChanged)
    def ownerNotesText(self) -> str:
        return self._owner_notes_text

    @Property(str, notify=ownerResponseStyleChanged)
    def ownerResponseStyle(self) -> str:
        return self._owner_profile.response_style

    @Property(str, notify=routeSummaryChanged)
    def routeSummary(self) -> str:
        return self._route_summary

    @Property(str, notify=latencySummaryChanged)
    def latencySummary(self) -> str:
        return self._latency_summary

    @Property(str, notify=cockpitSummaryJsonChanged)
    def cockpitSummaryJson(self) -> str:
        return self._cockpit_summary_json

    @Property(str, notify=speechModeSummaryChanged)
    def speechModeSummary(self) -> str:
        return self._speech_mode_summary

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

    @Property(bool, notify=operationsVisibleChanged)
    def operationsVisible(self) -> bool:
        return self._operations_visible

    @Property(bool, notify=debugModeEnabledChanged)
    def debugModeEnabled(self) -> bool:
        return self._debug_mode_enabled

    @Property(bool, notify=approvalModeVisibleChanged)
    def approvalModeVisible(self) -> bool:
        return self._ui_mode == "approval"

    @Property(bool, notify=wakeWordEnabledChanged)
    def wakeWordEnabled(self) -> bool:
        return self._wake_word_enabled

    @Property(bool, notify=showOperationsByDefaultChanged)
    def showOperationsByDefault(self) -> bool:
        return self._show_operations_by_default

    @Property(str, notify=omniraEndpointChanged)
    def omniraEndpoint(self) -> str:
        return self._omnira_endpoint

    @Property(str, notify=launchModeChanged)
    def launchMode(self) -> str:
        return self._launch_mode

    @Property(bool, notify=startMinimizedChanged)
    def startMinimized(self) -> bool:
        return self._start_minimized

    @Property(str, notify=ownerNameChanged)
    def ownerName(self) -> str:
        return self._owner_name

    @Property(bool, notify=ownerKnownChanged)
    def ownerKnown(self) -> bool:
        return bool(self._owner_name.strip())

    @Property(bool, notify=cameraConsentChanged)
    def cameraConsent(self) -> bool:
        return self._camera_consent

    @Property(bool, notify=voiceLearningEnabledChanged)
    def voiceLearningEnabled(self) -> bool:
        return self._voice_learning_enabled

    @Property(bool, notify=lowLatencyVoiceChanged)
    def lowLatencyVoice(self) -> bool:
        return self._low_latency_voice

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Slot()
    def refreshStatus(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        self._config = load_config()
        self._owner_profile = load_owner_profile()
        self._refresh_owner_profile_summary()
        ok, msg = check_backend()
        self._backend_status = f"MODEL CORE // {'ONLINE' if ok else 'OFFLINE'}"
        self._backend_detail = msg
        self.backendStatusChanged.emit()
        self.backendDetailChanged.emit()

        self._active_model = self._config.model
        self.activeModelChanged.emit()
        self._omnira_endpoint = self._config.base_url
        self.omniraEndpointChanged.emit()
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
        self._refresh_cockpit_summary()
        self._refresh_visual_outputs()

        self._set_state(self._fallback_state())

        if not self._workflow_trace:
            self._push_trace("shell.online", "ok", msg)
        self._append_system_line(msg)
        self._prime_owner_onboarding()

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
        set_capture_state(True, provider=resolve_speech_provider(prefer_realtime=False), mode="push-to-talk")
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
    def openOperations(self) -> None:
        self._set_ui_mode("operations")
        self._append_system_line("Operations overlay opened.")

    @Slot()
    def hideOperations(self) -> None:
        if self._assistant_state == "approval_required":
            self._set_ui_mode("approval")
            self._append_system_line("Approval view remains active until the pending decision is resolved.")
            return
        if self._debug_mode_enabled:
            self._set_ui_mode("debug")
            self._append_system_line("Debug mode keeps operations visible until developer mode is exited.")
            return
        self._set_ui_mode(DEFAULT_UI_MODE)
        self._append_system_line("Operations overlay hidden.")

    @Slot()
    def enterDebugMode(self) -> None:
        self._set_ui_mode("debug")
        self._push_trace("ui.mode", "warning", "Debug mode enabled")

    @Slot()
    def exitDebugMode(self) -> None:
        self._debug_mode_enabled = False
        self.debugModeEnabledChanged.emit()
        if self._assistant_state == "approval_required":
            self._set_ui_mode("approval")
        else:
            self._set_ui_mode(DEFAULT_UI_MODE)
        self._push_trace("ui.mode", "ok", "Debug mode disabled")

    @Slot(str)
    def showApproval(self, action: str) -> None:
        summary = " ".join(action.strip().split())
        if summary:
            self._append_system_line(f"Approval summary: {summary}")
        self._set_ui_mode("approval")

    @Slot()
    def openConversationMode(self) -> None:
        self._set_ui_mode("conversation")

    @Slot()
    def openInsightMode(self) -> None:
        self._set_ui_mode("insight")

    @Slot()
    def openPresenceMode(self) -> None:
        self._set_ui_mode("presence")

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

    @Slot(bool)
    def setWakeWordEnabled(self, enabled: bool) -> None:
        self._wake_word_enabled = bool(enabled)
        self.wakeWordEnabledChanged.emit()
        self._save_ui_settings()

    @Slot(bool)
    def setShowOperationsByDefault(self, enabled: bool) -> None:
        self._show_operations_by_default = bool(enabled)
        self.showOperationsByDefaultChanged.emit()
        self._save_ui_settings()

    @Slot(str)
    def setDefaultUiMode(self, mode: str) -> None:
        normalized = normalize_ui_mode(mode)
        if normalized not in {"presence", "conversation", "insight"}:
            return
        self._set_ui_mode(normalized)
        self._save_ui_settings()

    @Slot(str)
    def setOwnerName(self, name: str) -> None:
        self._complete_owner_onboarding(name, source="settings")

    @Slot(str)
    def setOwnerResponseStyle(self, style: str) -> None:
        self._owner_profile = set_response_style(style)
        self._refresh_owner_profile_summary()
        self._append_system_line(f"Owner response style set to {self._owner_profile.response_style}.")

    @Slot(str)
    def saveOwnerPreferences(self, raw_text: str) -> None:
        self._owner_profile = replace_preferences(raw_text)
        self._refresh_owner_profile_summary()
        self._append_system_line("Saved owner preferences.")

    @Slot(str)
    def saveOwnerAliases(self, raw_text: str) -> None:
        self._owner_profile = replace_aliases(raw_text)
        self._refresh_owner_profile_summary()
        self._append_system_line("Saved owner phrase mappings.")

    @Slot(str)
    def saveOwnerNotes(self, raw_text: str) -> None:
        self._owner_profile = replace_notes(raw_text)
        self._refresh_owner_profile_summary()
        self._append_system_line("Saved owner adaptation notes.")

    @Slot(bool)
    def setCameraConsent(self, enabled: bool) -> None:
        next_value = bool(enabled)
        if self._camera_consent == next_value:
            return
        self._camera_consent = next_value
        self.cameraConsentChanged.emit()
        self._save_ui_settings()
        status = "Camera consent recorded. Face enrollment can be wired on top of this local profile." if next_value else "Camera consent removed. Visual owner recognition stays disabled."
        self._append_system_line(status)
        self._push_trace("owner.camera_consent", "ok", str(next_value).lower())
        self._refresh_cockpit_summary()
        self._refresh_visual_outputs()

    @Slot(bool)
    def setVoiceLearningEnabled(self, enabled: bool) -> None:
        next_value = bool(enabled)
        if self._voice_learning_enabled == next_value:
            return
        self._voice_learning_enabled = next_value
        self.voiceLearningEnabledChanged.emit()
        self._save_ui_settings()
        status = "Voice learning is enabled. Jarvis will retain this preference while deeper accent modeling is still being wired." if next_value else "Voice learning preference disabled."
        self._append_system_line(status)
        self._push_trace("owner.voice_learning", "ok", str(next_value).lower())
        self._refresh_cockpit_summary()
        self._refresh_visual_outputs()

    @Slot(bool)
    def setLowLatencyVoice(self, enabled: bool) -> None:
        next_value = bool(enabled)
        if self._low_latency_voice == next_value:
            return
        self._low_latency_voice = next_value
        self.lowLatencyVoiceChanged.emit()
        self._save_ui_settings()
        status = "Low-latency voice mode enabled. Capture windows are shorter so Jarvis can respond faster." if next_value else "Low-latency voice mode disabled. Longer capture windows may improve longer utterances."
        self._append_system_line(status)
        self._push_trace("voice.latency_mode", "ok", str(next_value).lower())
        self._refresh_cockpit_summary()
        self._refresh_visual_outputs()

    @Slot(str)
    def setSpeechLanguageMode(self, mode: str) -> None:
        normalized = str(mode or "").strip().lower()
        if normalized not in {"english", "hinglish", "hindi"}:
            return
        set_speech_mode_config(language_mode=normalized)
        status = speech_mode_status()
        self._append_system_line(f"Speech mode set to {normalized}. {status.get('detail', '')}".strip())
        self._push_trace("voice.language", "ok", normalized)
        self._refresh_mic_status()
        self._refresh_cockpit_summary()
        self._refresh_visual_outputs()

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

    @Slot(str)
    def setUiMode(self, mode: str) -> None:
        self._set_ui_mode(mode)

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

        self._owner_profile, learned_items = learn_from_message(text)
        self._refresh_owner_profile_summary()
        if learned_items:
            self._push_trace("owner.learn", "ok", ", ".join(learned_items[:3]))

        self._set_last_user_transcript(text)
        self._append_section("YOU", text)
        self._append_to_selected_session("user", text)
        self._set_workflow_status("WORKFLOW // ROUTING REQUEST")
        self._set_route_summary("ROUTE // DECIDING")
        self._set_latency_summary("LATENCY // PENDING")
        self._push_trace("voice.command", "ok", text[:96])
        self._refresh_visual_outputs()
        self._set_state("thinking")

        if not self.ownerKnown:
            self._complete_owner_onboarding(text, source="conversation")
            return

        local_command = self._detect_window_command(text)
        if local_command is not None:
            command, acknowledgement = local_command
            self._handle_local_window_command(command, acknowledgement, text)
            return

        self._busy = True
        self._interrupt_requested = False
        self._response_interrupted = False
        self.busyChanged.emit()

        worker = threading.Thread(target=self._run_commander_turn, args=(text,), daemon=True)
        worker.start()

    def _run_commander_turn(self, text: str) -> None:
        try:
            response = self._commander.handle_owner_command(
                OwnerCommand(
                    text=text,
                    source="desktop_cinematic",
                    context={"ui_mode": self._ui_mode, "surface": "desktop_qt"},
                    metadata={"channel": "desktop"},
                )
            )
            self.commanderResponseReady.emit(response.to_json())
        except Exception as exc:
            self.commanderResponseErrored.emit(str(exc))

    @Slot(str)
    def _handle_commander_response(self, response_json: str) -> None:
        payload = json.loads(response_json)
        envelope = build_response_envelope(**payload)

        reply_text = envelope.reply_text or envelope.speech_text or "Jarvis completed the request."
        self._active_agent = envelope.agent or self._active_agent
        self._active_model = envelope.model or self._active_model
        self.activeAgentChanged.emit()
        self.activeModelChanged.emit()

        self._set_last_assistant_reply(reply_text)
        self._append_section("JARVIS", reply_text)
        self._append_to_selected_session("assistant", reply_text)

        route_label = f"ROUTE // {self._active_agent.upper()} // {self._active_model}"
        if envelope.approval_required:
            route_label += " // APPROVAL"
        self._set_route_summary(route_label)
        self._set_latency_summary("LATENCY // COMMANDER ROUTED")
        if envelope.approval_required:
            self._set_workflow_status("WORKFLOW // APPROVAL REQUIRED")
        elif envelope.provider == "assistant_core":
            self._set_workflow_status("WORKFLOW // ASSISTANT CORE")
        elif envelope.provider == "local-runtime":
            self._set_workflow_status("WORKFLOW // LOCAL RUNTIME")
        else:
            self._set_workflow_status("WORKFLOW // COMMAND COMPLETE")

        self._push_trace(
            "commander.response",
            "warning" if envelope.approval_required else "ok",
            envelope.intent or envelope.agent or "response",
        )
        self._publish_response_envelope(envelope)
        self._refresh_cockpit_summary()
        self._refresh_pending_approvals()
        self._refresh_approval_status()
        self._refresh_visual_outputs()

        if envelope.approval_required:
            self._set_state("approval_required")
        else:
            self._set_state(envelope.state or self._fallback_state())
            if not self._speaker_muted and envelope.speech_text:
                self._set_voice_capture_status("VOICE // SPEAKING")
                self._speak_reply_async(envelope.speech_text)
            self._set_state(self._fallback_state())

        self._busy = False
        self.busyChanged.emit()

    @Slot(str)
    def _handle_commander_error(self, message: str) -> None:
        self._append_system_line(f"Commander failed: {message}")
        self._set_last_assistant_reply("I hit an internal error while processing that request.")
        self._set_latency_summary("LATENCY // ERROR")
        self._set_workflow_status("WORKFLOW // COMMANDER ERROR")
        self._push_trace("commander.response", "error", message)
        self._refresh_visual_outputs()
        self._busy = False
        self.busyChanged.emit()
        self._set_state("error")

    def _run_stream(self, text: str) -> None:
        try:
            self._stream_started_at = time.perf_counter()
            self._stream_first_token_ms = None
            self._latest_stream_contract = JarvisOMNIRAResponse()
            cfg = load_config()
            adaptive_context = summarize_owner_profile(self._owner_profile)
            dynamic_routing = False
            if cfg.backend == "omnira":
                if should_use_fast_assistant_route(text):
                    agent_name = "omnira-lite"
                    agent = _omnira_fast_profile(adaptive_context)
                    model_name = resolve_model_name(agent.name, agent.model, cfg) or agent.model or "omnira-lite-qwen-3b-v0.1"
                else:
                    agent_name = "omnira-prime"
                    agent = _omnira_dynamic_profile(adaptive_context)
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
            self._set_route_summary(f"ROUTE // {agent_name.upper()} // {model_name}")
            self._set_workflow_status(f"WORKFLOW // {agent_name.upper()} ACTIVE")
            self._push_trace("router.pick", "ok", f"{agent_name} -> {model_name}")
            self._set_state("executing")
            self.streamStarted.emit()
            for chunk in stream_task(
                text,
                agent,
                self._project_path,
                source="desktop.cinematic",
                dynamic_routing=dynamic_routing,
                stream_event_callback=self._capture_stream_contract,
            ):
                if self._interrupt_requested:
                    self._response_interrupted = True
                    break
                if self._stream_first_token_ms is None:
                    self._stream_first_token_ms = int((time.perf_counter() - self._stream_started_at) * 1000)
                    self._set_latency_summary(f"LATENCY // FIRST TOKEN {self._stream_first_token_ms}MS")
                    self._push_trace("stream.first_token", "ok", f"{self._stream_first_token_ms} ms")
                    self._set_workflow_status(f"WORKFLOW // STREAMING // FIRST TOKEN {self._stream_first_token_ms}MS")
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
        partial_text = "".join(self._assistant_chunks).strip()
        if partial_text:
            envelope = self._compose_response_envelope(
                reply_text=partial_text,
                speech_text="",
                state="speaking",
                intent=self._latest_stream_contract.intent or "backend_response",
                agent=self._latest_stream_contract.agent or self._active_agent,
                model=self._latest_stream_contract.model or self._active_model,
                provider=self._latest_stream_contract.provider,
                confidence=self._latest_stream_contract.confidence or 0.5,
                decision_path=self._latest_stream_contract.decision_path,
                memory_hits=self._normalize_memory_hit_labels(self._latest_stream_contract.memory_hits),
                tool_calls=self._latest_stream_contract.tool_calls,
                workflow_trace=self._normalize_workflow_trace(self._latest_stream_contract.workflow_trace),
                visualization=self._latest_stream_contract.visualization,
                safety_flags=self._latest_stream_contract.safety_flags,
                approval_required=self._latest_stream_contract.approval_required,
                risk_level=self._latest_stream_contract.risk_level,
                metadata=self._latest_stream_contract.metadata,
            )
            self._publish_response_envelope(envelope)

    @Slot()
    def _finish_stream_reply(self) -> None:
        total_ms = int((time.perf_counter() - self._stream_started_at) * 1000) if self._stream_started_at else 0
        if self._stream_first_token_ms is not None:
            self._set_latency_summary(f"LATENCY // FIRST {self._stream_first_token_ms}MS // TOTAL {total_ms}MS")
        else:
            self._set_latency_summary(f"LATENCY // TOTAL {total_ms}MS")
        self._conversation_text += "\n\n"
        self.conversationTextChanged.emit()
        assistant_text = "".join(self._assistant_chunks).strip()
        if assistant_text:
            envelope = self._compose_response_envelope(
                reply_text=assistant_text,
                speech_text="" if self._speaker_muted or self._response_interrupted else assistant_text,
                state="speaking" if not self._speaker_muted and not self._response_interrupted else self._fallback_state(),
                intent=self._latest_stream_contract.intent or "backend_response",
                agent=self._latest_stream_contract.agent or self._active_agent,
                model=self._latest_stream_contract.model or self._active_model,
                provider=self._latest_stream_contract.provider,
                confidence=self._latest_stream_contract.confidence or 0.82,
                decision_path=self._latest_stream_contract.decision_path,
                memory_hits=self._normalize_memory_hit_labels(self._latest_stream_contract.memory_hits),
                tool_calls=self._latest_stream_contract.tool_calls,
                workflow_trace=self._normalize_workflow_trace(self._latest_stream_contract.workflow_trace),
                visualization=self._latest_stream_contract.visualization,
                safety_flags=self._latest_stream_contract.safety_flags,
                approval_required=self._latest_stream_contract.approval_required,
                risk_level=self._latest_stream_contract.risk_level,
                error=self._latest_stream_contract.error,
                metadata=self._latest_stream_contract.metadata,
            )
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
                first_token_detail = f"; first token {self._stream_first_token_ms} ms" if self._stream_first_token_ms is not None else ""
                self._push_trace("backend.stream", "ok", f"Completed {len(assistant_text)} chars in {total_ms} ms{first_token_detail}")
            self._publish_response_envelope(envelope)
            self._record_interaction(
                source="backend_stream",
                transcript=self._last_user_transcript,
                envelope=envelope,
                success=not self._response_interrupted,
                memory_saved=True,
                training_candidate=not self._response_interrupted,
            )
        else:
            self._push_trace("backend.stream", "warning", "No assistant text returned")

        if self._response_interrupted:
            self._set_workflow_status("WORKFLOW // INTERRUPTED")
        else:
            self._set_workflow_status(f"WORKFLOW // READY // TOTAL {total_ms}MS")
        self._refresh_memory_status()
        self._refresh_visual_outputs()
        self._set_state(self._fallback_state())
        self._busy = False
        self.busyChanged.emit()
        self._stream_started_at = 0.0

    @Slot(str)
    def _handle_stream_error(self, message: str) -> None:
        self._append_system_line(f"Response failed: {message}")
        self._set_workflow_status("WORKFLOW // ERROR")
        self._set_latency_summary("LATENCY // FAILED")
        self._push_trace("backend.error", "error", message)
        self._set_state("error")
        envelope = self._compose_response_envelope(
            reply_text="",
            speech_text="",
            state="error",
            intent="backend_error",
            agent=self._active_agent,
            model=self._active_model,
            provider=self._latest_stream_contract.provider,
            confidence=0.0,
            decision_path=self._latest_stream_contract.decision_path,
            memory_hits=self._normalize_memory_hit_labels(self._latest_stream_contract.memory_hits),
            tool_calls=[],
            workflow_trace=self._normalize_workflow_trace(self._latest_stream_contract.workflow_trace),
            visualization=self._latest_stream_contract.visualization,
            safety_flags=self._latest_stream_contract.safety_flags,
            approval_required=False,
            risk_level="medium",
            error={"kind": "backend", "message": message},
            metadata=self._latest_stream_contract.metadata,
        )
        self._publish_response_envelope(envelope)
        self._record_interaction(
            source="backend_stream",
            transcript=self._last_user_transcript,
            envelope=envelope,
            success=False,
            memory_saved=False,
            training_candidate=False,
        )
        self._busy = False
        self.busyChanged.emit()
        self._refresh_visual_outputs()

    def _set_state(self, state: str) -> None:
        state = normalize_ui_state(state, fallback=self._fallback_state())
        title, hint, narrative = self._describe_state(state)
        changed = state != self._assistant_state
        self._assistant_state = state
        self._scene_title = title
        self._scene_hint = hint
        self._state_narrative = narrative
        if changed:
            self.assistantStateChanged.emit()
            self.uiStateChanged.emit()
        self.sceneTitleChanged.emit()
        self.sceneHintChanged.emit()
        self.stateNarrativeChanged.emit()
        self._sync_ui_mode_with_state()

    def _set_ui_mode(self, mode: str) -> None:
        normalized = normalize_ui_mode(mode)
        mode_changed = normalized != self._ui_mode
        next_operations_visible = mode_shows_operations(normalized)
        next_debug_mode = normalized == "debug"
        operations_changed = next_operations_visible != self._operations_visible
        debug_changed = next_debug_mode != self._debug_mode_enabled

        self._ui_mode = normalized
        self._operations_visible = next_operations_visible
        self._debug_mode_enabled = next_debug_mode

        if mode_changed:
            self.uiModeChanged.emit()
        if operations_changed:
            self.operationsVisibleChanged.emit()
        if debug_changed:
            self.debugModeEnabledChanged.emit()
        self.approvalModeVisibleChanged.emit()

    def _sync_ui_mode_with_state(self) -> None:
        if self._assistant_state == "approval_required":
            self._set_ui_mode("approval")
            return
        if self._assistant_state == "error" and not self._debug_mode_enabled:
            self._set_ui_mode("operations")
            return
        if self._debug_mode_enabled:
            self._set_ui_mode("debug")
            return
        if self._ui_mode == "approval":
            self._set_ui_mode(DEFAULT_UI_MODE)

    def _describe_state(self, state: str) -> tuple[str, str, str]:
        owner = self._owner_name.strip()
        owner_label = owner if owner else "owner"
        if state == "disconnected":
            return (
                "Connection standby",
                "Jarvis is ready locally but the active backend channel is not connected.",
                "The shell stays available for local controls while the OMNIRA or model endpoint reconnects.",
            )
        if state == "idle":
            return (
                f"Standing by for {owner_label}" if owner else "Core stable",
                f"Jarvis is present and awaiting {owner_label}'s next command." if owner else "Jarvis is present and awaiting a voice command.",
                f"The command center recognizes {owner_label} and remains ready for conversation and supervised actions." if owner else "The command center is quiet, but model, memory, and workflow surfaces remain online.",
            )
        if state == "listening":
            return (
                "Listening field open",
                f"Microphone intake is active and waiting for {owner_label}." if owner else "Microphone intake is active and voice capture is ready.",
                f"The AI core is tuned to {owner_label}'s current turn and holds the command center open for speech." if owner else "The AI core shifts into intake mode and holds the command center open for speech.",
            )
        if state == "transcribing":
            return (
                "Transcribing voice",
                "Jarvis is converting the captured utterance into a routed command.",
                "The shell is briefly in transcript normalization before intent routing resumes.",
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

    def _normalize_owner_name(self, raw: str) -> str:
        cleaned = " ".join(raw.strip().split())
        lowered = cleaned.lower()
        for prefix in ("my name is ", "i am ", "i'm ", "this is ", "it is ", "its "):
            if lowered.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                break
        cleaned = cleaned.strip(" .,!?")
        return cleaned[:48]

    def _prime_owner_onboarding(self) -> None:
        if self.ownerKnown or self._owner_prompted:
            return
        self._owner_prompted = True
        self._scene_title = "Identify your owner"
        self._scene_hint = "Tell Jarvis your name so it can greet and personalize the shell."
        self._state_narrative = "Owner onboarding is active. Local identity should be bound before camera recognition and deeper personalization are added."
        self.sceneTitleChanged.emit()
        self.sceneHintChanged.emit()
        self.stateNarrativeChanged.emit()
        self._set_last_assistant_reply("Welcome. I need your owner name before I personalize this shell.")
        self._append_system_line("Welcome. Tell me your name and I will bind this shell to your local owner profile. Camera recognition is not wired yet, but this is the first identity layer.")
        self._set_workflow_status("WORKFLOW // OWNER ONBOARDING")

    def _complete_owner_onboarding(self, raw_name: str, *, source: str) -> None:
        owner_name = self._normalize_owner_name(raw_name)
        if not owner_name:
            message = "I did not catch the owner name. Tell me your name clearly so I can personalize the shell."
            self._set_last_assistant_reply(message)
            self._append_section("JARVIS", message)
            self._set_workflow_status("WORKFLOW // OWNER ONBOARDING")
            self._push_trace("owner.profile", "warning", "Owner name missing")
            self._refresh_visual_outputs()
            self._set_state("idle")
            return

        self._owner_name = owner_name
        self._owner_profile = bind_owner_name(owner_name)
        self._refresh_owner_profile_summary()
        self._owner_prompted = False
        self.ownerNameChanged.emit()
        self.ownerKnownChanged.emit()
        self._save_ui_settings()
        self._set_workflow_status("WORKFLOW // OWNER PROFILE BOUND")
        self._push_trace("owner.profile", "ok", f"Bound to {owner_name} via {source}")
        greeting = (
            f"Welcome, {owner_name}. I know who I am serving now. I will use your local owner profile for greetings and personalization. "
            "Camera recognition, face verification, and deeper accent learning are the next capability layers to wire in."
        )
        self._set_last_assistant_reply(greeting)
        self._append_section("JARVIS", greeting)
        self._refresh_visual_outputs()
        self._set_state(self._fallback_state())
        if not self._speaker_muted:
            self._set_voice_capture_status("VOICE // SPEAKING")
            self._speak_reply_async(greeting)

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
        speech_config = get_speech_mode_config()
        active_provider = resolve_speech_provider(speech_config, prefer_realtime=get_listen_state().enabled)
        self._speech_mode_summary = f"SPEECH // {speech_config.language_mode.upper()} // {active_provider.upper()}"
        self.micStatusChanged.emit()
        self.speechModeSummaryChanged.emit()

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

    def _refresh_owner_profile_summary(self) -> None:
        self._owner_profile_summary = summarize_owner_profile(self._owner_profile) or "No learned owner profile yet."
        self._owner_preferences_text = preferences_text(self._owner_profile)
        self._owner_aliases_text = aliases_text(self._owner_profile)
        self._owner_notes_text = notes_text(self._owner_profile)
        self.ownerProfileSummaryChanged.emit()
        self.ownerPreferencesTextChanged.emit()
        self.ownerAliasesTextChanged.emit()
        self.ownerNotesTextChanged.emit()
        self.ownerResponseStyleChanged.emit()

    def _set_route_summary(self, value: str) -> None:
        self._route_summary = value
        self.routeSummaryChanged.emit()
        self._refresh_cockpit_summary()

    def _set_latency_summary(self, value: str) -> None:
        self._latency_summary = value
        self.latencySummaryChanged.emit()
        self._refresh_cockpit_summary()

    def _set_workflow_status(self, value: str) -> None:
        self._workflow_status = value
        self.workflowStatusChanged.emit()
        self._refresh_cockpit_summary()

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
                    "kind": "command_result",
                    "title": "Awaiting Request",
                    "body": "Insight Mode becomes active once Jarvis completes a turn.",
                },
                {
                    "kind": "status_cards",
                    "title": "Runtime",
                    "metrics": [
                        {"label": "State", "value": "IDLE"},
                        {"label": "Mode", "value": self._ui_mode.upper()},
                        {"label": "Backend", "value": self._config.backend.upper()},
                    ],
                },
                {
                    "kind": "workflow_trace",
                    "title": "Flow",
                    "items": ["Shell online", "Awaiting command"],
                },
            ]
        )
        self._publish_response_envelope(self._compose_response_envelope(state=self._assistant_state, intent="shell_ready", agent="jarvis-shell", model="local-ui", confidence=1.0))

    def _refresh_visual_outputs(self) -> None:
        envelope = self._response_envelope
        runtime_metrics = [
            {"label": "State", "value": envelope.state.upper() if envelope.state else self._assistant_state.upper()},
            {"label": "Risk", "value": envelope.risk_level.upper()},
            {"label": "Approval", "value": "YES" if envelope.approval_required else "NO"},
            {"label": "Provider", "value": (envelope.provider or "unknown").upper()},
            {"label": "Memory", "value": str(len(envelope.memory_hits))},
            {"label": "Tools", "value": str(len(envelope.tool_calls))},
        ]
        decision_items = envelope.decision_path or [f"state:{envelope.state or self._assistant_state}"]
        workflow_items = [
            f"{item.get('ts', '')}  {item.get('step', '')}  {item.get('status', '')}".strip()
            for item in (envelope.workflow_trace or self._workflow_trace[:6])
        ]
        response_title = str(envelope.visualization.get("title") or envelope.intent or envelope.agent or "Response").replace("_", " ").title()
        runtime_rows = [
            ["Agent", envelope.agent or self._active_agent or "jarvis"],
            ["Model", envelope.model or self._active_model or self._config.model],
            ["Backend", self._backend_status.replace("MODEL CORE // ", "")],
            ["Voice", self._voice_capture_status.replace("VOICE // ", "")],
            ["Route", " > ".join((envelope.decision_path or [])[:3]) or self._route_summary.replace("ROUTE // ", "")],
        ]
        payload = [
            {
                "kind": "command_result",
                "title": response_title,
                "body": envelope.reply_text or self._last_assistant_reply,
            },
            {
                "kind": "status_cards",
                "title": "Runtime",
                "metrics": runtime_metrics,
            },
            {
                "kind": "workflow_trace",
                "title": "Decision Path",
                "items": [str(item) for item in decision_items[:6]],
            },
            {
                "kind": "comparison_table",
                "title": "Execution",
                "rows": runtime_rows,
            },
        ]
        if workflow_items:
            payload.append(
                {
                    "kind": "workflow_trace",
                    "title": "Recent Trace",
                    "items": workflow_items[:6],
                }
            )
        visualization = dict(envelope.visualization or {})
        visualization_type = str(visualization.get("type") or "").strip().lower()
        if visualization_type == "status_cards":
            payload.insert(
                0,
                {
                    "kind": "status_cards",
                    "title": str(visualization.get("title") or "Status Cards"),
                    "metrics": [
                        {
                            "label": str(item.get("label") or "State"),
                            "value": str(item.get("value") or ""),
                        }
                        for item in visualization.get("items", [])
                        if isinstance(item, dict)
                    ],
                },
            )
        elif visualization_type == "timeline":
            payload.insert(
                0,
                {
                    "kind": "timeline",
                    "title": str(visualization.get("title") or "Timeline"),
                    "items": [str(item) for item in visualization.get("items", [])],
                },
            )
        elif visualization_type == "task_tree":
            payload.insert(
                0,
                {
                    "kind": "task_tree",
                    "title": str(visualization.get("title") or "Task Tree"),
                    "items": [str(item) for item in visualization.get("items", [])],
                },
            )
        elif visualization_type == "comparison_table":
            payload.insert(
                0,
                {
                    "kind": "comparison_table",
                    "title": str(visualization.get("title") or "Comparison Table"),
                    "rows": [[str(cell) for cell in row[:2]] for row in visualization.get("rows", []) if isinstance(row, list)],
                },
            )
        elif visualization_type == "command_result":
            payload.insert(
                0,
                {
                    "kind": "command_result",
                    "title": str(visualization.get("title") or "Command Result"),
                    "body": str(visualization.get("body") or envelope.reply_text or self._last_assistant_reply),
                },
            )
        elif visualization_type == "memory_used":
            payload.insert(
                0,
                {
                    "kind": "memory_used",
                    "title": str(visualization.get("title") or "Memory Used"),
                    "items": self._normalize_memory_hit_labels(list(visualization.get("items", []))) or envelope.memory_hits,
                },
            )
        elif visualization_type == "workflow_trace":
            payload.insert(
                0,
                {
                    "kind": "workflow_trace",
                    "title": str(visualization.get("title") or "Workflow Trace"),
                    "items": [str(item) for item in visualization.get("items", [])] or timeline,
                },
            )
        else:
            payload[0] = {
                "kind": "command_result",
                "title": str(visualization.get("title") or response_title),
                "body": str(visualization.get("body") or envelope.reply_text or self._last_assistant_reply),
            }
        if envelope.memory_hits:
            payload.append(
                {
                    "kind": "memory_used",
                    "title": "Memory Hits",
                    "items": envelope.memory_hits,
                }
            )
        if envelope.tool_calls:
            payload.append(
                {
                    "kind": "comparison_table",
                    "title": "Tool Calls",
                    "rows": [[item.get("name", "tool"), item.get("status", "unknown")] for item in envelope.tool_calls],
                }
            )
        if envelope.safety_flags:
            payload.append(
                {
                    "kind": "workflow_trace",
                    "title": "Safety Flags",
                    "items": [str(item) for item in envelope.safety_flags],
                }
            )
        self._visual_output_json = json.dumps(payload)
        self.visualOutputJsonChanged.emit()

    def _publish_response_envelope(self, envelope: JarvisResponseEnvelope) -> None:
        self._response_envelope = envelope
        self.responseEnvelopeJsonChanged.emit()

    def _compose_response_envelope(
        self,
        *,
        reply_text: str = "",
        speech_text: str = "",
        state: str,
        intent: str,
        agent: str,
        model: str,
        provider: str = "",
        confidence: float,
        decision_path: list[str] | None = None,
        memory_hits: list[str] | None = None,
        tool_calls: list[dict[str, object]] | None = None,
        workflow_trace: list[dict[str, str]] | None = None,
        visualization: dict[str, object] | None = None,
        safety_flags: list[str] | None = None,
        approval_required: bool = False,
        risk_level: str = "low",
        error: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> JarvisResponseEnvelope:
        return build_response_envelope(
            reply_text=reply_text,
            speech_text=speech_text,
            state=state,
            intent=intent,
            agent=agent,
            model=model,
            provider=provider,
            confidence=confidence,
            decision_path=list(decision_path or []),
            memory_hits=list(memory_hits or self._current_memory_hits()),
            tool_calls=[dict(item) for item in (tool_calls or [])],
            workflow_trace=[dict(item) for item in (workflow_trace or self._workflow_trace[:10])],
            visualization=dict(visualization or {
                "title": "Response Surface" if not approval_required else "Approval Surface",
                "body": reply_text or self._last_assistant_reply,
            }),
            safety_flags=list(safety_flags or []),
            approval_required=approval_required,
            risk_level=risk_level,
            error=error,
            metadata=dict(metadata or {}),
        )

    def _current_memory_hits(self) -> list[str]:
        if self._memory_status == "MEMORY // COLD":
            return []
        return [self._memory_status]

    def _record_interaction(
        self,
        *,
        source: str,
        transcript: str,
        envelope: JarvisResponseEnvelope,
        success: bool,
        memory_saved: bool,
        training_candidate: bool,
        feedback: str = "",
    ) -> None:
        record = InteractionRecord(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            project_id=self._project_id,
            source=source,
            ui_mode=self._ui_mode,
            user_command=transcript,
            transcript=transcript,
            detected_intent=envelope.intent,
            selected_agent=envelope.agent,
            selected_model=envelope.model,
            provider=envelope.provider,
            workflow_steps=[dict(item) for item in envelope.workflow_trace],
            reply_text=envelope.reply_text,
            speech_text=envelope.speech_text,
            user_feedback=feedback,
            memory_hits_count=len(envelope.memory_hits),
            tool_calls_count=len(envelope.tool_calls),
            success=success,
            memory_saved=memory_saved,
            training_candidate=training_candidate,
            approval_required=envelope.approval_required,
            risk_level=envelope.risk_level,
            error=envelope.error,
            metadata={
                "confidence": envelope.confidence,
                "decision_path": envelope.decision_path,
                "safety_flags": envelope.safety_flags,
                **envelope.metadata,
            },
        )
        try:
            path = write_interaction_record(self._project_id, record)
            self._push_trace("interaction.record", "ok", path.name)
            self._refresh_cockpit_summary()
        except Exception as exc:
            self._push_trace("interaction.record", "error", str(exc))

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

        if any(token in lowered for token in ["open operations panel", "show operations panel", "open operations", "show operations"]):
            return ("open-operations", "Opening the operations panel.")
        if any(token in lowered for token in ["hide operations panel", "close operations panel", "hide operations", "close operations"]):
            return ("hide-operations", "Hiding the operations panel.")
        if any(token in lowered for token in ["show workflow", "show workflow trace", "show runtime details"]):
            return ("show-workflow", f"Opening workflow trace. {self._workflow_status}.")
        if any(token in lowered for token in ["show backend status", "backend status", "show omnira status"]):
            return ("show-backend", f"Opening backend status. {self._backend_status}. {self._omnira_status}.")
        if any(token in lowered for token in ["show model used", "show model", "which model are you using"]):
            return ("show-model", f"Current model lane is {self._active_model}.")
        if any(token in lowered for token in ["show memory used", "show memory", "memory status"]):
            return ("show-memory", f"Current memory status is {self._memory_status}.")
        if any(token in lowered for token in ["enter debug mode", "enable debug mode", "debug mode on"]):
            return ("debug-on", "Entering debug mode.")
        if any(token in lowered for token in ["exit debug mode", "disable debug mode", "debug mode off"]):
            return ("debug-off", "Exiting debug mode.")
        if lowered in {"stop", "interrupt", "stop now", "stop speaking"}:
            return ("interrupt", "Stopping the active response.")
        if lowered in {"resume", "resume listening", "resume voice"}:
            return ("resume", "Resuming the voice channels.")
        if lowered in {"go silent", "mute voice", "silent mode"}:
            return ("silent", "Jarvis voice output muted.")
        if lowered in {"start listening", "listen now", "begin listening"}:
            return ("start-listening", "Starting live listening.")
        if lowered in {"stop listening", "pause listening", "disable listening"}:
            return ("stop-listening", "Stopping live listening.")

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
        elif command == "open-operations":
            self.openOperations()
        elif command == "hide-operations":
            self.hideOperations()
        elif command in {"show-workflow", "show-backend", "show-model", "show-memory"}:
            self.openOperations()
        elif command == "debug-on":
            self.enterDebugMode()
        elif command == "debug-off":
            self.exitDebugMode()
        elif command == "interrupt":
            self.interruptResponse()
        elif command == "resume":
            if self._speaker_muted:
                self.toggleSpeakerMuted()
            if self._microphone_muted:
                self.toggleMicrophoneMuted()
            if self._listen_status != "AUTO LISTEN // ON":
                self.setListenEnabled(True)
        elif command == "silent":
            if not self._speaker_muted:
                self.toggleSpeakerMuted()
        elif command == "start-listening":
            self.setListenEnabled(True)
        elif command == "stop-listening":
            self.setListenEnabled(False)
        elif command.startswith("speech-mode:"):
            language_mode = command.split(":", 1)[1]
            set_speech_mode_config(language_mode=language_mode)
            status = speech_mode_status()
            acknowledgement = f"{language_mode.title()} mode selected. {status['detail']}"
            self._refresh_mic_status()
            self._refresh_cockpit_summary()
        else:
            self.windowCommandRequested.emit(command)

        self._set_last_user_transcript(transcript)
        self._set_last_assistant_reply(acknowledgement)
        self._append_section("YOU", transcript)
        self._append_section("JARVIS", acknowledgement)
        self._set_workflow_status("WORKFLOW // LOCAL WINDOW CONTROL")
        self._push_trace("window.control", "ok", command)
        self._set_state("executing")
        envelope = self._compose_response_envelope(
            reply_text=acknowledgement,
            speech_text="" if command in {"mute-speaker", "silent", "interrupt"} else acknowledgement,
            state="executing",
            intent=command,
            agent="jarvis-shell",
            model="local-ui",
            confidence=1.0,
            tool_calls=[{"name": f"ui.{command}", "status": "completed"}],
            approval_required=False,
            risk_level="low",
        )
        self._publish_response_envelope(envelope)
        self._refresh_visual_outputs()
        self._record_interaction(
            source="local_ui_command",
            transcript=transcript,
            envelope=envelope,
            success=True,
            memory_saved=False,
            training_candidate=False,
        )
        if command != "mute-speaker":
            self._set_voice_capture_status("VOICE // SPEAKING")
            self._speak_reply_async(acknowledgement)
        self._set_state(self._fallback_state())

    def _capture_voice_once(self) -> None:
        try:
            result = transcribe_microphone_input(
                duration_s=self._push_to_talk_duration(),
                provider="auto",
                prefer_realtime=False,
                progress_callback=self.voiceCaptureProgress.emit,
            )
            route = route_transcript(result.transcript)
            self.voiceTranscriptReady.emit(route.normalized_task, "push-to-talk")
        except Exception as exc:
            self.voiceCaptureFailed.emit(str(exc))

    def _capture_stream_contract(self, stream_event: object) -> None:
        response = getattr(stream_event, "response", None)
        if response is None:
            return
        self._latest_stream_contract = response

    def _normalize_memory_hit_labels(self, memory_hits: list[object]) -> list[str]:
        labels: list[str] = []
        for item in memory_hits:
            if isinstance(item, dict):
                title = str(item.get("title") or item.get("source") or "memory").strip()
                content = str(item.get("content") or "").strip()
                labels.append(f"{title}: {content}".strip(": "))
            elif item is not None:
                labels.append(str(item))
        return [label for label in labels if label.strip()]

    def _normalize_workflow_trace(self, items: list[dict[str, object]]) -> list[dict[str, str]]:
        if not items:
            return [dict(item) for item in self._workflow_trace[:10]]
        normalized: list[dict[str, str]] = []
        for item in items[:10]:
            normalized.append(
                {
                    "ts": str(item.get("ts") or time.strftime("%H:%M:%S")),
                    "step": str(item.get("step") or item.get("detail") or "workflow"),
                    "status": str(item.get("status") or "ok"),
                    "detail": str(item.get("detail") or item.get("step") or ""),
                }
            )
        return normalized

    def _start_listen_loop(self) -> None:
        if self.listen_thread is not None and self.listen_thread.is_alive():
            return
        self.listen_stop_event.clear()
        set_capture_state(True, provider=resolve_speech_provider(prefer_realtime=True), mode="continuous")
        self._refresh_mic_status()
        self._set_voice_capture_status("VOICE // LIVE LISTEN")
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

    def _stop_listen_loop(self) -> None:
        self.listen_stop_event.set()
        set_capture_state(False, provider=resolve_speech_provider(prefer_realtime=True), mode="continuous")
        self._refresh_mic_status()
        if not self._microphone_muted:
            self._set_voice_capture_status("VOICE // READY")

    def _listen_loop(self) -> None:
        while not self.listen_stop_event.is_set():
            if self._busy or self._microphone_muted:
                time.sleep(0.4)
                continue
            try:
                result = transcribe_microphone_input(
                    duration_s=self._live_listen_duration(),
                    provider="auto",
                    allow_empty=True,
                    prefer_realtime=True,
                    progress_callback=self.voiceCaptureProgress.emit,
                )
            except Exception as exc:
                self.voiceCaptureFailed.emit(str(exc))
                time.sleep(1.0)
                continue
            if self.listen_stop_event.is_set():
                break
            transcript = " ".join(result.transcript.split())
            if not transcript:
                continue
            if self._wake_word_enabled and not live_listen_accepts_transcript(transcript):
                self.voiceCaptureProgress.emit("VOICE // PASSIVE LISTEN // WAITING FOR 'JARVIS'")
                self._push_trace("voice.wake_gate", "ok", transcript[:64])
                continue
            route = route_transcript(transcript)
            self.voiceTranscriptReady.emit(route.normalized_task, "live-listen")

    @Slot(str, str)
    def _handle_voice_transcript(self, transcript: str, source: str) -> None:
        set_capture_state(
            get_listen_state().enabled,
            provider=resolve_speech_provider(prefer_realtime=source == "live-listen"),
            mode="continuous" if get_listen_state().enabled else "push-to-talk",
        )
        self._refresh_mic_status()
        self._set_state("transcribing")
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
            set_capture_state(False, provider=resolve_speech_provider(prefer_realtime=False), mode="push-to-talk")
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
        if "OFFLINE" in self._backend_status:
            return "disconnected"
        if self._microphone_muted or self._speaker_muted:
            return "muted"
        if self._listen_status == "AUTO LISTEN // ON":
            return "listening"
        return "idle"

    def _push_to_talk_duration(self) -> float:
        return 3.0 if self._low_latency_voice else 6.0

    def _live_listen_duration(self) -> float:
        return 1.6 if self._low_latency_voice else 3.0

    def _today_utc(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _extract_utc_day(self, value: object) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        normalized = raw.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).astimezone(timezone.utc).date().isoformat()
        except ValueError:
            return ""

    def _load_json_payloads(self, root: Path) -> list[dict[str, object]]:
        payloads: list[dict[str, object]] = []
        for path in iter_json_like_files(root):
            try:
                payload = read_json_file(path, default={})
            except Exception:
                continue
            if payload:
                payloads.append(payload)
        return payloads

    def _refresh_cockpit_summary(self) -> None:
        today = self._today_utc()
        interaction_root = data_dir() / "interactions" / self._project_id
        learning_root = data_dir() / "learning"
        training_root = data_dir() / "training_candidates"

        interaction_payloads = self._load_json_payloads(interaction_root)
        learning_payloads = self._load_json_payloads(learning_root)
        training_payloads = self._load_json_payloads(training_root)

        today_interactions = [item for item in interaction_payloads if self._extract_utc_day(item.get("timestamp")) == today]
        today_learning = [item for item in learning_payloads if self._extract_utc_day(item.get("timestamp")) == today]
        today_training = [item for item in training_payloads if self._extract_utc_day(item.get("timestamp") or item.get("created_at")) == today]

        success_count = sum(1 for item in today_interactions if bool(item.get("success", False)))
        approval_count = sum(1 for item in today_interactions if bool(item.get("approval_required", False)))
        memory_saved_count = sum(1 for item in today_interactions if bool(item.get("memory_saved", False)))
        tool_call_count = sum(int(item.get("tool_calls_count", 0) or 0) for item in today_interactions)
        intents = sorted({str(item.get("detected_intent", "")).strip() for item in today_interactions if str(item.get("detected_intent", "")).strip()})
        models = sorted({str(item.get("selected_model", "")).strip() for item in today_interactions if str(item.get("selected_model", "")).strip()})
        latest_command = str(today_interactions[-1].get("user_command", "")).strip() if today_interactions else ""
        latest_learning_intent = str(today_learning[-1].get("intent", "")).strip() if today_learning else ""

        speech_cfg = get_speech_mode_config()
        speech_status = speech_mode_status()
        capture_state = get_capture_state()
        memory_control = load_memory_control_state()

        summary = {
            "date": today,
            "backend": self._config.backend,
            "omnira_status": self._omnira_status,
            "active_agent": self._active_agent,
            "active_model": self._active_model,
            "route": self._route_summary,
            "latency": self._latency_summary,
            "workflow": self._workflow_status,
            "model_rationale": dict(self._response_envelope.metadata.get("model_rationale") or {}),
            "voice": {
                "listen_status": self._listen_status,
                "capture_status": self._voice_capture_status,
                "microphone_muted": self._microphone_muted,
                "speaker_muted": self._speaker_muted,
                "low_latency": self._low_latency_voice,
                "language_mode": speech_cfg.language_mode,
                "provider": speech_status.get("active_provider", speech_cfg.provider),
                "culture": speech_status.get("resolved_culture", speech_cfg.culture),
                "capture_mode": capture_state.mode,
                "capture_active": capture_state.active,
            },
            "learning": {
                "interactions_today": len(today_interactions),
                "successful_turns": success_count,
                "learning_records_today": len(today_learning),
                "training_candidates_today": len(today_training),
                "memory_saves_today": memory_saved_count,
                "approval_turns_today": approval_count,
                "tool_calls_today": tool_call_count,
                "latest_command": latest_command,
                "latest_learning_intent": latest_learning_intent,
                "intents": intents[:10],
                "models": models[:8],
            },
            "controls": {
                "compute_mode": memory_control.compute_mode,
                "pinned_model": memory_control.pinned_model,
                "observation_enabled": memory_control.observation_enabled,
                "training_enabled": memory_control.training_enabled,
                "internet_learning_enabled": memory_control.internet_learning_enabled,
                "camera_consent": self._camera_consent,
                "voice_learning_enabled": self._voice_learning_enabled,
                "show_operations_by_default": self._show_operations_by_default,
            },
        }
        self._cockpit_summary_json = json.dumps(summary)
        self.cockpitSummaryJsonChanged.emit()

    def _load_ui_settings(self) -> None:
        defaults = {
            "speaker_muted": False,
            "microphone_muted": False,
            "text_fallback_visible": False,
            "default_ui_mode": DEFAULT_UI_MODE,
            "show_operations_by_default": True,
            "wake_word_enabled": True,
            "launch_mode": "manual",
            "start_minimized": False,
            "owner_name": "",
            "camera_consent": False,
            "voice_learning_enabled": False,
            "low_latency_voice": True,
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
        self._show_operations_by_default = True
        self._wake_word_enabled = bool(merged.get("wake_word_enabled", True))
        default_ui_mode = normalize_ui_mode(merged.get("default_ui_mode", DEFAULT_UI_MODE))
        self._ui_mode = "operations" if self._show_operations_by_default else default_ui_mode
        self._operations_visible = mode_shows_operations(self._ui_mode)
        self._debug_mode_enabled = self._ui_mode == "debug"
        self._launch_mode = str(merged["launch_mode"] or "manual")
        self._start_minimized = bool(merged["start_minimized"])
        self._owner_name = self._normalize_owner_name(str(merged.get("owner_name", "")))
        self._camera_consent = bool(merged.get("camera_consent", False))
        self._voice_learning_enabled = bool(merged.get("voice_learning_enabled", False))
        self._low_latency_voice = bool(merged.get("low_latency_voice", True))
        if any(key not in data for key in defaults):
            self._save_ui_settings()

    def _save_ui_settings(self) -> None:
        payload = {
            "speaker_muted": self._speaker_muted,
            "microphone_muted": self._microphone_muted,
            "text_fallback_visible": self._text_fallback_visible,
            "default_ui_mode": self._ui_mode if self._ui_mode in {"presence", "conversation", "insight"} else DEFAULT_UI_MODE,
            "show_operations_by_default": self._show_operations_by_default,
            "wake_word_enabled": self._wake_word_enabled,
            "launch_mode": self._launch_mode,
            "start_minimized": self._start_minimized,
            "owner_name": self._owner_name,
            "camera_consent": self._camera_consent,
            "voice_learning_enabled": self._voice_learning_enabled,
            "low_latency_voice": self._low_latency_voice,
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
