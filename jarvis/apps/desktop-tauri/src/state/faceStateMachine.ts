import type { JarvisFaceState } from "../types/jarvis";

export type FaceVisualSpec = {
  accent: string;
  glow: string;
  ring: string;
  pulseSpeed: number;
  orbitSpeed: number;
  intensity: number;
  label: string;
  shellScale: number;
  rippleStrength: number;
  sweepStrength: number;
};

const FACE_VISUALS: Record<JarvisFaceState, FaceVisualSpec> = {
  idle: { accent: "#6ae8ff", glow: "#2cc3ff", ring: "#86f7ff", pulseSpeed: 0.8, orbitSpeed: 0.2, intensity: 0.9, label: "Idle", shellScale: 1, rippleStrength: 0.08, sweepStrength: 0.04 },
  listening: { accent: "#79fff2", glow: "#35e2d0", ring: "#8ffff7", pulseSpeed: 1.4, orbitSpeed: 0.5, intensity: 1.1, label: "Listening", shellScale: 1.04, rippleStrength: 0.18, sweepStrength: 0.08 },
  transcribing: { accent: "#7af0ff", glow: "#4f9dff", ring: "#9dc6ff", pulseSpeed: 1.8, orbitSpeed: 0.8, intensity: 1.15, label: "Transcribing", shellScale: 1.05, rippleStrength: 0.24, sweepStrength: 0.1 },
  thinking: { accent: "#7fbcff", glow: "#7584ff", ring: "#b39dff", pulseSpeed: 1.2, orbitSpeed: 1.4, intensity: 1.25, label: "Thinking", shellScale: 1.03, rippleStrength: 0.1, sweepStrength: 0.16 },
  speaking: { accent: "#87f8ff", glow: "#4be3ff", ring: "#d4f3ff", pulseSpeed: 2.1, orbitSpeed: 1.2, intensity: 1.35, label: "Speaking", shellScale: 1.08, rippleStrength: 0.22, sweepStrength: 0.1 },
  executing: { accent: "#9dfcff", glow: "#47b8ff", ring: "#9de2ff", pulseSpeed: 2.6, orbitSpeed: 2.2, intensity: 1.4, label: "Executing", shellScale: 1.09, rippleStrength: 0.12, sweepStrength: 0.18 },
  approval_required: { accent: "#ffe07a", glow: "#ffb34a", ring: "#ffe8a6", pulseSpeed: 0.5, orbitSpeed: 0.15, intensity: 1.45, label: "Approval Required", shellScale: 1.02, rippleStrength: 0.04, sweepStrength: 0.02 },
  scanning: { accent: "#7cf7d4", glow: "#49d8a4", ring: "#b4ffe1", pulseSpeed: 1.6, orbitSpeed: 2.6, intensity: 1.2, label: "Scanning", shellScale: 1.04, rippleStrength: 0.1, sweepStrength: 0.3 },
  memory_recall: { accent: "#c7a7ff", glow: "#8b7bff", ring: "#dfccff", pulseSpeed: 0.9, orbitSpeed: 1.7, intensity: 1.2, label: "Memory Recall", shellScale: 1.06, rippleStrength: 0.16, sweepStrength: 0.12 },
  deployment_running: { accent: "#6ee7ff", glow: "#3f8dff", ring: "#8fd8ff", pulseSpeed: 1.9, orbitSpeed: 2.9, intensity: 1.3, label: "Deployment Running", shellScale: 1.07, rippleStrength: 0.14, sweepStrength: 0.2 },
  alert: { accent: "#ffbf5e", glow: "#ff8b3d", ring: "#ffd698", pulseSpeed: 2.4, orbitSpeed: 1.9, intensity: 1.35, label: "Alert", shellScale: 1.08, rippleStrength: 0.18, sweepStrength: 0.12 },
  danger: { accent: "#ff6b6b", glow: "#ff3131", ring: "#ffabab", pulseSpeed: 3.2, orbitSpeed: 2.8, intensity: 1.55, label: "Danger", shellScale: 1.12, rippleStrength: 0.28, sweepStrength: 0.14 },
  muted: { accent: "#64748b", glow: "#334155", ring: "#94a3b8", pulseSpeed: 0.35, orbitSpeed: 0.08, intensity: 0.55, label: "Muted", shellScale: 0.98, rippleStrength: 0.02, sweepStrength: 0.01 },
  disconnected: { accent: "#718096", glow: "#475569", ring: "#94a3b8", pulseSpeed: 0.25, orbitSpeed: 0.05, intensity: 0.45, label: "Disconnected", shellScale: 0.97, rippleStrength: 0.01, sweepStrength: 0.01 },
  error: { accent: "#ff8094", glow: "#ff3a60", ring: "#ffb0bb", pulseSpeed: 2.8, orbitSpeed: 0.9, intensity: 1.45, label: "Error", shellScale: 1.1, rippleStrength: 0.24, sweepStrength: 0.08 },
};

export function resolveFaceVisual(state: JarvisFaceState): FaceVisualSpec {
  return FACE_VISUALS[state] ?? FACE_VISUALS.idle;
}