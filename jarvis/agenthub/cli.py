from __future__ import annotations

from datetime import datetime, timezone
import httpx
import os
from pathlib import Path
import subprocess
import sys
import time
import typer

from .agents import AgentProfile, list_agents, get_agent
from .router import pick_agent
from .orchestrator import run_task
from .evals import run_golden_evals
from .tools import list_tools
from .workflows import create_plan, run_plan
from .queue import enqueue, claim_next, process_item, queue_counts
from .backend import check_backend
from .backend_client import build_routing_profile
from .dataset import export_dataset
from .repo_health import scan_repo
from .policies import (
    list_profiles,
    get_profile,
    evaluate_tool_access,
    evaluate_path_access,
    evaluate_app_access,
    evaluate_command_access,
    recording_requires_consent,
)
from .audit import append_audit_event, list_audit_events
from .speech import (
    list_speech_providers,
    list_windows_recognizers,
    transcribe_text_input,
    transcribe_file_input,
    transcribe_microphone_input,
    get_microphone_config,
    set_microphone_config,
    get_capture_state,
    set_capture_state,
    get_speech_mode_config,
    resolve_speech_provider,
    set_speech_mode_config,
    speech_mode_status,
    list_input_devices,
    record_microphone_clip,
)
from .interview import (
    create_session,
    add_turn,
    list_sessions,
    session_summary,
    load_session,
    coaching_summary,
    coaching_drills,
)
from .voice import route_transcript, get_listen_state, set_listen_state
from .propose import propose_fix
from .apply_patch_cmd import apply_proposal
from .auto_apply import auto_apply_docs_only
from .approvals import record_approval
from .maintenance import schedule_repo_health, schedule_maintenance
from .tracing import start_trace, span, record_handoff
from .config import load_config
from .contracts import OwnerCommand
from .commander import JarvisCommander
from .memory import project_id
from .memory_control import load_memory_control_state
from .secure_storage import iter_json_like_files, read_json_file, storage_encryption_status
from .streaming import stream_task
from .approval_queue import list_pending_approvals
from .runtime import JarvisRuntime
from .runtime_actions import maybe_execute_runtime_action, approve_runtime_action, reject_runtime_action
from .assistant_core import handle_assistant_core, should_use_fast_assistant_route

app = typer.Typer(no_args_is_help=True)


SHELL_HELP_TEXT = """Jarvis shell commands:
/help                 Show this help
/exit                 Exit the Jarvis shell
/quit                 Exit the Jarvis shell
/status               Show Jarvis operating status
/today                Show today's learning and activity progress
/progress             Show today's learning and activity progress
/omnira               Show OMNIRA provider, learning, and training status
/autonomy             Show Jarvis autonomy and supervision status
/voice                Show voice, listen, and capture status
/listen on            Enable terminal listen state
/listen off           Disable terminal listen state
/approvals            List pending approval items
/approve <id> [note]  Approve a queued runtime action
/reject <id> [note]   Reject a queued runtime action
/clear                Print spacing to visually clear the shell

Everything else is sent to Jarvis as a normal assistant turn.
Examples:
- privacy status
- learning readiness
- how are you operating
- what did you learn today
- start omnira
- model status
- pin model to omnira-reasoning-qwen-7b-v0.1
- update the roadmap and tell me what changed
"""


def _omnira_dynamic_profile() -> AgentProfile:
    return AgentProfile(
        name="assistant",
        description="Neutral assistant prompt for OMNIRA dynamic routing.",
        system_prompt=(
            "You are Jarvis, a concise and helpful personal assistant. "
            "Respond naturally to general conversation. "
            "When the user asks for technical or project work, provide the task clearly so the backend can route it to the right specialist."
        ),
    )


def _omnira_fast_profile() -> AgentProfile:
    return AgentProfile(
        name="assistant-lite",
        description="Fast assistant prompt for lightweight OMNIRA turns.",
        system_prompt=(
            "You are Jarvis, a fast and concise personal assistant. "
            "Answer short conversational prompts directly. "
            "Do not expand into long explanations unless the user explicitly asks for depth."
        ),
        model="omnira-lite-qwen-3b-v0.1",
    )

def _ensure_backend():
    ok, msg = check_backend()
    if not ok:
        typer.echo(f"Backend check failed: {msg}")
        raise typer.Exit(code=1)


def _format_pending_approvals() -> str:
    items = list_pending_approvals()
    if not items:
        return "No pending approvals."
    lines = ["Pending approvals:"]
    for item in items:
        lines.append(f"- {item.id} | {item.risk} | {item.source} | {item.task}")
    return "\n".join(lines)


def _format_shell_response(response, *, show_meta: bool = False) -> str:
    reply_text = str(getattr(response, "reply_text", "") or getattr(response, "speech_text", "") or "No response.").strip()
    lines = [f"jarvis> {reply_text}"]
    approval_request = dict(getattr(response, "metadata", {}).get("approval_request") or {})
    approval_id = str(approval_request.get("approval_id") or "").strip()
    if getattr(response, "approval_required", False):
        if approval_id:
            lines.append(f"[approval] {approval_id} is waiting. Use /approvals, /approve {approval_id}, or /reject {approval_id}.")
        else:
            lines.append("[approval] This action is waiting in the approval queue. Use /approvals to inspect it.")
    error = getattr(response, "error", None) or {}
    if error.get("message"):
        lines.append(f"[error] {error['message']}")
    if show_meta:
        lines.append(
            "[meta] "
            f"intent={getattr(response, 'intent', '')} "
            f"agent={getattr(response, 'agent', '')} "
            f"model={getattr(response, 'model', '')} "
            f"state={getattr(response, 'state', '')} "
            f"risk={getattr(response, 'risk_level', '')}"
        )
    return "\n".join(lines)


def _today_utc() -> datetime:
    return datetime.now(timezone.utc)


