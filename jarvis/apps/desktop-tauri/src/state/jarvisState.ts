import type {
  ApprovalPayload,
  BridgeCommandResponse,
  BridgeSocketEvent,
  BridgeStateResponse,
  CommandFeedEntry,
  JarvisFaceState,
  MemoryStatus,
  TranscriptEntry,
} from "../types/jarvis";

export type JarvisUiState = {
  conversationId: string;
  activeState: JarvisFaceState;
  activeAgent: string;
  activeModel: string;
  backendOnline: boolean;
  backendDetail: string;
  modelRationale: string;
  confidence: number | null;
  transcript: TranscriptEntry[];
  commandFeed: CommandFeedEntry[];
  memoryStatus: MemoryStatus;
  currentApproval: ApprovalPayload | null;
  requestPending: boolean;
  errorMessage: string;
  voiceStatus: string;
  websocketConnected: boolean;
  lastEventTime: string;
  bridgeVersion: string;
  websocketUrl: string;
  partialAssistantMessage: string;
};

const EMPTY_MEMORY_STATUS: MemoryStatus = {
  memory_enabled: true,
  training_enabled: true,
  profile_learning_enabled: true,
  internet_learning_enabled: false,
  compute_mode: "balanced",
  pinned_model: null,
};

function feedEntry(type: string, message: string, time = new Date().toISOString()): CommandFeedEntry {
  return {
    id: `${time}-${type}-${message}`,
    time,
    type,
    message,
  };
}

function transcriptEntry(role: TranscriptEntry["role"], message: string, meta?: string): TranscriptEntry {
  return {
    id: `${role}-${Date.now()}-${message.slice(0, 12)}`,
    role,
    message,
    meta,
  };
}

export function createInitialJarvisUiState(): JarvisUiState {
  return {
    conversationId: "",
    activeState: "idle",
    activeAgent: "commander",
    activeModel: "",
    backendOnline: false,
    backendDetail: "Waiting for Python bridge.",
    modelRationale: "",
    confidence: null,
    transcript: [transcriptEntry("system", "JARVIS cinematic shell is waiting for the Python bridge.")],
    commandFeed: [feedEntry("info", "Cockpit initialized.")],
    memoryStatus: EMPTY_MEMORY_STATUS,
    currentApproval: null,
    requestPending: false,
    errorMessage: "",
    voiceStatus: "Voice bridge offline",
    websocketConnected: false,
    lastEventTime: "",
    bridgeVersion: "v0.2",
    websocketUrl: "",
    partialAssistantMessage: "",
  };
}

export function hydrateBridgeState(current: JarvisUiState, state: BridgeStateResponse): JarvisUiState {
  return {
    ...current,
    conversationId: state.conversation_id,
    activeState: state.shell.active_state,
    activeAgent: state.shell.active_agent,
    activeModel: state.shell.active_model,
    backendOnline: state.shell.backend_online,
    backendDetail: state.shell.backend_detail,
    memoryStatus: state.memory_status,
    voiceStatus: `${state.voice.speech.language_mode} via ${state.voice.capture_provider}`,
    bridgeVersion: state.bridge_version,
    websocketUrl: state.websocket_url,
    commandFeed: [
      feedEntry(state.shell.backend_online ? "ok" : "warning", state.shell.backend_detail),
      ...current.commandFeed,
    ].slice(0, 24),
  };
}

export function applyPendingCommand(current: JarvisUiState, message: string): JarvisUiState {
  return {
    ...current,
    activeState: "thinking",
    requestPending: true,
    errorMessage: "",
    transcript: [...current.transcript, transcriptEntry("user", message)],
    commandFeed: [feedEntry("info", `Queued command: ${message}`), ...current.commandFeed].slice(0, 24),
  };
}

