import type { MemoryStatus as MemoryStatusType } from "../types/jarvis";

type MemoryStatusProps = {
  memoryStatus: MemoryStatusType;
};

export function MemoryStatus({ memoryStatus }: MemoryStatusProps) {
  return (
    <section className="panel-surface status-panel">
      <div className="panel-heading">
        <span className="eyebrow">Memory Controls</span>
        <h3>Privacy and Compute</h3>
      </div>
      <dl className="status-grid">
        <div>
          <dt>Memory</dt>
          <dd>{memoryStatus.memory_enabled ? "enabled" : "disabled"}</dd>
        </div>
        <div>
          <dt>Training</dt>
          <dd>{memoryStatus.training_enabled ? "enabled" : "disabled"}</dd>
        </div>
        <div>
          <dt>Profile learning</dt>
          <dd>{memoryStatus.profile_learning_enabled ? "enabled" : "disabled"}</dd>
        </div>
        <div>
          <dt>Internet learning</dt>
          <dd>{memoryStatus.internet_learning_enabled ? "enabled" : "disabled"}</dd>
        </div>
        <div>
          <dt>Compute mode</dt>
          <dd>{memoryStatus.compute_mode}</dd>
        </div>
        <div>
          <dt>Pinned model</dt>
          <dd>{memoryStatus.pinned_model ?? "none"}</dd>
        </div>
      </dl>
    </section>
  );
}