def _extract_utc_day(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return ""


def _load_json_payloads(paths: list[Path]) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for path in paths:
        try:
            payloads.append(read_json_file(path, default={}))
        except Exception:
            continue
    return payloads


def _format_operating_status(project_path: str) -> str:
    cfg = load_config()
    backend_ok, backend_message = check_backend()
    runtime = JarvisRuntime(project_path=project_path)
    runtime_status = runtime.refresh_status(active_agent="omnira_bridge")
    memory_control = load_memory_control_state()
    routing_profile = build_routing_profile("assistant", None, cfg, dynamic_routing=cfg.backend == "omnira", compute_mode=memory_control.compute_mode)
    encrypted, encryption_label = storage_encryption_status()
    own_model_mode = "yes" if cfg.backend == "omnira" else "partial"
    provider_name, provider_detail = _detect_backend_provider(cfg)
    lines = [
        "Jarvis operating status:",
        f"- Backend: {cfg.backend}.",
        f"- Own model path active: {own_model_mode}.",
        f"- Backend health: {'online' if backend_ok else 'offline'}.",
        f"- Backend detail: {backend_message}",
        f"- Model provider: {provider_name}.",
        f"- Configured endpoint: {cfg.base_url}",
        f"- Default configured model: {cfg.model}",
        f"- Active compute mode: {memory_control.compute_mode}",
        f"- Pinned model: {memory_control.pinned_model or 'not set'}",
        f"- Current routing lane: {routing_profile.model_name or 'dynamic via OMNIRA router'}",
        f"- Reasoning effort: {routing_profile.reasoning_effort}",
        f"- Max output tokens: {routing_profile.max_output_tokens}",
        f"- Runtime control mode: {runtime_status.control_mode}",
        f"- OMNIRA runtime status: {'online' if runtime_status.omnira_online else 'offline'}",
        f"- Observation capture: {'on' if memory_control.observation_enabled else 'off'}",
        f"- Training capture: {'on' if memory_control.training_enabled else 'off'}",
        f"- Internet learning: {'on' if memory_control.internet_learning_enabled else 'off'}",
        f"- Encryption at rest: {'on' if encrypted else 'off'} ({encryption_label})",
    ]
    if provider_detail:
        lines.append(f"- Provider detail: {provider_detail}")
    return "\n".join(lines)


def _detect_backend_provider(cfg) -> tuple[str, str]:
    if cfg.backend != "omnira" or not cfg.base_url:
        return cfg.backend, ""
    try:
        response = httpx.get(f"{cfg.base_url.rstrip('/')}/models", timeout=5)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list) and payload:
            provider = str(payload[0].get("provider") or "unknown").strip() or "unknown"
            if provider == "mock":
                return provider, "OMNIRA API is serving placeholder model responses. Enable a real provider such as Ollama to get live model output."
            return provider, "OMNIRA API is backed by a live model provider."
    except Exception as exc:
        return "unknown", f"provider inspection failed: {exc}"
    return "unknown", ""


def _format_daily_progress(project_path: str) -> str:
    today = _today_utc().date().isoformat()
    pid = project_id(project_path)
    interaction_payloads = _load_json_payloads(iter_json_like_files(Path(project_path) / "data" / "interactions" / pid))
    learning_payloads = _load_json_payloads(iter_json_like_files(Path(project_path) / "data" / "learning"))

    today_interactions = [item for item in interaction_payloads if _extract_utc_day(item.get("timestamp")) == today]
    today_learning = [item for item in learning_payloads if _extract_utc_day(item.get("timestamp")) == today]

    success_count = sum(1 for item in today_interactions if bool(item.get("success", False)))
    approval_count = sum(1 for item in today_interactions if bool(item.get("approval_required", False)))
    training_candidate_count = sum(1 for item in today_interactions if bool(item.get("training_candidate", False)))
    memory_saved_count = sum(1 for item in today_interactions if bool(item.get("memory_saved", False)))
    tool_call_count = sum(int(item.get("tool_calls_count", 0) or 0) for item in today_interactions)
    intents = sorted({str(item.get("detected_intent", "")).strip() for item in today_interactions if str(item.get("detected_intent", "")).strip()})
    models = sorted({str(item.get("selected_model", "")).strip() for item in today_interactions if str(item.get("selected_model", "")).strip()})
    last_command = str(today_interactions[-1].get("user_command", "")).strip() if today_interactions else ""
    last_learning_intent = str(today_learning[-1].get("intent", "")).strip() if today_learning else ""

    lines = [
        f"Jarvis daily progress for {today}:",
        f"- Interactions today: {len(today_interactions)}",
        f"- Successful turns: {success_count}",
        f"- Learning records written today: {len(today_learning)}",
        f"- Training candidates created today: {training_candidate_count}",
        f"- Memory saves today: {memory_saved_count}",
        f"- Approval-gated turns today: {approval_count}",
        f"- Tool calls executed today: {tool_call_count}",
        f"- Intents seen today: {', '.join(intents[:8]) if intents else 'none yet'}",
        f"- Models used today: {', '.join(models[:6]) if models else 'none yet'}",
    ]
    if last_command:
        lines.append(f"- Latest command: {last_command[:160]}")
    if last_learning_intent:
        lines.append(f"- Latest learned intent: {last_learning_intent}")
    lines.append("- Interpretation: Jarvis learns by recording supervised interactions, storing local learning records, and promoting some successful turns into training candidates for OMNIRA fine-tuning.")
    return "\n".join(lines)


def _latest_record_stamp(paths: list[Path]) -> str:
    if not paths:
        return "none yet"
    latest = max(paths, key=lambda item: item.stat().st_mtime if item.exists() else 0)
    return datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat()


def _format_omnira_status(project_path: str) -> str:
    cfg = load_config()
    provider_name, provider_detail = _detect_backend_provider(cfg)
    memory_control = load_memory_control_state()
    runtime = JarvisRuntime(project_path=project_path)
    runtime_status = runtime.refresh_status(active_agent="omnira_bridge")

    jarvis_root = Path(project_path)
    workspace_root = jarvis_root.parent
    training_root = workspace_root / "omnira-ai" / "training"
    learning_paths = iter_json_like_files(jarvis_root / "data" / "learning")
    candidate_paths = iter_json_like_files(jarvis_root / "data" / "training_candidates")
    interaction_paths = iter_json_like_files(jarvis_root / "data" / "interactions" / project_id(project_path))
    training_configs = list((training_root / "configs").glob("*.yaml")) if (training_root / "configs").exists() else []
    training_datasets = list((training_root / "datasets").glob("**/*")) if (training_root / "datasets").exists() else []

    model_count = 0
    model_ids: list[str] = []
    if cfg.backend == "omnira" and cfg.base_url:
        try:
            response = httpx.get(f"{cfg.base_url.rstrip('/')}/models", timeout=5)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                model_count = len(payload)
                model_ids = [str(item.get("id", "")).strip() for item in payload if str(item.get("id", "")).strip()]
        except Exception:
            pass

    lines = [
        "OMNIRA operator status:",
        f"- Endpoint: {cfg.base_url}",
        f"- Provider: {provider_name}",
        f"- Runtime online: {'yes' if runtime_status.omnira_online else 'no'}",
        f"- Active compute mode: {memory_control.compute_mode}",
        f"- Pinned model: {memory_control.pinned_model or 'not set'}",
        f"- Model catalog count: {model_count}",
        f"- Model lanes: {', '.join(model_ids[:8]) if model_ids else 'unavailable'}",
        f"- Learning records: {len(learning_paths)}",
        f"- Training candidates: {len(candidate_paths)}",
        f"- Interaction records: {len(interaction_paths)}",
        f"- Latest learning write: {_latest_record_stamp(learning_paths)}",
        f"- Latest training candidate: {_latest_record_stamp(candidate_paths)}",
        f"- Training configs present: {len(training_configs)}",
        f"- Training dataset files present: {len(training_datasets)}",
        f"- Observation capture: {'on' if memory_control.observation_enabled else 'off'}",
        f"- Profile learning: {'on' if memory_control.profile_learning_enabled else 'off'}",
        f"- Internet learning: {'on' if memory_control.internet_learning_enabled else 'off'}",
        f"- Internet domains: {', '.join(memory_control.internet_learning_domains[:8]) if memory_control.internet_learning_domains else 'none'}",
        "- Live learning source: local interactions, learning records, and approved training candidates.",
        "- Screen sharing/camera learning: not active in this shell today.",
    ]
    if provider_detail:
        lines.append(f"- Provider detail: {provider_detail}")
    return "\n".join(lines)


