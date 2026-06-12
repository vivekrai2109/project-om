import type { JarvisUiState } from "../state/jarvisState";

type DiagnosticsStripProps = {
  uiState: JarvisUiState;
};

export function DiagnosticsStrip({ uiState }: DiagnosticsStripProps) {
  return (
    <section className="panel-surface diagnostics-strip">
      <div className="diagnostics-chip"><span>HTTP</span><strong>{uiState.backendOnline ? "online" : "offline"}</strong></div>
      <div className="diagnostics-chip"><span>WS</span><strong>{uiState.websocketConnected ? "connected" : "disconnected"}</strong></div>
      <div className="diagnostics-chip"><span>STATE</span><strong>{uiState.activeState}</strong></div>
      <div className="diagnostics-chip"><span>AGENT</span><strong>{uiState.activeAgent || "commander"}</strong></div>
      <div className="diagnostics-chip"><span>MODEL</span><strong>{uiState.activeModel || "dynamic"}</strong></div>
      <div className="diagnostics-chip"><span>LAST EVENT</span><strong>{uiState.lastEventTime || "n/a"}</strong></div>
      <div className="diagnostics-chip"><span>BUILD</span><strong>{uiState.bridgeVersion}</strong></div>
    </section>
  );
}