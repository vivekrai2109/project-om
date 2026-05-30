# Memory Strategy

OMNIRA Memory is divided into three core domains.

- Conversation memory stores recent interactions and decision context.
- Personal memory stores user preferences, recurring patterns, and long-lived facts.
- Project memory stores repository, architecture, and task-specific knowledge.

The MVP uses a JSON-backed store to keep implementation simple. The next step is PostgreSQL persistence with structured metadata, retention policies, and pgvector-powered semantic search.