def _format_autonomy_status(project_path: str) -> str:
    memory_control = load_memory_control_state()
    runtime = JarvisRuntime(project_path=project_path)
    status = runtime.refresh_status(active_agent="omnira_bridge")
    level = "supervised"
    blockers = [
        "high-risk actions require approval",
        "camera and screen perception are not active in this shell",
        "internet learning remains owner-controlled",
    ]
    if status.omnira_online and memory_control.observation_enabled and memory_control.training_enabled:
        blockers.append("live model backend quality still depends on the active provider and eval coverage")
    return "\n".join(
        [
            "Jarvis autonomy status:",
            f"- Current autonomy mode: {level}",
            f"- Runtime control mode: {status.control_mode}",
            f"- Backend online: {'yes' if status.omnira_online else 'no'}",
            f"- Observation capture: {'on' if memory_control.observation_enabled else 'off'}",
            f"- Training capture: {'on' if memory_control.training_enabled else 'off'}",
            f"- Internet learning: {'on' if memory_control.internet_learning_enabled else 'off'}",
            "- What Jarvis can do now: chat, route tasks, record learning, prepare changes, run safer actions, and ask for approval on risky work.",
            f"- What still blocks full autonomy: {'; '.join(blockers)}.",
        ]
    )


def _handle_shell_status_query(command_text: str, *, project_path: str) -> tuple[bool, str]:
    normalized = " ".join(str(command_text or "").strip().lower().split())
    if normalized in {"operating status", "status report", "how are you operating", "how is jarvis operating", "what model are you using", "what model is jarvis using"}:
        return True, _format_operating_status(project_path)
    if normalized in {"daily progress", "learning progress", "what did you learn today", "show daily progress", "show learning progress", "today progress"}:
        return True, _format_daily_progress(project_path)
    return False, ""


def _handle_shell_control_command(command_text: str, *, project_path: str, policy_profile: str) -> tuple[bool, bool, str]:
    normalized = " ".join(str(command_text or "").split())
    if not normalized.startswith("/"):
        return False, True, ""

    parts = normalized.split(maxsplit=2)
    command_name = parts[0].lower()
    if command_name in {"/help", "/?"}:
        return True, True, SHELL_HELP_TEXT
    if command_name in {"/exit", "/quit"}:
        return True, False, "Closing Jarvis shell."
    if command_name == "/status":
        return True, True, _format_operating_status(project_path)
    if command_name in {"/today", "/progress"}:
        return True, True, _format_daily_progress(project_path)
    if command_name == "/omnira":
        return True, True, _format_omnira_status(project_path)
    if command_name == "/autonomy":
        return True, True, _format_autonomy_status(project_path)
    if command_name == "/voice":
        listen_state = get_listen_state()
        capture_state = get_capture_state()
        speech_status = speech_mode_status()
        return True, True, "\n".join(
            [
                "Jarvis voice status:",
                f"- Listen enabled: {'yes' if listen_state.enabled else 'no'} ({listen_state.mode})",
                f"- Capture active: {'yes' if capture_state.active else 'no'}",
                f"- Capture provider: {capture_state.provider or 'not set'}",
                f"- Voice language mode: {speech_status.get('language_mode', 'unknown')}",
                f"- Voice provider: {speech_status.get('active_provider', speech_status.get('provider', 'unknown'))}",
                f"- Detail: {speech_status.get('detail', '')}",
            ]
        )
    if command_name == "/listen":
        if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
            return True, True, "Usage: /listen on|off"
        next_state = set_listen_state(parts[1].lower() == "on")
        return True, True, f"Jarvis listen state is now {'on' if next_state.enabled else 'off'} ({next_state.mode})."
    if command_name == "/approvals":
        return True, True, _format_pending_approvals()
    if command_name == "/approve":
        if len(parts) < 2:
            return True, True, "Usage: /approve <approval-id> [note]"
        note = parts[2] if len(parts) > 2 else ""
        result = approve_runtime_action(parts[1], project_path, profile=policy_profile, note=note)
        return True, True, result.message
    if command_name == "/reject":
        if len(parts) < 2:
            return True, True, "Usage: /reject <approval-id> [note]"
        note = parts[2] if len(parts) > 2 else ""
        result = reject_runtime_action(parts[1], note=note)
        return True, True, result.message
    if command_name == "/clear":
        return True, True, "\n" * 40
    return True, True, f"Unknown shell command: {parts[0]}. Type /help for shell controls."


def _execute_shell_turn(
    command_text: str,
    *,
    commander: JarvisCommander,
    project_path: str,
    policy_profile: str,
    show_meta: bool = False,
) -> tuple[bool, str]:
    handled, should_continue, output = _handle_shell_control_command(
        command_text,
        project_path=project_path,
        policy_profile=policy_profile,
    )
    if handled:
        return should_continue, output

    handled, output = _handle_shell_status_query(command_text, project_path=project_path)
    if handled:
        return True, output

    response = commander.handle_owner_command(
        OwnerCommand(
            text=command_text,
            source="terminal_shell",
            metadata={"channel": "shell"},
        )
    )
    return True, _format_shell_response(response, show_meta=show_meta)


@app.command("list-agents")
def list_agents_cmd():
    """List available agents."""
    for a in list_agents():
        desc = f" - {a.description}" if a.description else ""
        typer.echo(f"{a.name}{desc}")


