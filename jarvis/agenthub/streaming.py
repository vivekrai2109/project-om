from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Callable, Iterable

from .agents import AgentProfile
from .backend_client import build_routing_profile, create_openai_client, resolve_omnira_agent_name
from .config import load_config
from .context import build_repo_context, should_include_repo_context
from .memory import RunRecord, project_id, load_memory, write_run, append_memory
from .orchestrator import _build_input
from .tracing import TraceContext, start_trace, span, event


def stream_task(
    task: str,
    agent: AgentProfile,
    project_path: str,
    trace: TraceContext | None = None,
    source: str | None = None,
    dynamic_routing: bool = False,
    stream_event_callback: Callable[[object], None] | None = None,
) -> Iterable[str]:
    started_at = time.time()
    cfg = load_config()
    routing_profile = build_routing_profile(agent.name, agent.model, cfg, dynamic_routing=dynamic_routing)
    model = routing_profile.model_name
    preferred_agent = resolve_omnira_agent_name(agent.name, dynamic_routing=dynamic_routing) if cfg.backend == "omnira" else None
    client = create_openai_client(cfg)

    pid = project_id(project_path)
    trace_ctx = trace or start_trace(project_path, agent=agent.name, source=source or "stream_task")

    with span(trace_ctx, "memory.load", {"project_id": pid}):
        memory = load_memory(pid)
    repo_context = ""
    if should_include_repo_context(task):
        with span(trace_ctx, "repo.context", {"project_id": pid}):
            repo_context = build_repo_context(project_path)

    with span(trace_ctx, "openai.stream", {"model": model or "dynamic", "timeout_s": cfg.request_timeout_s}):
        request_input = _build_input(agent.system_prompt, task, memory, repo_context)
        if cfg.backend == "omnira":
            stream = client.responses.create(
                model=model,
                input=request_input,
                max_output_tokens=routing_profile.max_output_tokens,
                reasoning={"effort": routing_profile.reasoning_effort},
                timeout=cfg.request_timeout_s,
                stream=True,
                preferred_agent=preferred_agent,
            )
        else:
            stream = client.responses.create(
                model=model,
                input=request_input,
                max_output_tokens=routing_profile.max_output_tokens,
                reasoning={"effort": routing_profile.reasoning_effort},
                timeout=cfg.request_timeout_s,
                stream=True,
            )

    chunks: list[str] = []
    first_token_ms: int | None = None
    for stream_event in stream:
        if stream_event_callback is not None:
            try:
                stream_event_callback(stream_event)
            except Exception:
                pass
        delta = None
        if isinstance(stream_event, dict):
            delta = stream_event.get("delta") or stream_event.get("text")
        else:
            delta = getattr(stream_event, "delta", None) or getattr(stream_event, "text", None)
        if delta:
            if first_token_ms is None:
                first_token_ms = int((time.time() - started_at) * 1000)
                event(trace_ctx, "stream.first_token", {"latency_ms": first_token_ms, "model": model or "dynamic"})
            chunks.append(str(delta))
            yield str(delta)

    output_text = "".join(chunks).strip()
    total_ms = int((time.time() - started_at) * 1000)
    event(
        trace_ctx,
        "stream.complete",
        {
            "chars": len(output_text),
            "first_token_ms": first_token_ms,
            "total_ms": total_ms,
            "model": model or "dynamic",
        },
    )

    # Persist run + memory
    created_at = datetime.now(timezone.utc).timestamp()
    with span(trace_ctx, "run.write", {"project_id": pid}):
        run_path = write_run(
            pid,
            RunRecord(
                timestamp=created_at,
                project_path=project_path,
                agent=agent.name,
                task=task,
                response=output_text,
                    model=getattr(stream, "model", None) or model or "omnira-dynamic",
                trace_id=trace_ctx.trace_id if trace_ctx else None,
            ),
        )
    event(trace_ctx, "run.complete", {"run_file": str(run_path)})

    if output_text:
        summary = "\n".join(
            [
                f"### Run Summary ({datetime.now(timezone.utc).isoformat()})",
                f"- Agent: {agent.name}",
                f"- Task: {task}",
                f"- Output (truncated): {output_text[:400].strip()}",
            ]
        )
        with span(trace_ctx, "memory.append", {"project_id": pid}):
            append_memory(pid, summary)
