export type JarvisFaceState =
  | "idle"
  | "listening"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "executing"
  | "approval_required"
  | "scanning"
  | "memory_recall"
  | "deployment_running"
  | "alert"
  | "danger"
  | "muted"
  | "disconnected"
  | "error";

export type ToolEvent = {
  time: string;
  type: string;
  message: string;
};

export type MemoryStatus = {
  memory_enabled: boolean;
  training_enabled: boolean;
  profile_learning_enabled: boolean;
  internet_learning_enabled: boolean;
  compute_mode: string;
  pinned_model: string | null;
};

export type ApprovalPayload = {
  required: boolean;
  risk_level: string;
  reason: string;
  action_summary: string;
  approval_id: string;
  expected_result: string;
  permission_level: string;
};

export type BridgeCommandResponse = {
  conversation_id: string;
  turn_id: string;
  state: JarvisFaceState;
  agent: string;
  model: string;
  provider: string;
  model_rationale: string;
  confidence: number;
  task: string;
  user_message: string;
  assistant_message: string;
  requires_approval: boolean;
  approval: ApprovalPayload;
  tool_events: ToolEvent[];
  memory_status: MemoryStatus;
  error: { message?: string } | null;
  decision_path: string[];
  safety_flags: string[];
};

export type BridgeStateResponse = {
  conversation_id: string;
  shell: {
    active_state: JarvisFaceState;
    active_agent: string;
    active_model: string;
    backend_online: boolean;
    backend_detail: string;
  };
  voice: {
    listen_enabled: boolean;
    listen_mode: string;
    capture_active: boolean;
    capture_provider: string;
    microphone: {
      device: string;
      sample_rate: number;
      chunk_ms: number;
      mode: string;
    };
    speech: {
      language_mode: string;
      active_provider: string;
      detail: string;
    };
  };
  memory_status: MemoryStatus;
  approval_queue: {
    count: number;
  };
  project_path: string;
  policy_profile: string;
  bridge_version: string;
  websocket_url: string;
};

export type TranscriptEntry = {
  id: string;
  role: "system" | "user" | "assistant";
  message: string;
  meta?: string;
};

export type CommandFeedEntry = {
  id: string;
  time: string;
  type: string;
  message: string;
};

export type ApprovalResolution = {
  ok: boolean;
  message: string;
  action?: string;
};

export type StateChangedEvent = {
  type: "state_changed";
  state: JarvisFaceState;
  timestamp: string;
};

export type ToolEventMessage = {
  type: "tool_event";
  event: ToolEvent;
};

export type PartialResponseEvent = {
  type: "partial_response";
  text: string;
  timestamp: string;
};

export type ApprovalRequiredEvent = {
  type: "approval_required";
  approval: ApprovalPayload;
};

export type FinalResponseEvent = {
  type: "final_response";
  envelope: Pick<
    BridgeCommandResponse,
    "conversation_id" | "turn_id" | "state" | "agent" | "model" | "assistant_message" | "requires_approval"
  >;
};

export type VoiceListeningStartedEvent = { type: "voice_listening_started"; timestamp: string };
export type VoiceListeningStoppedEvent = { type: "voice_listening_stopped"; timestamp: string };
export type PartialTranscriptEvent = { type: "partial_transcript"; text: string; timestamp: string };
export type FinalTranscriptEvent = { type: "final_transcript"; text: string; timestamp: string };
export type TtsStartedEvent = { type: "tts_started"; timestamp: string };
export type TtsStoppedEvent = { type: "tts_stopped"; timestamp: string };
export type BargeInDetectedEvent = { type: "barge_in_detected"; timestamp: string };

export type BridgeSocketEvent =
  | StateChangedEvent
  | ToolEventMessage
  | PartialResponseEvent
  | ApprovalRequiredEvent
  | FinalResponseEvent
  | VoiceListeningStartedEvent
  | VoiceListeningStoppedEvent
  | PartialTranscriptEvent
  | FinalTranscriptEvent
  | TtsStartedEvent
  | TtsStoppedEvent
  | BargeInDetectedEvent;