@app.command()
def run(
    task: str = typer.Argument(..., help="Task for the agent"),
    agent: str = typer.Option("auto", "--agent", help="Agent name or 'auto'"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    policy_profile: str = typer.Option("personal", "--profile", help="Policy profile to use for runtime actions"),
    approve_runtime: bool = typer.Option(False, "--approve-runtime", help="Allow runtime actions that require approval under the selected profile"),
):
    """Run a task with a selected agent."""
    _ensure_backend()
    cfg = load_config()
    project_path = str(project.resolve())
    trace = start_trace(project_path, agent if agent != "auto" else None, source="cli.run")
    with span(trace, "cli.run", {"agent": agent}):
        runtime_result = maybe_execute_runtime_action(
            task,
            project_path,
            profile=policy_profile,
            approve_runtime=approve_runtime,
            source="cli.run",
            note=f"project={project_path}; profile={policy_profile}",
        )
        if runtime_result.handled:
            typer.echo("\n---\n")
            typer.echo(runtime_result.message)
            return

        assistant_result = handle_assistant_core(
            task,
            project_path=project_path,
            backend_status="MODEL CORE // ONLINE",
            backend_detail="Backend reachable.",
            active_model=cfg.model,
        )
        if assistant_result.handled:
            typer.echo("\n---\n")
            typer.echo(assistant_result.message)
            return

        chosen = agent
        dynamic_routing = False
        if agent == "auto":
            if cfg.backend == "omnira":
                if should_use_fast_assistant_route(task):
                    chosen = "assistant-lite"
                    record_handoff(trace, "auto", "omnira-lite", "omnira.fast-route", task=task)
                    typer.echo("[router] using OMNIRA Lite for a fast assistant turn")
                else:
                    chosen = "assistant"
                    dynamic_routing = True
                    record_handoff(trace, "auto", "omnira-prime", "omnira.dynamic-route", task=task)
                    typer.echo("[router] delegating agent and model selection to OMNIRA Prime")
            else:
                with span(trace, "router.pick", {"mode": "keyword"}):
                    chosen = pick_agent(task)
                record_handoff(trace, "auto", chosen, "router.pick", task=task)
                typer.echo(f"[router] selected agent: {chosen}")

        if dynamic_routing:
            agent_profile = _omnira_dynamic_profile()
        elif chosen == "assistant-lite":
            agent_profile = _omnira_fast_profile()
        else:
            agent_profile = get_agent(chosen)
        chunks: list[str] = []
        for chunk in stream_task(task, agent_profile, project_path, trace=trace, source="cli.run", dynamic_routing=dynamic_routing):
            chunks.append(chunk)
            typer.echo(chunk, nl=False)
        output = "".join(chunks).strip()
    typer.echo("\n---\n")
    typer.echo(output)


@app.command("shell")
def shell_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    policy_profile: str = typer.Option("personal", "--profile", help="Policy profile to use for runtime actions"),
    show_meta: bool = typer.Option(False, "--show-meta", help="Show intent, model, and state after each Jarvis reply"),
):
    """Start an interactive Jarvis terminal shell."""
    project_path = str(project.resolve())
    cfg = load_config()
    backend_ok, backend_message = check_backend()
    commander = JarvisCommander(project_path=project_path, profile=policy_profile, stage_approvals=True)

    typer.echo("JARVIS SHELL // ONLINE")
    typer.echo(f"Project: {project_path}")
    typer.echo(f"Profile: {policy_profile}")
    typer.echo(f"Backend: {'online' if backend_ok else 'offline'} | {backend_message}")
    typer.echo(f"Default model lane: {cfg.model}")
    provider_name, provider_detail = _detect_backend_provider(cfg)
    typer.echo(f"Model provider: {provider_name}")
    if provider_name == "mock":
        typer.echo("Warning: OMNIRA is currently returning placeholder mock responses, not live model output.")
    if provider_detail:
        typer.echo(provider_detail)
    typer.echo("Type /help for shell controls. Type natural language for everything else.")

    while True:
        try:
            command_text = input("you> ")
        except EOFError:
            typer.echo("\nClosing Jarvis shell.")
            break
        except KeyboardInterrupt:
            typer.echo("\nClosing Jarvis shell.")
            break

        normalized = " ".join(command_text.split())
        if not normalized:
            continue

        should_continue, output = _execute_shell_turn(
            normalized,
            commander=commander,
            project_path=project_path,
            policy_profile=policy_profile,
            show_meta=show_meta,
        )
        if output:
            typer.echo("")
            typer.echo(output)
            typer.echo("")
        if not should_continue:
            break


