import { ApprovalPanel } from "./ApprovalPanel";
import { CommandFeed } from "./CommandFeed";
import { ControlBar } from "./ControlBar";
import { DiagnosticsStrip } from "./DiagnosticsStrip";
import { JarvisOrb } from "./JarvisOrb";
import type { JarvisUiState } from "../state/jarvisState";
import { MemoryStatus } from "./MemoryStatus";
import { ModelStatus } from "./ModelStatus";
import { TranscriptPanel } from "./TranscriptPanel";

type JarvisCockpitProps = {
  uiState: JarvisUiState;
  isPending: boolean;
  onSendCommand: (message: string) => void;
  onApprove: (approvalId: string) => void;
  onReject: (approvalId: string) => void;
};

export function JarvisCockpit({ uiState, isPending, onSendCommand, onApprove, onReject }: JarvisCockpitProps) {
  return (
    <main className="cockpit-shell">
      <header className="cockpit-header panel-surface">
        <div>
          <p className="eyebrow">JARVIS Cinematic Shell v0.1</p>
          <h1>OMNIRA brain. JARVIS commander shell.</h1>
          <p className="header-copy">
            Production-bound Tauri cockpit around the permanent Python commander and approval-safe local runtime.
          </p>
        </div>
        <div className="status-pill-row">
          <span className={`status-pill ${uiState.backendOnline ? "ok" : "warning"}`}>
            {uiState.backendOnline ? "Bridge Online" : "Bridge Waiting"}
          </span>
          <span className="status-pill">State: {uiState.activeState}</span>
          <span className="status-pill">Voice: {uiState.voiceStatus}</span>
        </div>
      </header>

      <DiagnosticsStrip uiState={uiState} />

      <section className="cockpit-grid">
        <aside className="panel-column left-column">
          <ModelStatus uiState={uiState} />
          <MemoryStatus memoryStatus={uiState.memoryStatus} />
        </aside>

        <section className="center-column">
          <section className="panel-surface orb-panel">
            <JarvisOrb state={uiState.activeState} />
            <div className="orb-caption">
              <span className="eyebrow">Assistant Core</span>
              <h2>{uiState.activeState.replace(/_/g, " ")}</h2>
              <p>{uiState.backendDetail}</p>
              {uiState.partialAssistantMessage ? <p className="partial-response">{uiState.partialAssistantMessage}</p> : null}
            </div>
          </section>
          <ControlBar isPending={isPending} onSendCommand={onSendCommand} />
          {uiState.currentApproval ? (
            <ApprovalPanel approval={uiState.currentApproval} onApprove={onApprove} onReject={onReject} />
          ) : null}
        </section>

        <aside className="panel-column right-column">
          <TranscriptPanel entries={uiState.transcript} />
          <CommandFeed entries={uiState.commandFeed} />
        </aside>
      </section>
    </main>
  );
}