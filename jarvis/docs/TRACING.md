# Tracing

Agent Hub emits lightweight JSONL spans to make agent handoffs and API calls observable without adding heavy dependencies.

## Enable

```yaml
tracing:
  enabled: true
  sample_rate: 1.0
```

## Output

`data/traces/<project-id>/<trace-id>.jsonl`

Each line is a JSON object with one of:

- `type: "trace_start"` (metadata)
- `type: "span"` (timed operation)
- `type: "event"` (instant marker)

## Handoff events

When `agent=auto`, routing emits:

```json
{"type":"event","name":"handoff","attributes":{"from":"auto","to":"<agent>","reason":"router.pick"}}
```

## Common spans

- `cli.run`, `web.chat`, `web.chat.stream`, `queue.process`, `plan.run`, `plan.step`
- `router.pick` (selection)
- `agent.run`
- `openai.request`, `openai.stream`
- `memory.load`, `memory.append`
- `run.write`

Tracing never raises on failure; it is best-effort and should not affect agent execution.