@app.command("shell-window")
def shell_window_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    policy_profile: str = typer.Option("personal", "--profile", help="Policy profile to use for runtime actions"),
    show_meta: bool = typer.Option(True, "--show-meta/--hide-meta", help="Show intent, model, and state after each Jarvis reply"),
):
    """Open Jarvis shell in a dedicated terminal window."""
    project_path = str(project.resolve())
    env = os.environ.copy()
    current_pythonpath = str(env.get("PYTHONPATH", "")).strip()
    env["PYTHONPATH"] = project_path if not current_pythonpath else f"{project_path}{os.pathsep}{current_pythonpath}"

    command = [
        sys.executable,
        "-m",
        "agenthub",
        "shell",
        "--project",
        project_path,
        "--profile",
        policy_profile,
    ]
    if show_meta:
        command.append("--show-meta")

    popen_kwargs: dict[str, object] = {
        "cwd": project_path,
        "env": env,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    else:
        popen_kwargs["start_new_session"] = True

    subprocess.Popen(command, **popen_kwargs)
    typer.echo(f"Opened Jarvis shell window for {project_path}")


@app.command("approvals")
def approvals_cmd():
    """List pending runtime approvals."""
    items = list_pending_approvals()
    if not items:
        typer.echo("No pending approvals.")
        return
    for item in items:
        typer.echo(f"{item.id} | {item.risk} | {item.source} | {item.task}")


@app.command("approve-runtime")
def approve_runtime_cmd(
    approval_id: str = typer.Argument(..., help="Pending approval id"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    policy_profile: str = typer.Option("personal", "--profile", help="Policy profile to use for runtime actions"),
    note: str = typer.Option("", "--note", help="Optional approval note"),
):
    """Approve and execute a pending runtime action."""
    result = approve_runtime_action(approval_id, str(project.resolve()), profile=policy_profile, note=note)
    typer.echo("\n---\n")
    typer.echo(result.message)


@app.command("reject-runtime")
def reject_runtime_cmd(
    approval_id: str = typer.Argument(..., help="Pending approval id"),
    note: str = typer.Option("", "--note", help="Optional rejection note"),
):
    """Reject a pending runtime action."""
    result = reject_runtime_action(approval_id, note=note)
    typer.echo("\n---\n")
    typer.echo(result.message)


@app.command("evals")
def evals_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    file: Path = typer.Option(None, "--file", help="Eval task file"),
):
    """Run golden eval tasks and write results to data/evals."""
    _ensure_backend()
    out_path = run_golden_evals(str(project.resolve()), task_file=file)
    typer.echo(f"Eval results written to {out_path}")


@app.command("list-tools")
def list_tools_cmd():
    """List available tools and default permissions."""
    for t in list_tools():
        agents = ", ".join(t.default_allowed_agents)
        typer.echo(f"{t.name} ({t.risk}) - {t.description} | default: [{agents}]")


@app.command("list-profiles")
def list_profiles_cmd():
    """List available user policy profiles."""
    for profile in list_profiles():
        typer.echo(f"{profile.name} - {profile.description}")


@app.command("show-profile")
def show_profile_cmd(
    name: str = typer.Argument(..., help="Profile name"),
):
    """Show a user policy profile."""
    profile = get_profile(name)
    typer.echo(f"name: {profile.name}")
    typer.echo(f"description: {profile.description}")
    typer.echo(f"default_risk: {profile.default_risk}")
    typer.echo(f"require_approval_for: {', '.join(profile.require_approval_for)}")
    typer.echo(f"allowed_paths: {', '.join(profile.allowed_paths)}")
    typer.echo(f"allowed_apps: {', '.join(profile.allowed_apps)}")
    typer.echo(f"allowed_commands: {', '.join(profile.allowed_commands)}")
    typer.echo(f"recording_requires_consent: {profile.recording_requires_consent}")


def _set_runtime_mode(project: Path, mode: str, *, note: str) -> None:
    runtime = JarvisRuntime(project_path=str(project.resolve()))
    status = runtime.set_control_mode(mode, source=f"cli.{mode}", note=note)
    typer.echo(f"Jarvis control mode: {status.control_mode}")


@app.command("start")
def start_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Set Jarvis runtime control mode to active."""
    _set_runtime_mode(project, "active", note="owner start command")


@app.command("resume")
def resume_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Resume Jarvis runtime automation."""
    _set_runtime_mode(project, "active", note="owner resume command")


@app.command("pause")
def pause_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Pause Jarvis runtime automation."""
    _set_runtime_mode(project, "paused", note="owner pause command")


@app.command("stop")
def stop_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Stop Jarvis runtime automation."""
    _set_runtime_mode(project, "stopped", note="owner stop command")


@app.command("kill")
def kill_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Emergency kill Jarvis runtime automation."""
    _set_runtime_mode(project, "killed", note="owner kill command")


@app.command("runtime-status")
def runtime_status_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Show Jarvis runtime control and health state."""
    runtime = JarvisRuntime(project_path=str(project.resolve()))
    status = runtime.status()
    typer.echo(f"control_mode: {status.control_mode}")
    typer.echo(f"commands_blocked: {status.commands_blocked}")
    typer.echo(f"active_tasks: {status.active_tasks}")
    typer.echo(f"pending_approvals: {status.pending_approvals}")
    typer.echo(f"active_model: {status.active_model}")


@app.command("check-tool-policy")
def check_tool_policy_cmd(
    profile: str = typer.Argument(..., help="Profile name"),
    tool: str = typer.Argument(..., help="Tool name"),
):
    """Check whether a tool requires approval for a profile."""
    decision = evaluate_tool_access(profile, tool)
    typer.echo(f"profile: {decision.profile}")
    typer.echo(f"tool: {decision.tool}")
    typer.echo(f"tool_risk: {decision.tool_risk}")
    typer.echo(f"requires_approval: {decision.requires_approval}")
    typer.echo(f"reason: {decision.reason}")


@app.command("check-path-policy")
def check_path_policy_cmd(
    profile: str = typer.Argument(..., help="Profile name"),
    path_value: str = typer.Argument(..., help="Path to evaluate"),
):
    """Check whether a path is allowed for a profile."""
    decision = evaluate_path_access(profile, path_value)
    typer.echo(f"profile: {decision.profile}")
    typer.echo(f"target: {decision.target}")
    typer.echo(f"allowed: {decision.allowed}")
    typer.echo(f"reason: {decision.reason}")


@app.command("check-app-policy")
def check_app_policy_cmd(
    profile: str = typer.Argument(..., help="Profile name"),
    app_name: str = typer.Argument(..., help="App name"),
):
    """Check whether an app is allowed for a profile."""
    decision = evaluate_app_access(profile, app_name)
    typer.echo(f"profile: {decision.profile}")
    typer.echo(f"target: {decision.target}")
    typer.echo(f"allowed: {decision.allowed}")
    typer.echo(f"reason: {decision.reason}")


@app.command("check-command-policy")
def check_command_policy_cmd(
    profile: str = typer.Argument(..., help="Profile name"),
    command_text: str = typer.Argument(..., help="Command text"),
):
    """Check whether a command is allowed for a profile."""
    decision = evaluate_command_access(profile, command_text)
    typer.echo(f"profile: {decision.profile}")
    typer.echo(f"target: {decision.target}")
    typer.echo(f"allowed: {decision.allowed}")
    typer.echo(f"reason: {decision.reason}")


@app.command("check-recording-policy")
def check_recording_policy_cmd(
    profile: str = typer.Argument(..., help="Profile name"),
):
    """Check whether recording requires consent for a profile."""
    typer.echo(f"profile: {profile}")
    typer.echo(f"recording_requires_consent: {recording_requires_consent(profile)}")


@app.command("audit-log")
def audit_log_cmd(
    action: str = typer.Argument(..., help="Action name"),
    profile: str = typer.Argument(..., help="Profile name"),
    target: str = typer.Argument(..., help="Action target"),
    outcome: str = typer.Argument(..., help="Outcome value"),
    detail: str = typer.Option("", "--detail", help="Optional detail"),
):
    """Append a local action audit event."""
    path = append_audit_event(action, profile, target, outcome, detail)
    typer.echo(f"audit_event: {path}")


@app.command("audit-history")
def audit_history_cmd(
    limit: int = typer.Option(20, "--limit", help="Maximum events to show"),
):
    """Show recent local action audit events."""
    for event in list_audit_events(limit=limit):
        typer.echo(f"{event.timestamp} | {event.profile} | {event.action} | {event.target} | {event.outcome}")


@app.command("voice-route")
def voice_route_cmd(
    transcript: str = typer.Argument(..., help="Transcript text to route"),
):
    """Route a transcript through the existing agent router."""
    route = route_transcript(transcript)
    typer.echo(f"suggested_agent: {route.suggested_agent}")
    typer.echo(f"normalized_task: {route.normalized_task}")


@app.command("listen-status")
def listen_status_cmd():
    """Show current local listen state."""
    state = get_listen_state()
    typer.echo(f"enabled: {state.enabled}")
    typer.echo(f"mode: {state.mode}")


@app.command("listen-on")
def listen_on_cmd(
    mode: str = typer.Option("push-to-talk", "--mode", help="Listen mode"),
):
    """Enable local listen mode."""
    state = set_listen_state(True, mode=mode)
    typer.echo(f"enabled: {state.enabled}")
    typer.echo(f"mode: {state.mode}")


@app.command("listen-off")
def listen_off_cmd():
    """Disable local listen mode."""
    state = set_listen_state(False)
    typer.echo(f"enabled: {state.enabled}")
    typer.echo(f"mode: {state.mode}")


@app.command("list-stt-providers")
def list_stt_providers_cmd():
    """List available speech-to-text providers."""
    for provider in list_speech_providers():
        typer.echo(
            f"{provider.name} ({provider.kind}) - {provider.description} | network: {provider.requires_network}"
        )


@app.command("transcribe-text")
def transcribe_text_cmd(
    text: str = typer.Argument(..., help="Transcript text"),
):
    """Normalize inline transcript text through the STT abstraction."""
    result = transcribe_text_input(text)
    typer.echo(f"provider: {result.provider}")
    typer.echo(f"source: {result.source}")
    typer.echo(f"transcript: {result.transcript}")


@app.command("transcribe-file")
def transcribe_file_cmd(
    path_value: str = typer.Argument(..., help="Text or audio file path"),
    provider: str = typer.Option("text", "--provider", help="Speech provider name"),
):
    """Transcribe a file through the configured speech provider."""
    result = transcribe_file_input(path_value, provider=provider)
    typer.echo(f"provider: {result.provider}")
    typer.echo(f"source: {result.source}")
    typer.echo(f"transcript: {result.transcript}")


@app.command("mic-status")
def mic_status_cmd():
    """Show local microphone and capture state."""
    cfg = get_microphone_config()
    capture = get_capture_state()
    speech = get_speech_mode_config()
    active_provider = resolve_speech_provider(speech, prefer_realtime=cfg.mode == "continuous")
    typer.echo(f"device: {cfg.device}")
    typer.echo(f"sample_rate: {cfg.sample_rate}")
    typer.echo(f"chunk_ms: {cfg.chunk_ms}")
    typer.echo(f"mode: {cfg.mode}")
    typer.echo(f"capture_active: {capture.active}")
    typer.echo(f"capture_provider: {capture.provider}")
    typer.echo(f"speech_language_mode: {speech.language_mode}")
    typer.echo(f"speech_provider: {speech.provider}")
    typer.echo(f"speech_active_provider: {active_provider}")
    typer.echo(f"speech_culture: {speech.culture}")


@app.command("speech-status")
def speech_status_cmd():
    """Show current speech language mode and recognizer availability."""
    status = speech_mode_status()
    typer.echo(f"language_mode: {status['language_mode']}")
    typer.echo(f"provider: {status['provider']}")
    typer.echo(f"active_provider: {status['active_provider']}")
    typer.echo(f"configured_culture: {status['configured_culture']}")
    typer.echo(f"resolved_culture: {status['resolved_culture']}")
    typer.echo(f"availability: {status['availability']}")
    typer.echo(f"detail: {status['detail']}")
    recognizers = status["recognizers"]
    if not recognizers:
        typer.echo("recognizers: none")
        return
    typer.echo("recognizers:")
    for item in recognizers:
        typer.echo(f"- {item['culture']} | {item['name']}")


@app.command("speech-mode")
def speech_mode_cmd(
    language_mode: str = typer.Option(None, "--language", help="Speech mode: english, hinglish, hindi"),
    provider: str = typer.Option(None, "--provider", help="Speech provider: windows_dictation, openai_audio, auto"),
    culture: str = typer.Option(None, "--culture", help="Recognizer culture override such as en-US or hi-IN"),
):
    """Get or update the active speech language mode."""
    if language_mode is None and provider is None and culture is None:
        cfg = get_speech_mode_config()
    else:
        cfg = set_speech_mode_config(language_mode=language_mode, provider=provider, culture=culture)
    typer.echo(f"language_mode: {cfg.language_mode}")
    typer.echo(f"provider: {cfg.provider}")
    typer.echo(f"culture: {cfg.culture}")
    status = speech_mode_status()
    typer.echo(f"active_provider: {status['active_provider']}")
    typer.echo(f"availability: {status['availability']}")
    typer.echo(f"detail: {status['detail']}")


@app.command("speech-recognizers")
def speech_recognizers_cmd():
    """List installed Windows speech recognizers."""
    try:
        recognizers = list_windows_recognizers()
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    if not recognizers:
        typer.echo("No Windows speech recognizers found.")
        return
    for item in recognizers:
        typer.echo(f"{item.culture}: {item.name}")


@app.command("speech-test")
def speech_test_cmd(
    duration: float = typer.Option(4.0, "--duration", help="Recording duration in seconds"),
    allow_empty: bool = typer.Option(False, "--allow-empty", help="Allow empty transcript results"),
):
    """Record and transcribe from the active microphone using the active speech mode."""
    try:
        result = transcribe_microphone_input(duration_s=duration, provider="auto", allow_empty=allow_empty)
    except (RuntimeError, ValueError) as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"provider: {result.provider}")
    typer.echo(f"source: {result.source}")
    typer.echo(f"transcript: {result.transcript}")


