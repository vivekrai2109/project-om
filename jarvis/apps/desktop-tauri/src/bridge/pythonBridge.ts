import type { ApprovalResolution, BridgeCommandResponse, BridgeSocketEvent, BridgeStateResponse } from "../types/jarvis";

const env = (globalThis as { __JARVIS_ENV__?: Record<string, string | undefined> }).__JARVIS_ENV__ ?? {};

const BRIDGE_BASE_URL = env.VITE_JARVIS_BRIDGE_URL ?? "http://127.0.0.1:8010";
const BRIDGE_WS_URL =
  env.VITE_JARVIS_WS_URL ??
  `${BRIDGE_BASE_URL.startsWith("https") ? "wss" : "ws"}://${new URL(BRIDGE_BASE_URL).host}/api/v1/events`;

async function readJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Bridge request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

export function loadBridgeState(): Promise<BridgeStateResponse> {
  return readJson<BridgeStateResponse>(`${BRIDGE_BASE_URL}/api/v1/state`, { cache: "no-store" });
}

export function sendJarvisCommand(message: string, conversationId: string): Promise<BridgeCommandResponse> {
  return readJson<BridgeCommandResponse>(`${BRIDGE_BASE_URL}/api/v1/command`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
}

export function approveApproval(approvalId: string, note = ""): Promise<ApprovalResolution> {
  return readJson<ApprovalResolution>(`${BRIDGE_BASE_URL}/api/v1/approvals/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approval_id: approvalId, note }),
  });
}

export function rejectApproval(approvalId: string, note = ""): Promise<ApprovalResolution> {
  return readJson<ApprovalResolution>(`${BRIDGE_BASE_URL}/api/v1/approvals/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approval_id: approvalId, note }),
  });
}

type BridgeSocketOptions = {
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (message: string) => void;
  onEvent: (event: BridgeSocketEvent) => void;
};

export function connectBridgeEvents(options: BridgeSocketOptions): () => void {
  let socket: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  let disposed = false;

  const scheduleReconnect = () => {
    if (disposed || reconnectTimer !== null) {
      return;
    }
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 1500);
  };

  const connect = () => {
    if (disposed) {
      return;
    }
    try {
      socket = new WebSocket(BRIDGE_WS_URL);
    } catch (error) {
      options.onError?.(error instanceof Error ? error.message : String(error));
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      options.onOpen?.();
    };

    socket.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data) as BridgeSocketEvent;
        options.onEvent(payload);
      } catch (error) {
        options.onError?.(error instanceof Error ? error.message : String(error));
      }
    };

    socket.onerror = () => {
      options.onError?.("Bridge WebSocket error");
    };

    socket.onclose = () => {
      options.onClose?.();
      scheduleReconnect();
    };
  };

  connect();

  return () => {
    disposed = true;
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
    }
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
  };
}