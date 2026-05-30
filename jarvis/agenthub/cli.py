from __future__ import annotations

from pathlib import Path
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
from .streaming import stream_task
from .approval_queue import list_pending_approvals
from .runtime_actions import maybe_execute_runtime_action, approve_runtime_action, reject_runtime_action

app = typer.Typer(no_args_is_help=True)


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

def _ensure_backend():
    ok, msg = check_backend()
    if not ok:
        typer.echo(f"Backend check failed: {msg}")
        raise typer.Exit(code=1)


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

        chosen = agent
        dynamic_routing = False
        if agent == "auto":
            if cfg.backend == "omnira":
                chosen = "assistant"
                dynamic_routing = True
                record_handoff(trace, "auto", "omnira-prime", "omnira.dynamic-route", task=task)
                typer.echo("[router] delegating agent and model selection to OMNIRA Prime")
            else:
                with span(trace, "router.pick", {"mode": "keyword"}):
                    chosen = pick_agent(task)
                record_handoff(trace, "auto", chosen, "router.pick", task=task)
                typer.echo(f"[router] selected agent: {chosen}")

        agent_profile = _omnira_dynamic_profile() if dynamic_routing else get_agent(chosen)
        chunks: list[str] = []
        for chunk in stream_task(task, agent_profile, project_path, trace=trace, source="cli.run", dynamic_routing=dynamic_routing):
            chunks.append(chunk)
            typer.echo(chunk, nl=False)
        output = "".join(chunks).strip()
    typer.echo("\n---\n")
    typer.echo(output)


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
    typer.echo(f"device: {cfg.device}")
    typer.echo(f"sample_rate: {cfg.sample_rate}")
    typer.echo(f"chunk_ms: {cfg.chunk_ms}")
    typer.echo(f"mode: {cfg.mode}")
    typer.echo(f"capture_active: {capture.active}")
    typer.echo(f"capture_provider: {capture.provider}")
    typer.echo(f"speech_language_mode: {speech.language_mode}")
    typer.echo(f"speech_provider: {speech.provider}")
    typer.echo(f"speech_culture: {speech.culture}")


@app.command("speech-status")
def speech_status_cmd():
    """Show current speech language mode and recognizer availability."""
    status = speech_mode_status()
    typer.echo(f"language_mode: {status['language_mode']}")
    typer.echo(f"provider: {status['provider']}")
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


@app.command("desktop")
def desktop_cmd():
    """Start the native Jarvis Lite desktop app."""
    from .desktop import start_desktop

    start_desktop()


@app.command("desktop-cinematic")
def desktop_cinematic_cmd():
    """Start the experimental cinematic Jarvis desktop shell."""
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