@app.command("mic-config")
def mic_config_cmd(
    device: str = typer.Option(None, "--device", help="Microphone device name"),
    sample_rate: int = typer.Option(None, "--sample-rate", help="Sample rate"),
    chunk_ms: int = typer.Option(None, "--chunk-ms", help="Chunk size in milliseconds"),
    mode: str = typer.Option(None, "--mode", help="Capture mode"),
):
    """Update local microphone configuration."""
    cfg = set_microphone_config(device=device, sample_rate=sample_rate, chunk_ms=chunk_ms, mode=mode)
    typer.echo(f"device: {cfg.device}")
    typer.echo(f"sample_rate: {cfg.sample_rate}")
    typer.echo(f"chunk_ms: {cfg.chunk_ms}")
    typer.echo(f"mode: {cfg.mode}")


@app.command("capture-start")
def capture_start_cmd(
    provider: str = typer.Option("text", "--provider", help="Speech provider name"),
    mode: str = typer.Option(None, "--mode", help="Capture mode override"),
):
    """Enable local microphone capture state."""
    state = set_capture_state(True, provider=provider, mode=mode)
    typer.echo(f"active: {state.active}")
    typer.echo(f"provider: {state.provider}")
    typer.echo(f"mode: {state.mode}")


@app.command("capture-stop")
def capture_stop_cmd():
    """Disable local microphone capture state."""
    state = set_capture_state(False)
    typer.echo(f"active: {state.active}")
    typer.echo(f"provider: {state.provider}")
    typer.echo(f"mode: {state.mode}")