export function applyBridgeResponse(current: JarvisUiState, response: BridgeCommandResponse): JarvisUiState {
  const assistantMeta = [response.agent, response.model].filter(Boolean).join(" // ");
  const responseEntries = response.tool_events.map((event) => feedEntry(event.type, event.message, event.time));
  return {
    ...current,
    conversationId: response.conversation_id,
    activeState: response.state,
    activeAgent: response.agent || current.activeAgent,
    activeModel: response.model || current.activeModel,
    modelRationale: response.model_rationale,
    confidence: Number.isFinite(response.confidence) ? response.confidence : null,
    transcript: [...current.transcript, transcriptEntry("assistant", response.assistant_message, assistantMeta)],
    commandFeed: [...responseEntries, ...current.commandFeed].slice(0, 32),
    memoryStatus: response.memory_status,
    currentApproval: response.requires_approval ? response.approval : null,
    requestPending: false,
    errorMessage: response.error?.message ?? "",
    partialAssistantMessage: "",
  };
}

export function applyApprovalResolution(
  current: JarvisUiState,
  action: "approve" | "reject",
  message: string,
): JarvisUiState {
  return {
    ...current,
    currentApproval: null,
    activeState: action === "approve" ? "executing" : "idle",
    commandFeed: [feedEntry(action === "approve" ? "ok" : "warning", message), ...current.commandFeed].slice(0, 32),
  };
}

export function applySocketConnected(current: JarvisUiState, connected: boolean): JarvisUiState {
  return {
    ...current,
    websocketConnected: connected,
    commandFeed: connected
      ? [feedEntry("ok", "Bridge event stream connected."), ...current.commandFeed].slice(0, 32)
      : [feedEntry("warning", "Bridge event stream disconnected."), ...current.commandFeed].slice(0, 32),
  };
}

export function applyBridgeEvent(current: JarvisUiState, event: BridgeSocketEvent): JarvisUiState {
  switch (event.type) {
    case "state_changed":
      return {
        ...current,
        activeState: event.state,
        lastEventTime: event.timestamp,
      };
    case "tool_event":
      return {
        ...current,
        lastEventTime: event.event.time,
        commandFeed: [feedEntry(event.event.type, event.event.message, event.event.time), ...current.commandFeed].slice(0, 32),
      };
    case "partial_response":
      return {
        ...current,
        lastEventTime: event.timestamp,
        partialAssistantMessage: event.text,
      };
    case "approval_required":
      return {
        ...current,
        activeState: "approval_required",
        currentApproval: event.approval,
      };
    case "final_response":
      return {
        ...current,
        conversationId: event.envelope.conversation_id || current.conversationId,
        activeState: event.envelope.state,
        activeAgent: event.envelope.agent || current.activeAgent,
        activeModel: event.envelope.model || current.activeModel,
        transcript: [
          ...current.transcript,
          transcriptEntry(
            "assistant",
            event.envelope.assistant_message,
            [event.envelope.agent, event.envelope.model].filter(Boolean).join(" // "),
          ),
        ],
        requestPending: false,
        partialAssistantMessage: "",
      };
    case "voice_listening_started":
      return { ...current, voiceStatus: "Listening", lastEventTime: event.timestamp };
    case "voice_listening_stopped":
      return { ...current, voiceStatus: "Voice idle", lastEventTime: event.timestamp };
    case "partial_transcript":
      return { ...current, voiceStatus: `Partial transcript: ${event.text}`, lastEventTime: event.timestamp };
    case "final_transcript":
      return { ...current, voiceStatus: `Final transcript: ${event.text}`, lastEventTime: event.timestamp };
    case "tts_started":
      return { ...current, voiceStatus: "TTS speaking", lastEventTime: event.timestamp };
    case "tts_stopped":
      return { ...current, voiceStatus: "TTS stopped", lastEventTime: event.timestamp };
    case "barge_in_detected":
      return {
        ...current,
        voiceStatus: "Barge-in detected",
        lastEventTime: event.timestamp,
        commandFeed: [feedEntry("warning", "Barge-in detected", event.timestamp), ...current.commandFeed].slice(0, 32),
      };
    default:
      return current;
  }
}