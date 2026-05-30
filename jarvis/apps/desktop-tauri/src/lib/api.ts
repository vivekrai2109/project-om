export type JarvisState = {
  listen: { enabled: boolean; mode: string };
  microphone: { device: string; sample_rate: number; chunk_ms: number; mode: string };
  capture: { active: boolean; provider: string; mode: string };
  sessions: Array<{ id: string; title: string; created_at: string; turn_count: number }>;
};

export type ChatResponse = {
  agent: string;
  response: string;
  intent?: string;
  action?: string;
};

const API_BASE_URL = import.meta.env.VITE_JARVIS_API_URL ?? "http://127.0.0.1:8010";

export async function loadJarvisState(): Promise<JarvisState> {
  const response = await fetch(`${API_BASE_URL}/jarvis/state`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`State request failed with status ${response.status}`);
  }
  return (await response.json()) as JarvisState;
}

export async function sendJarvisMessage(message: string, project?: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, project }),
  });
  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }
  return (await response.json()) as ChatResponse;
}