@app.command("mic-devices")
def mic_devices_cmd():
    """List available microphone input devices."""
    try:
        devices = list_input_devices()
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    if not devices:
        typer.echo("No input devices found.")
        return
    for device in devices:
        typer.echo(
            f"{device.index}: {device.name} | channels={device.max_input_channels} | sample_rate={device.default_sample_rate}"
        )


@app.command("mic-record")
def mic_record_cmd(
    duration: float = typer.Option(5.0, "--duration", help="Recording duration in seconds"),
    out: str = typer.Option(None, "--out", help="Output WAV path"),
):
    """Record a microphone clip to a WAV file."""
    try:
        path = record_microphone_clip(duration_s=duration, output_path=out)
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1)
    typer.echo(f"recording: {path}")


@app.command("interview-capture-turn")
def interview_capture_turn_cmd(
    session_id: str = typer.Argument(..., help="Interview session id"),
    role: str = typer.Argument(..., help="Turn role: interviewer or candidate"),
    text: str = typer.Option(None, "--text", help="Inline transcript text"),
    file: str = typer.Option(None, "--file", help="Text or audio file to transcribe"),
    provider: str = typer.Option("text", "--provider", help="Speech provider name"),
    record_seconds: float = typer.Option(None, "--record-seconds", help="Record audio before transcription"),
):
    """Capture a turn from text, file, or recorded audio, then append it to an interview session."""
    if role not in {"interviewer", "candidate"}:
        typer.echo("role must be 'interviewer' or 'candidate'")
        raise typer.Exit(code=1)

    source_count = sum(value is not None for value in [text, file, record_seconds])
    if source_count != 1:
        typer.echo("provide exactly one source: --text, --file, or --record-seconds")
        raise typer.Exit(code=1)

    if text is not None:
        result = transcribe_text_input(text)
    elif file is not None:
        try:
            result = transcribe_file_input(file, provider=provider)
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1)
    else:
        try:
            recorded = record_microphone_clip(duration_s=record_seconds)
            result = transcribe_file_input(str(recorded), provider=provider)
        except (RuntimeError, FileNotFoundError, ValueError) as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1)

    session = add_turn(session_id, role, result.transcript)
    typer.echo(f"session_id: {session.id}")
    typer.echo(f"role: {role}")
    typer.echo(f"provider: {result.provider}")
    typer.echo(f"source: {result.source}")
    typer.echo(f"transcript: {result.transcript}")
    typer.echo(f"turn_count: {len(session.turns)}")

    if role == "candidate":
        summary = coaching_summary(session_id)
        typer.echo(f"answer_score: {summary['answer_score']}/{summary['max_score']}")
        typer.echo(f"feedback: {summary['feedback']}")


@app.command("interview-start")
def interview_start_cmd(
    title: str = typer.Argument(..., help="Interview session title"),
):
    """Create a local interview coaching session."""
    session = create_session(title)
    typer.echo(f"session_id: {session.id}")
    typer.echo(f"created_at: {session.created_at}")
    typer.echo(f"title: {session.title}")


@app.command("interview-add-turn")
def interview_add_turn_cmd(
    session_id: str = typer.Argument(..., help="Interview session id"),
    role: str = typer.Argument(..., help="Turn role: interviewer or candidate"),
    text: str = typer.Argument(..., help="Turn transcript"),
):
    """Append a transcript turn to an interview session."""
    session = add_turn(session_id, role, text)
    typer.echo(f"session_id: {session.id}")
    typer.echo(f"turn_count: {len(session.turns)}")


@app.command("interview-summary")
def interview_summary_cmd(
    session_id: str = typer.Argument(..., help="Interview session id"),
):
    """Show a compact summary for an interview session."""
    summary = session_summary(session_id)
    for key, value in summary.items():
        typer.echo(f"{key}: {value}")


@app.command("interview-show")
def interview_show_cmd(
    session_id: str = typer.Argument(..., help="Interview session id"),
):
    """Show stored interview turns."""
    session = load_session(session_id)
    typer.echo(f"session_id: {session.id}")
    typer.echo(f"title: {session.title}")
    for idx, turn in enumerate(session.turns, start=1):
        suffix = f" [{turn.question_type}]" if turn.question_type else ""
        typer.echo(f"{idx}. {turn.role}{suffix}: {turn.text}")


@app.command("interview-list")
def interview_list_cmd(
    limit: int = typer.Option(20, "--limit", help="Maximum sessions to show"),
):
    """List recent interview coaching sessions."""
    for session in list_sessions(limit=limit):
        typer.echo(f"{session.created_at} | {session.id} | {session.title} | turns={len(session.turns)}")


@app.command("interview-coach")
def interview_coach_cmd(
    session_id: str = typer.Argument(..., help="Interview session id"),
):
    """Show lightweight coaching feedback for the latest recorded answer."""
    summary = coaching_summary(session_id)
    for key, value in summary.items():
        typer.echo(f"{key}: {value}")


@app.command("interview-drills")
def interview_drills_cmd(
    limit: int = typer.Option(20, "--limit", help="Maximum sessions to analyze"),
):
    """Show recurring interview coaching drills from recent sessions."""
    for drill in coaching_drills(limit=limit):
        typer.echo(drill)


