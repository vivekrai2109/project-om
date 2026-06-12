import type { JarvisUiState } from "../state/jarvisState";

type ModelStatusProps = {
  uiState: JarvisUiState;
};

export function ModelStatus({ uiState }: ModelStatusProps) {
  return (
    <section className="panel-surface status-panel">
      <div className="panel-heading">
        <span className="eyebrow">Model Path</span>
        <h3>Agent and Routing</h3>
      </div>
      <dl className="status-grid">
        <div>
          <dt>State</dt>
          <dd>{uiState.activeState}</dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{uiState.activeAgent || "commander"}</dd>
        </div>
        <div>
          <dt>Model</dt>
          <dd>{uiState.activeModel || "dynamic"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{uiState.confidence !== null ? uiState.confidence.toFixed(2) : "n/a"}</dd>
        </div>
      </dl>
      <div className="status-detail-block">
        <label>Model rationale</label>
        <p>{uiState.modelRationale || "The bridge will surface model rationale when the commander provides it."}</p>
      </div>
    </section>
  );
}