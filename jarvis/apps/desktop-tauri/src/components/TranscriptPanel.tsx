import type { TranscriptEntry } from "../types/jarvis";

type TranscriptPanelProps = {
  entries: TranscriptEntry[];
};

export function TranscriptPanel({ entries }: TranscriptPanelProps) {
  return (
    <section className="panel-surface transcript-panel">
      <div className="panel-heading">
        <span className="eyebrow">Transcript</span>
        <h3>Conversation Channel</h3>
      </div>
      <div className="transcript-feed">
        {entries.map((entry) => (
          <article key={entry.id} className={`transcript-card ${entry.role}`}>
            <span className="transcript-role">{entry.role}</span>
            <p>{entry.message}</p>
            {entry.meta ? <span className="transcript-meta">{entry.meta}</span> : null}
          </article>
        ))}
      </div>
    </section>
  );
}