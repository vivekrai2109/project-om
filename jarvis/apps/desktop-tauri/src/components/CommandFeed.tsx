import type { CommandFeedEntry } from "../types/jarvis";

type CommandFeedProps = {
  entries: CommandFeedEntry[];
};

export function CommandFeed({ entries }: CommandFeedProps) {
  return (
    <section className="panel-surface command-feed-panel">
      <div className="panel-heading">
        <span className="eyebrow">Tool Feed</span>
        <h3>Runtime Events</h3>
      </div>
      <div className="command-feed-list">
        {entries.map((entry) => (
          <article key={entry.id} className={`command-feed-entry ${entry.type}`}>
            <span className="feed-time">{new Date(entry.time).toLocaleTimeString()}</span>
            <p>{entry.message}</p>
          </article>
        ))}
      </div>
    </section>
  );
}