from __future__ import annotations

from pathlib import Path

from .backend_client import build_routing_profile, create_openai_client, resolve_omnira_agent_name
from .config import load_config
from .agents import AgentProfile
from datetime import datetime, timezone
import time

from .memory import RunRecord, project_id, load_memory, write_run, append_memory
from .context import build_repo_context
from .tracing import TraceContext, start_trace, span, event


def _extract_output_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    output = getattr(response, "output", None)
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            content = None
            if isinstance(item, dict):
                content = item.get("content")
            else:
                content = getattr(item, "content", None)
            if not content:
                continue
            for c in content:
                c_type = c.get("type") if isinstance(c, dict) else getattr(c, "type", None)
                if c_type in ("output_text", "text"):
                    c_text = c.get("text") if isinstance(c, dict) else getattr(c, "text", "")
                    if c_text:
                        parts.append(c_text)
        return "\n".join(parts).strip()
    return ""


def _build_input(system_prompt: str, task: str, memory: str, repo_context: str) -> list[dict]:
    full_system = system_prompt.strip()
    if memory.strip():
        full_system += "\n\nProject memory:\n" + memory.strip()
    if repo_context.strip():
        full_system += "\n\nRepository context:\n" + repo_context.strip()

    return [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": full_system}],
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": task.strip()}],
        },
    ]


def run_task(
    task: str,
    agent: AgentProfile,
    project_path: str,
    trace: TraceContext | None = None,
    source: str | None = None,
    dynamic_routing: bool = False,
) -> str:
    cfg = load_config()
    routing_profile = build_routing_profile(agent.name, agent.model, cfg, dynamic_routing=dynamic_routing)
    model = routing_profile.model_name
    preferred_agent = resolve_omnira_agent_name(agent.name, dynamic_routing=dynamic_routing) if cfg.backend == "omnira" else None

    # Lazy init so non-API commands (e.g., list-agents) don't require a key.
    client = create_openai_client(cfg)

    pid = project_id(project_path)
    trace_ctx = trace or start_trace(project_path, agent=agent.name, source=source or "run_task")

    with span(
        trace_ctx,
        "agent.run",
        {"agent": agent.name, "model": model or "dynamic", "backend": cfg.backend, "project_id": pid},
    ):
        with span(trace_ctx, "memory.load", {"project_id": pid}):
            memory = load_memory(pid)

        with span(trace_ctx, "repo.context", {"project_id": pid}):
            repo_context = build_repo_context(project_path)

        last_err: Exception | None = None
        response = None
        for attempt in range(1, cfg.retry_max_attempts + 1):
            try:
                with span(
                    trace_ctx,
                    "openai.request",
                    {"attempt": attempt, "model": model or "dynamic", "timeout_s": cfg.request_timeout_s},
                ):
                    request_input = _build_input(agent.system_prompt, task, memory, repo_context)
                    if cfg.backend == "omnira":
                        response = client.responses.create(
                            model=model,
                            input=request_input,
                            max_output_tokens=routing_profile.max_output_tokens,
                            reasoning={"effort": routing_profile.reasoning_effort},
                            timeout=cfg.request_timeout_s,
                            preferred_agent=preferred_agent,
                        )
                    else:
                        response = client.responses.create(
                            model=model,
                            input=request_input,
                            max_output_tokens=routing_profile.max_output_tokens,
                            reasoning={"effort": routing_profile.reasoning_effort},
                            timeout=cfg.request_timeout_s,
                        )
                last_err = None
                break
            except Exception as exc:  # best-effort retry
                last_err = exc
                event(trace_ctx, "openai.retry", {"attempt": attempt, "error": str(exc)})
                msg = str(exc)
                if "model_not_found" in msg or "does not exist" in msg:
                    backend_hint = (
                        "If you want to use OMNIRA, set backend: omnira and point base_url at its OpenAI-compatible endpoint. "
                        if cfg.backend == "omnira"
                        else ""
                    )
                    raise RuntimeError(
                        "Model not found for current backend. "
                        "If you want gpt-oss-20b, set backend: local and base_url in config.yaml. "
                        f"{backend_hint}"
                        "Otherwise set model to an OpenAI model (e.g., gpt-5.2-codex) or let the OMNIRA backend map Jarvis agents automatically."
                    ) from exc
                if attempt >= cfg.retry_max_attempts:
                    break
                time.sleep(cfg.retry_backoff_s * attempt)

        if response is None:
            raise last_err  # type: ignore[misc]

        output_text = _extract_output_text(response)
        resolved_model = getattr(response, "model", None) or model or "omnira-dynamic"

        usage = getattr(response, "usage", None)
        input_tokens = None
        output_tokens = None
        total_tokens = None
        if usage is not None:
            if isinstance(usage, dict):
                input_tokens = usage.get("input_tokens")
                output_tokens = usage.get("output_tokens")
                total_tokens = usage.get("total_tokens")
            else:
                input_tokens = getattr(usage, "input_tokens", None)
                output_tokens = getattr(usage, "output_tokens", None)
                total_tokens = getattr(usage, "total_tokens", None)

        # Persist a lightweight summary for quick recall without extra model calls.
        created_at = response.created_at
        try:
            if isinstance(created_at, (int, float)):
                ts = datetime.fromtimestamp(created_at, tz=timezone.utc).isoformat()
            else:
                ts = str(created_at)
        except Exception:
            ts = "unknown"

        summary = "\n".join(
            [
                f"### Run Summary ({ts})",
                f"- Agent: {agent.name}",
                f"- Task: {task}",
                f"- Output (truncated): {output_text[:400].strip()}",
            ]
        )
        with span(trace_ctx, "memory.append", {"project_id": pid}):
            append_memory(pid, summary)

        with span(trace_ctx, "run.write", {"project_id": pid}):
            run_path = write_run(
                pid,
                RunRecord(
                    timestamp=response.created_at,
                    project_path=project_path,
                    agent=agent.name,
                    task=task,
                    response=output_text,
                    model=resolved_model,
                    trace_id=trace_ctx.trace_id if trace_ctx else None,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                ),
            )
        event(trace_ctx, "run.complete", {"run_file": str(run_path)})

        return output_text