@app.command("plan")
def plan_cmd(
    task: str = typer.Argument(..., help="Task to plan"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Generate a JSON plan without executing it."""
    _ensure_backend()
    steps = create_plan(task, str(project.resolve()))
    for i, s in enumerate(steps, start=1):
        agent_name = s.get("agent", "auto")
        task_text = s.get("task", "")
        typer.echo(f"{i}. {agent_name}: {task_text}")


@app.command("run-plan")
def run_plan_cmd(
    task: str = typer.Argument(..., help="Task to plan and execute"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Plan and execute a multi-agent workflow."""
    _ensure_backend()
    outputs = run_plan(task, str(project.resolve()))
    for i, out in enumerate(outputs, start=1):
        typer.echo(f"\n--- Step {i} ---\n")
        typer.echo(out)


@app.command("enqueue")
def enqueue_cmd(
    task: str = typer.Argument(..., help="Task to enqueue"),
    agent: str = typer.Option("auto", "--agent", help="Agent name or 'auto'"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Queue a task for background processing."""
    _ensure_backend()
    out = enqueue(task, agent, str(project.resolve()))
    typer.echo(f"Enqueued: {out}")


@app.command("worker")
def worker_cmd(
    once: bool = typer.Option(False, "--once", help="Process a single task then exit"),
    interval_s: int = typer.Option(5, "--interval", help="Polling interval in seconds"),
):
    """Process queued tasks."""
    while True:
        item = claim_next()
        if item is None:
            if once:
                return
            time.sleep(interval_s)
            continue
        _ensure_backend()
        result = process_item(item)
        typer.echo(f"Processed: {result}")
        if once:
            return


@app.command("queue-status")
def queue_status_cmd():
    """Show queue counts."""
    counts = queue_counts()
    for k, v in counts.items():
        typer.echo(f"{k}: {v}")


@app.command("web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
    port: int = typer.Option(8000, "--port", help="Port to bind"),
):
    """Start the local web UI."""
    from .web import start as start_web

    start_web(host=host, port=port)


@app.command("bridge")
def bridge_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind"),
    port: int = typer.Option(8010, "--port", help="Port to bind"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    policy_profile: str = typer.Option("personal", "--profile", help="Policy profile to use for runtime actions"),
):
    """Start the Jarvis cinematic bridge server for the Tauri shell."""
    from .bridge_server import start as start_bridge_server

    start_bridge_server(host=host, port=port, project_path=str(project.resolve()), policy_profile=policy_profile)


@app.command("desktop")
def desktop_cmd():
    """Start the primary Jarvis desktop shell."""
    try:
        from .desktop_qt import start_cinematic_desktop
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "") or "dependency"
        if missing.startswith("PySide6"):
            typer.echo("PySide6 not available, starting classic desktop shell instead.")
            from .desktop import start_desktop

            start_desktop()
            return
        raise

    start_cinematic_desktop()


@app.command("desktop-classic")
def desktop_classic_cmd():
    """Start the classic Tkinter desktop prototype."""
    from .desktop import start_desktop

    start_desktop()


@app.command("desktop-cinematic")
def desktop_cinematic_cmd():
    """Start the cinematic Jarvis desktop shell."""
    try:
        from .desktop_qt import start_cinematic_desktop
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "") or "dependency"
        if missing.startswith("PySide6"):
            typer.echo(
                "PySide6 is not installed. Run: pip install -e .[desktop]"
            )
            raise typer.Exit(code=1)
        raise

    start_cinematic_desktop()


@app.command("backend-check")
def backend_check_cmd():
    """Check connectivity to the configured model backend."""
    ok, msg = check_backend()
    status = "OK" if ok else "FAIL"
    typer.echo(f"{status}: {msg}")


@app.command("export-dataset")
def export_dataset_cmd(
    out: Path = typer.Option(Path("data/finetune.jsonl"), "--out", help="Output JSONL path"),
    project: Path = typer.Option(None, "--project", help="Project path filter"),
    min_chars: int = typer.Option(40, "--min-chars", help="Minimum assistant chars"),
):
    """Export run logs into a fine-tuning JSONL dataset."""
    project_path = str(project.resolve()) if project else None
    count = export_dataset(out, project_path=project_path, min_chars=min_chars)
    typer.echo(f"Wrote {count} records to {out}")


@app.command("repo-health")
def repo_health_cmd(
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path to scan"),
):
    """Read-only repo health scan (Stage A)."""
    issues = scan_repo(project.resolve())
    if not issues:
        typer.echo("No issues found.")
        return
    for it in issues:
        typer.echo(f"{it.kind}: {it.path}:{it.line} - {it.detail}")


@app.command("propose-fix")
def propose_fix_cmd(
    task: str = typer.Argument(..., help="Task to propose a patch for"),
    agent: str = typer.Option("auto", "--agent", help="Agent name or 'auto'"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Generate a proposal patch (no changes applied)."""
    result = propose_fix(task, agent, str(project.resolve()))
    typer.echo(f"Summary: {result.summary_path}")
    typer.echo(f"Patch: {result.patch_path}")
    typer.echo(f"Raw: {result.raw_output_path}")


@app.command("apply-proposal")
def apply_proposal_cmd(
    proposal_id: str = typer.Argument(..., help="Proposal id (timestamp prefix)"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    confirm: bool = typer.Option(False, "--confirm", help="Apply the patch (default: dry-run)"),
):
    """Apply a proposal patch (dry-run by default)."""
    result = apply_proposal(proposal_id, str(project.resolve()), confirm)
    status = "OK" if result.ok else "FAIL"
    typer.echo(f"{status}: {result.message}")


@app.command("auto-apply-docs")
def auto_apply_docs_cmd(
    proposal_id: str = typer.Argument(..., help="Proposal id (timestamp prefix)"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
):
    """Auto-apply docs-only proposals (Stage C)."""
    result = auto_apply_docs_only(proposal_id, str(project.resolve()))
    status = "OK" if result.ok else "FAIL"
    typer.echo(f"{status}: {result.message}")


@app.command("record-approval")
def record_approval_cmd(
    proposal_id: str = typer.Argument(..., help="Proposal id (timestamp prefix)"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    note: str = typer.Option("", "--note", help="Approval note"),
):
    """Record an approval for a proposal into data/approvals."""
    result = record_approval(proposal_id, str(project.resolve()), note=note or None)
    status = "OK" if result.ok else "FAIL"
    extra = f" -> {result.record_path}" if result.record_path else ""
    typer.echo(f"{status}: {result.message}{extra}")


@app.command("schedule-repo-health")
def schedule_repo_health_cmd(
    interval: int = typer.Option(3600, "--interval", help="Interval seconds"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    once: bool = typer.Option(False, "--once", help="Run once and exit"),
):
    """Schedule periodic repo health scans."""
    schedule_repo_health(str(project.resolve()), interval_s=interval, once=once)


@app.command("maintenance")
def maintenance_cmd(
    interval: int = typer.Option(3600, "--interval", help="Interval seconds"),
    project: Path = typer.Option(Path.cwd(), "--project", help="Project path"),
    cleanup_days: int = typer.Option(0, "--cleanup-days", help="Delete data files older than N days (0=disabled)"),
    once: bool = typer.Option(False, "--once", help="Run once and exit"),
):
    """Run scheduled maintenance (repo health + optional cleanup)."""
    cleanup = cleanup_days if cleanup_days > 0 else None
    schedule_maintenance(str(project.resolve()), interval_s=interval, cleanup_days=cleanup, once=once)


if __name__ == "__main__":
    app()
