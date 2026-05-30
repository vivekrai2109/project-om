from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .agents import get_agent
from .orchestrator import run_task
from .streaming import stream_task
from .config import data_dir
from .router import pick_agent
from .queue import queue_counts
from .memory import project_id
from .backend import check_backend
from .auto_apply import auto_apply_docs_only, check_docs_only
from .approvals import record_approval
from .apply_patch_cmd import apply_proposal
from .tracing import start_trace, span, record_handoff
from .interview import create_session, add_turn, list_sessions, load_session, session_summary, coaching_summary
from .speech import get_microphone_config, get_capture_state, list_input_devices, record_microphone_clip
from .voice import get_listen_state
from .approval_queue import list_pending_approvals
from .runtime_actions import maybe_execute_runtime_action, approve_runtime_action, reject_runtime_action
from .assistant_core import handle_assistant_core


app = FastAPI(title="Agent Hub")


def _load_recent_runs(limit: int = 50) -> list[dict[str, Any]]:
    runs_dir = data_dir() / "runs"
    if not runs_dir.exists():
        return []
    files = sorted(runs_dir.glob("**/*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    items = []
    for p in files[:limit]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_file"] = str(p.relative_to(data_dir()))
            items.append(data)
        except Exception:
            continue
    return items


def _latest_run_file(project_path: str) -> str | None:
    runs_dir = data_dir() / "runs" / project_id(project_path)
    if not runs_dir.exists():
        return None
    files = sorted(runs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return str(files[0].relative_to(data_dir()))


def _load_proposals(limit: int = 20) -> list[dict[str, Any]]:
    proposals_dir = data_dir() / "proposals"
    if not proposals_dir.exists():
        return []
    files = sorted(proposals_dir.glob("*_summary.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    items = []
    for p in files[:limit]:
        ts = p.name.replace("_summary.md", "")
        patch = proposals_dir / f"{ts}.patch"
        raw = proposals_dir / f"{ts}_raw.txt"
        items.append(
            {
                "id": ts,
                "summary_file": str(p.relative_to(data_dir())),
                "patch_file": str(patch.relative_to(data_dir())) if patch.exists() else "",
                "raw_file": str(raw.relative_to(data_dir())) if raw.exists() else "",
            }
        )
    return items


def _stats_from_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(runs)
    last = runs[0].get("timestamp") if runs else ""
    tokens = 0
    for r in runs:
        t = r.get("total_tokens")
        if isinstance(t, int):
            tokens += t
    return {
        "total_runs": total,
        "last_run": str(last),
        "total_tokens": tokens,
    }


def _load_interviews(limit: int = 20) -> list[dict[str, Any]]:
    items = []
    for session in list_sessions(limit=limit):
        items.append(
            {
                "id": session.id,
                "title": session.title,
                "created_at": session.created_at,
                "turn_count": len(session.turns),
            }
        )
    return items


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _render_home(message: str | None = None) -> str:
    runs = _load_recent_runs()
    counts = queue_counts()
    stats = _stats_from_runs(runs)
    proposals = _load_proposals()
    interviews = _load_interviews()

    runs_rows = []
    for r in runs:
        task = _html_escape(str(r.get("task", "")))[:120]
        agent = _html_escape(str(r.get("agent", "")))
        model = _html_escape(str(r.get("model", "")))
        run_file = _html_escape(str(r.get("_file", "")))
        tokens = _html_escape(str(r.get("total_tokens", "")))
        runs_rows.append(
            f"<tr data-run-file=\"{run_file}\"><td>{agent}</td><td>{model}</td><td>{tokens}</td><td>{task}</td></tr>"
        )
    runs_html = "\n".join(runs_rows) if runs_rows else "<tr><td colspan='4'>No runs yet</td></tr>"

    proposal_rows = []
    for p in proposals:
        pid = _html_escape(str(p.get("id", "")))
        proposal_rows.append(
            f"<tr data-proposal-id=\"{pid}\"><td>{pid}</td><td>summary</td></tr>"
        )
    proposals_html = "\n".join(proposal_rows) if proposal_rows else "<tr><td colspan='2'>No proposals yet</td></tr>"
    interview_options = ['<option value="">Select session</option>']
    for session in interviews:
      sid = _html_escape(str(session.get("id", "")))
      label = _html_escape(f"{session.get('title', '')} ({session.get('turn_count', 0)} turns)")
      interview_options.append(f'<option value="{sid}">{label}</option>')
    interview_options_html = "\n".join(interview_options)

    msg_html = f"<div class='notice'>{_html_escape(message)}</div>" if message else ""

    template = r"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Agent Hub</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet"/>
  <style>
    :root {
      --bg: #0f1220;
      --panel: #171a2b;
      --panel-2: #1f2340;
      --accent: #6ee7ff;
      --accent-2: #a78bfa;
      --text: #f6f7fb;
      --muted: #b7bdd6;
      --border: #2a2f4a;
      --green: #2dd4bf;
      --orange: #fb923c;
    }
    * { box-sizing: border-box; }
    body {
      font-family: "Space Grotesk", sans-serif;
      margin: 0;
      color: var(--text);
      background: radial-gradient(1200px 800px at 10% 10%, #1f2340 0%, #0f1220 50%, #0b0d18 100%);
    }
    header {
      padding: 24px 28px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(135deg, #171a2b 0%, #13162a 100%);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .title { display: flex; align-items: center; gap: 12px; }
    .dot {
      width: 12px; height: 12px; border-radius: 999px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      box-shadow: 0 0 16px rgba(110,231,255,0.5);
    }
    main { padding: 24px 28px 40px; }
    .layout { display: grid; grid-template-columns: 1fr 360px; gap: 18px; align-items: start; }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    }
    .card h3 { margin: 0 0 12px 0; font-size: 18px; letter-spacing: 0.2px; }
    .muted { color: var(--muted); }
    label { display: block; margin-bottom: 6px; }
    input, select, textarea {
      width: 100%;
      background: var(--panel-2);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 10px 12px;
      border-radius: 10px;
      font-family: "Space Grotesk", sans-serif;
    }
    textarea { min-height: 110px; }
    .row { display: grid; grid-template-columns: 1fr; gap: 12px; }
    button {
      margin-top: 12px;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #0b0d18;
      border: none;
      padding: 10px 14px;
      border-radius: 10px;
      font-weight: 600;
      cursor: pointer;
    }
    pre {
      font-family: "IBM Plex Mono", monospace;
      background: #0e1222;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      white-space: pre-wrap;
    }
    .toolbar {
      display: flex; align-items: center; justify-content: space-between;
      gap: 10px; margin-bottom: 8px;
    }
    .toolbar .actions {
      display: flex; gap: 8px; flex-wrap: wrap;
    }
    .btn {
      background: #14182c; border: 1px solid var(--border); color: var(--text);
      padding: 6px 10px; border-radius: 8px; cursor: pointer; font-size: 12px;
    }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th, td { border-bottom: 1px solid var(--border); padding: 8px; text-align: left; }
    tr:hover { background: rgba(255,255,255,0.03); cursor: pointer; }
    .badges { display: flex; flex-wrap: wrap; gap: 8px; }
    .badge {
      display: inline-block; padding: 6px 10px;
      border: 1px solid var(--border); border-radius: 10px;
      background: #14182c; color: var(--muted);
    }
    .pill { display: inline-flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 999px; background: #14182c; border: 1px solid var(--border); user-select: none; }
    .top-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
    .stat { background: #14182c; border: 1px solid var(--border); border-radius: 12px; padding: 10px 12px; }
    .stat .label { color: var(--muted); font-size: 12px; }
    .stat .value { font-size: 18px; font-weight: 600; }
    .chat { display: grid; grid-template-rows: 1fr auto; gap: 12px; height: calc(100vh - 260px); }
    .messages { overflow-y: auto; padding-right: 8px; display: flex; flex-direction: column; gap: 12px; }
    .msg { padding: 14px 16px; border-radius: 14px; max-width: 78%; border: 1px solid var(--border); line-height: 1.5; font-size: 15px; }
    .msg.user { background: #1b2140; align-self: flex-end; }
    .msg.assistant { background: #14182c; align-self: flex-start; }
    .msg .meta { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    .msg .actions { margin-top: 8px; display: flex; gap: 8px; }
    .btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--muted); padding: 6px 8px; border-radius: 8px; cursor: pointer; }
    .input-bar { display: grid; grid-template-columns: 1fr 140px; gap: 10px; }
    .notice { padding: 10px 12px; border-radius: 10px; background: #1b2140; border: 1px solid var(--border); margin-bottom: 12px; }
    .jarvis-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 18px; }
    .jarvis-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .jarvis-status { min-height: 180px; }
  </style>
</head>
<body>
  <header>
    <div class="title">
      <div class="dot"></div>
      <div>
        <h1 style="margin:0;">Agent Hub</h1>
        <div class="muted">Local-first multi-agent console</div>
      </div>
    </div>
  </header>
  <main>
    __MSG_HTML__
    <div class="layout">
      <section class="card">
        <div class="top-stats">
          <div class="stat">
            <div class="label">Total runs</div>
            <div class="value">__TOTAL_RUNS__</div>
          </div>
          <div class="stat">
            <div class="label">Last run (raw)</div>
            <div class="value">__LAST_RUN__</div>
          </div>
          <div class="stat">
            <div class="label">Total tokens (last __RUN_COUNT__)</div>
            <div class="value">__TOTAL_TOKENS__</div>
          </div>
        </div>

        <div class="card" style="background:#14182c; margin-bottom:16px;">
          <div class="toolbar">
            <h3 style="margin:0;">Jarvis Lite Panel</h3>
            <div class="actions">
              <button id="jarvis-refresh" class="btn" type="button">Refresh State</button>
            </div>
          </div>
          <div class="jarvis-grid">
            <div>
              <label>New interview session</label>
              <div class="input-bar">
                <input id="jarvis-session-title" type="text" placeholder="Practice session title"/>
                <button id="jarvis-start-session" type="button">Start</button>
              </div>
              <label style="margin-top:12px;">Current session</label>
              <select id="jarvis-session-select">__INTERVIEW_OPTIONS__</select>
              <label style="margin-top:12px;">Role</label>
              <select id="jarvis-role-select">
                <option value="interviewer">interviewer</option>
                <option value="candidate">candidate</option>
              </select>
              <label style="margin-top:12px;">Transcript text</label>
              <textarea id="jarvis-turn-text" placeholder="Type the spoken turn here for now..."></textarea>
              <div class="jarvis-actions">
                <button id="jarvis-add-turn" type="button">Add Turn</button>
                <button id="jarvis-load-session" type="button" style="background:#2a2f4a;color:#fff;">Load Session</button>
              </div>
              <div class="muted" style="margin-top:8px;">Live microphone capture is available. Remote transcription is currently blocked by local TLS trust, so text capture is the reliable path today.</div>
              <div class="jarvis-actions" style="margin-top:12px;">
                <button id="jarvis-list-devices" type="button">Mic Devices</button>
                <button id="jarvis-record-audio" type="button">Record 3s WAV</button>
              </div>
            </div>
            <div>
              <label>Jarvis state</label>
              <pre id="jarvis-state" class="jarvis-status">Loading state...</pre>
              <label>Session details</label>
              <pre id="jarvis-session-output" class="jarvis-status">No session loaded.</pre>
            </div>
          </div>
        </div>

        <div class="row">
          <div>
            <label>Project path (optional)</label>
            <input id="project-path" type="text" placeholder="C:\\path\\to\\repo"/>
          </div>
        </div>

        <div class="chat" style="margin-top:12px;">
          <div class="messages" id="messages"></div>
          <div>
            <label>Message</label>
            <div class="input-bar">
              <textarea id="chat-input" placeholder="Ask anything..."></textarea>
              <div>
                <button id="send-btn" type="button">Send</button>
                <button id="clear-btn" type="button" style="margin-top:8px;background:#2a2f4a;color:#fff;">Clear</button>
              </div>
            </div>
            <div class="muted" style="margin-top:6px;">Tip: Ctrl+Enter to send. Auto agent selects the best specialist.</div>
          </div>
        </div>

        <div style="margin-top:12px;">
          <div class="toolbar">
            <h3 style="margin:0;">Run Details</h3>
            <div class="actions">
              <button id="toggle-view" class="btn" type="button">View: Summary</button>
              <button id="download-run" class="btn" type="button" disabled>Download JSON</button>
            </div>
          </div>
          <div class="muted" id="run-file-path">No run selected.</div>
          <pre id="run-details">Click a run to view details.</pre>
        </div>

        <div style="margin-top:18px;">
          <div class="toolbar">
            <h3 style="margin:0;">Proposal Details</h3>
            <div class="actions">
              <button id="proposal-view" class="btn" type="button">View: Summary</button>
              <button id="proposal-check" class="btn" type="button" disabled>Check Docs</button>
              <button id="proposal-apply" class="btn" type="button" disabled>Auto-Apply Docs</button>
              <button id="proposal-check-general" class="btn" type="button" disabled>Check General</button>
              <button id="proposal-apply-manual" class="btn" type="button" disabled>Apply (Manual)</button>
              <button id="proposal-approve" class="btn" type="button" disabled>Record Approval</button>
              <button id="download-proposal" class="btn" type="button" disabled>Download Patch</button>
            </div>
          </div>
          <div class="muted" id="proposal-file-path">No proposal selected.</div>
          <div class="muted" id="proposal-status"></div>
          <pre id="proposal-details">Click a proposal to view details.</pre>
        </div>
      </section>

      <aside class="card">
        <h3>Queue</h3>
        <div class="badges">
          <div class="badge">pending: __PENDING__</div>
          <div class="badge">processing: __PROCESSING__</div>
          <div class="badge">done: __DONE__</div>
          <div class="badge">failed: __FAILED__</div>
        </div>

        <h3 style="margin-top:18px;">Recent Runs</h3>
        <table id="runs-table">
          <thead><tr><th>Agent</th><th>Model</th><th>Tokens</th><th>Task</th></tr></thead>
          <tbody>
            __RUNS_ROWS__
          </tbody>
        </table>

        <h3 style="margin-top:18px;">Proposals</h3>
        <table id="proposals-table">
          <thead><tr><th>ID</th><th>Type</th></tr></thead>
          <tbody>
            __PROPOSALS_ROWS__
          </tbody>
        </table>
      </aside>
    </div>
  </main>
  <script>
    const rows = Array.from(document.querySelectorAll('#runs-table tbody tr'));
    const messagesEl = document.getElementById('messages');
    const inputEl = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const clearBtn = document.getElementById('clear-btn');
    const projectPath = document.getElementById('project-path');
    const runDetails = document.getElementById('run-details');
    const runFilePath = document.getElementById('run-file-path');
    const toggleView = document.getElementById('toggle-view');
    const downloadRun = document.getElementById('download-run');
    const proposalDetails = document.getElementById('proposal-details');
    const proposalFilePath = document.getElementById('proposal-file-path');
    const proposalView = document.getElementById('proposal-view');
    const downloadProposal = document.getElementById('download-proposal');
    const proposalCheck = document.getElementById('proposal-check');
    const proposalApply = document.getElementById('proposal-apply');
    const proposalCheckGeneral = document.getElementById('proposal-check-general');
    const proposalApplyManual = document.getElementById('proposal-apply-manual');
    const proposalApprove = document.getElementById('proposal-approve');
    const proposalStatus = document.getElementById('proposal-status');
    const proposalRows = Array.from(document.querySelectorAll('#proposals-table tbody tr'));
    const jarvisRefresh = document.getElementById('jarvis-refresh');
    const jarvisSessionTitle = document.getElementById('jarvis-session-title');
    const jarvisStartSession = document.getElementById('jarvis-start-session');
    const jarvisSessionSelect = document.getElementById('jarvis-session-select');
    const jarvisRoleSelect = document.getElementById('jarvis-role-select');
    const jarvisTurnText = document.getElementById('jarvis-turn-text');
    const jarvisAddTurn = document.getElementById('jarvis-add-turn');
    const jarvisLoadSession = document.getElementById('jarvis-load-session');
    const jarvisState = document.getElementById('jarvis-state');
    const jarvisSessionOutput = document.getElementById('jarvis-session-output');
    const jarvisListDevices = document.getElementById('jarvis-list-devices');
    const jarvisRecordAudio = document.getElementById('jarvis-record-audio');

    let selectedRun = null;
    let viewMode = 'summary';
    let selectedProposal = null;
    let proposalMode = 'summary';

    function loadMessages() {
      try { return JSON.parse(localStorage.getItem('agenthub_chat') || '[]'); } catch (e) { return []; }
    }

    function saveMessages(msgs) {
      localStorage.setItem('agenthub_chat', JSON.stringify(msgs));
    }

    function addMessage(role, content, meta) {
      const msgs = loadMessages();
      msgs.push({ role, content, meta: meta || {} });
      saveMessages(msgs);
      renderMessages();
    }

    function renderMessages() {
      const msgs = loadMessages();
      messagesEl.innerHTML = '';
      msgs.forEach((m) => {
        const div = document.createElement('div');
        div.className = 'msg ' + m.role;
        const meta = m.meta && m.meta.agent ? ('Agent: ' + m.meta.agent) : (m.role === 'user' ? 'You' : 'Assistant');
        const content = (m.content || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        div.innerHTML = '<div class="meta">' + meta + '</div>' + '<div>' + content + '</div>' +
          (m.role === 'assistant' ? '<div class="actions"><button class="btn-ghost copy-btn">Copy</button></div>' : '');
        messagesEl.appendChild(div);
        const btn = div.querySelector('.copy-btn');
        if (btn) { btn.addEventListener('click', () => navigator.clipboard.writeText(m.content || '')); }
      });
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function setLastAssistant(content, agent) {
      const msgs = loadMessages();
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i].content = content;
          msgs[i].meta = { agent: agent || 'auto' };
          break;
        }
      }
      saveMessages(msgs);
      renderMessages();
    }

    function streamText(text, agent) {
      let i = 0;
      const step = 24;
      const tick = () => {
        i = Math.min(text.length, i + step);
        setLastAssistant(text.slice(0, i), agent);
        if (i < text.length) {
          requestAnimationFrame(tick);
        }
      };
      tick();
    }

    function appendToLastAssistant(delta, agent) {
      const msgs = loadMessages();
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant') {
          msgs[i].content = (msgs[i].content || '') + delta;
          msgs[i].meta = { agent: agent || 'auto' };
          break;
        }
      }
      saveMessages(msgs);
      renderMessages();
    }

    async function sendMessage() {
      const msg = inputEl.value.trim();
      if (!msg) return;
      addMessage('user', msg);
      inputEl.value = '';
      const agent = 'auto';
      const history = loadMessages().slice(-10).map((m) => ({ role: m.role, content: m.content }));
      const payload = { message: msg, agent: agent, project: projectPath.value || null, history: history };
      addMessage('assistant', '', { agent: 'auto' });

      const resp = await fetch('/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!resp.ok || !resp.body) {
        const fallback = await fetch('/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!fallback.ok) {
          addMessage('assistant', 'Error: ' + fallback.statusText, { agent: 'system' });
          return;
        }
        const data = await fallback.json();
        const text = data.response || '(empty)';
        streamText(text, data.agent);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let currentAgent = 'auto';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const lines = part.split('\n');
          let event = 'message';
          let dataLine = '';
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            if (line.startsWith('data:')) dataLine += line.slice(5).trim();
          }
          if (event === 'meta') {
            try {
              const meta = JSON.parse(dataLine);
              currentAgent = meta.agent || currentAgent;
            } catch (e) {}
            continue;
          }
          if (event === 'done') continue;
          try {
            const payload = JSON.parse(dataLine);
            const delta = payload.delta || '';
            if (delta) appendToLastAssistant(delta, currentAgent);
          } catch (e) {}
        }
      }
    }

    function renderRunDetails(data) {
      if (!data) {
        runDetails.textContent = 'Click a run to view details.';
        runFilePath.textContent = 'No run selected.';
        downloadRun.disabled = true;
        return;
      }

      runFilePath.textContent = 'File: ' + (data._file || '');
      downloadRun.disabled = false;

      if (viewMode === 'raw') {
        runDetails.textContent = JSON.stringify(data, null, 2);
        return;
      }

      const lines = [
        'Agent: ' + (data.agent || ''),
        'Model: ' + (data.model || ''),
        'Tokens: input ' + (data.input_tokens ?? 'n/a') + ' | output ' + (data.output_tokens ?? 'n/a') + ' | total ' + (data.total_tokens ?? 'n/a'),
        'Task: ' + (data.task || ''),
        '',
        'Output:',
        data.response || '(empty)'
      ];
      runDetails.textContent = lines.join('\n');
    }

    rows.forEach((row) => {
      row.addEventListener('click', async () => {
        const file = row.getAttribute('data-run-file');
        if (!file) return;
        const resp = await fetch('/run?file=' + encodeURIComponent(file));
        if (resp.ok) {
          const data = await resp.json();
          data._file = file;
          selectedRun = data;
          renderRunDetails(selectedRun);
        }
      });
    });

    sendBtn.addEventListener('click', sendMessage);
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { sendMessage(); }
    });

    clearBtn.addEventListener('click', () => {
      localStorage.removeItem('agenthub_chat');
      renderMessages();
    });

    toggleView.addEventListener('click', () => {
      viewMode = viewMode === 'summary' ? 'raw' : 'summary';
      toggleView.textContent = 'View: ' + (viewMode === 'summary' ? 'Summary' : 'Raw JSON');
      renderRunDetails(selectedRun);
    });

    downloadRun.addEventListener('click', () => {
      if (!selectedRun || !selectedRun._file) return;
      const url = '/run/download?file=' + encodeURIComponent(selectedRun._file);
      window.open(url, '_blank');
    });

    function renderProposalDetails(data) {
      if (!data) {
        proposalDetails.textContent = 'Click a proposal to view details.';
      proposalFilePath.textContent = 'No proposal selected.';
      proposalStatus.textContent = '';
      downloadProposal.disabled = true;
      proposalCheck.disabled = true;
      proposalApply.disabled = true;
      proposalCheckGeneral.disabled = true;
      proposalApplyManual.disabled = true;
      proposalApprove.disabled = true;
      return;
    }
    proposalFilePath.textContent = 'ID: ' + (data.id || '');
    proposalStatus.textContent = '';
    downloadProposal.disabled = !data.patch;
    proposalCheck.disabled = !data.patch;
    proposalApply.disabled = !data.patch;
    proposalCheckGeneral.disabled = !data.patch;
    proposalApplyManual.disabled = !data.patch;
    proposalApprove.disabled = !data.patch;
    proposalDetails.textContent = proposalMode === 'summary' ? (data.summary || '') : (data.patch || '');
  }

    proposalRows.forEach((row) => {
      row.addEventListener('click', async () => {
        const pid = row.getAttribute('data-proposal-id');
        if (!pid) return;
        const resp = await fetch('/proposal?id=' + encodeURIComponent(pid));
        if (resp.ok) {
          const data = await resp.json();
          selectedProposal = data;
          renderProposalDetails(selectedProposal);
        }
      });
    });

    proposalView.addEventListener('click', () => {
      proposalMode = proposalMode === 'summary' ? 'patch' : 'summary';
      proposalView.textContent = 'View: ' + (proposalMode === 'summary' ? 'Summary' : 'Patch');
      renderProposalDetails(selectedProposal);
    });

    downloadProposal.addEventListener('click', () => {
      if (!selectedProposal || !selectedProposal.id) return;
      const url = '/proposal/download?id=' + encodeURIComponent(selectedProposal.id);
      window.open(url, '_blank');
    });

    proposalCheck.addEventListener('click', async () => {
      if (!selectedProposal || !selectedProposal.id) return;
      const resp = await fetch('/proposal/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedProposal.id, project: projectPath.value || null })
      });
      const data = await resp.json();
      proposalStatus.textContent = (data.ok ? 'OK: ' : 'FAIL: ') + (data.message || '');
    });

    proposalApply.addEventListener('click', async () => {
      if (!selectedProposal || !selectedProposal.id) return;
      const resp = await fetch('/proposal/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedProposal.id, project: projectPath.value || null })
      });
      const data = await resp.json();
      proposalStatus.textContent = (data.ok ? 'OK: ' : 'FAIL: ') + (data.message || '');
    });

    proposalCheckGeneral.addEventListener('click', async () => {
      if (!selectedProposal || !selectedProposal.id) return;
      const resp = await fetch('/proposal/check-general', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedProposal.id, project: projectPath.value || null })
      });
      const data = await resp.json();
      proposalStatus.textContent = (data.ok ? 'OK: ' : 'FAIL: ') + (data.message || '');
    });

    proposalApplyManual.addEventListener('click', async () => {
      if (!selectedProposal || !selectedProposal.id) return;
      if (!confirm('Apply this patch to the repo?')) return;
      const resp = await fetch('/proposal/apply-manual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedProposal.id, project: projectPath.value || null })
      });
      const data = await resp.json();
      proposalStatus.textContent = (data.ok ? 'OK: ' : 'FAIL: ') + (data.message || '');
    });

    proposalApprove.addEventListener('click', async () => {
      if (!selectedProposal || !selectedProposal.id) return;
      const note = prompt('Approval note (optional):') || '';
      const resp = await fetch('/proposal/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: selectedProposal.id, project: projectPath.value || null, note: note })
      });
      const data = await resp.json();
      proposalStatus.textContent = (data.ok ? 'OK: ' : 'FAIL: ') + (data.message || '');
    });

    async function refreshJarvisState() {
      const resp = await fetch('/jarvis/state');
      const data = await resp.json();
      jarvisState.textContent = JSON.stringify(data, null, 2);
      const sessions = data.sessions || [];
      const current = jarvisSessionSelect.value;
      jarvisSessionSelect.innerHTML = '<option value="">Select session</option>';
      sessions.forEach((session) => {
        const option = document.createElement('option');
        option.value = session.id;
        option.textContent = session.title + ' (' + session.turn_count + ' turns)';
        jarvisSessionSelect.appendChild(option);
      });
      if (current) jarvisSessionSelect.value = current;
    }

    async function loadJarvisSession() {
      const sessionId = jarvisSessionSelect.value;
      if (!sessionId) {
        jarvisSessionOutput.textContent = 'Select a session first.';
        return;
      }
      const resp = await fetch('/jarvis/session?session_id=' + encodeURIComponent(sessionId));
      const data = await resp.json();
      jarvisSessionOutput.textContent = JSON.stringify(data, null, 2);
    }

    jarvisRefresh.addEventListener('click', refreshJarvisState);

    jarvisStartSession.addEventListener('click', async () => {
      const title = jarvisSessionTitle.value.trim();
      if (!title) return;
      const resp = await fetch('/jarvis/session/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      });
      const data = await resp.json();
      jarvisSessionTitle.value = '';
      await refreshJarvisState();
      if (data.session_id) jarvisSessionSelect.value = data.session_id;
      jarvisSessionOutput.textContent = JSON.stringify(data, null, 2);
    });

    jarvisAddTurn.addEventListener('click', async () => {
      const sessionId = jarvisSessionSelect.value;
      const text = jarvisTurnText.value.trim();
      if (!sessionId || !text) return;
      const resp = await fetch('/jarvis/session/turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, role: jarvisRoleSelect.value, text })
      });
      const data = await resp.json();
      jarvisTurnText.value = '';
      await refreshJarvisState();
      jarvisSessionOutput.textContent = JSON.stringify(data, null, 2);
    });

    jarvisLoadSession.addEventListener('click', loadJarvisSession);

    jarvisListDevices.addEventListener('click', async () => {
      const resp = await fetch('/jarvis/mic/devices');
      const data = await resp.json();
      jarvisState.textContent = JSON.stringify(data, null, 2);
    });

    jarvisRecordAudio.addEventListener('click', async () => {
      jarvisSessionOutput.textContent = 'Recording 3 seconds...';
      const resp = await fetch('/jarvis/mic/record', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration: 3 })
      });
      const data = await resp.json();
      jarvisSessionOutput.textContent = JSON.stringify(data, null, 2);
    });

    renderMessages();
    refreshJarvisState();
  </script>
</body>
</html>
"""

    html = template
    html = html.replace("__MSG_HTML__", msg_html)
    html = html.replace("__RUNS_ROWS__", runs_html)
    html = html.replace("__PROPOSALS_ROWS__", proposals_html)
    html = html.replace("__PENDING__", str(counts.get("pending", 0)))
    html = html.replace("__PROCESSING__", str(counts.get("processing", 0)))
    html = html.replace("__DONE__", str(counts.get("done", 0)))
    html = html.replace("__FAILED__", str(counts.get("failed", 0)))
    html = html.replace("__TOTAL_RUNS__", str(stats.get("total_runs", 0)))
    html = html.replace("__LAST_RUN__", _html_escape(str(stats.get("last_run", ""))))
    html = html.replace("__RUN_COUNT__", str(len(runs)))
    html = html.replace("__TOTAL_TOKENS__", str(stats.get("total_tokens", 0)))
    html = html.replace("__INTERVIEW_OPTIONS__", interview_options_html)
    return html


@app.get("/", response_class=HTMLResponse)
def home():
    return _render_home()


@app.post("/run", response_class=HTMLResponse)
def run(agent: str = Form(...), task: str = Form(...), project: str | None = None):
    project_path = project or str(Path.cwd())
    runtime_result = maybe_execute_runtime_action(task, project_path, source="web.run", note=f"project={project_path}")
    if runtime_result.handled:
        return _render_home(message=runtime_result.message)
    agent_name = agent
    if agent_name == "auto":
        agent_name = pick_agent(task)
    profile = get_agent(agent_name)
    trace = start_trace(project_path, agent_name if agent_name != "auto" else None, source="web.run")
    with span(trace, "web.run", {"agent": agent_name}):
        if agent == "auto":
            record_handoff(trace, "auto", agent_name, "router.pick", task=task)
        run_task(task, profile, project_path, trace=trace, source="web.run")
    return _render_home(message=f"Ran with agent: {agent_name}")


@app.get("/run")
def run_detail(file: str):
    base = data_dir().resolve()
    target = (base / file).resolve()
    if not str(target).startswith(str(base)):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return JSONResponse({"error": "bad run data"}, status_code=400)
    return JSONResponse(data)


@app.get("/run/download")
def run_download(file: str):
    base = data_dir().resolve()
    target = (base / file).resolve()
    if not str(target).startswith(str(base)):
        return JSONResponse({"error": "invalid path"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        data = target.read_text(encoding="utf-8")
    except Exception:
        return JSONResponse({"error": "bad run data"}, status_code=400)
    return HTMLResponse(content=data, media_type="application/json")


@app.get("/proposal")
def proposal_detail(id: str):
    proposals_dir = data_dir() / "proposals"
    summary = proposals_dir / f"{id}_summary.md"
    patch = proposals_dir / f"{id}.patch"
    if not summary.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        summary_text = summary.read_text(encoding="utf-8")
    except Exception:
        summary_text = ""
    try:
        patch_text = patch.read_text(encoding="utf-8") if patch.exists() else ""
    except Exception:
        patch_text = ""
    return JSONResponse({"id": id, "summary": summary_text, "patch": patch_text})


@app.post("/proposal/check")
def proposal_check(payload: dict = Body(...)):
    proposal_id = str(payload.get("id", "")).strip()
    project = payload.get("project")
    project_path = project or str(Path.cwd())
    if not proposal_id:
        return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = check_docs_only(proposal_id, project_path)
    return JSONResponse({"ok": result.ok, "message": result.message})


@app.post("/proposal/check-general")
def proposal_check_general(payload: dict = Body(...)):
    proposal_id = str(payload.get("id", "")).strip()
    project = payload.get("project")
    project_path = project or str(Path.cwd())
    if not proposal_id:
        return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = apply_proposal(proposal_id, project_path, confirm=False)
    return JSONResponse({"ok": result.ok, "message": result.message})


@app.post("/proposal/apply-manual")
def proposal_apply_manual(payload: dict = Body(...)):
    proposal_id = str(payload.get("id", "")).strip()
    project = payload.get("project")
    project_path = project or str(Path.cwd())
    if not proposal_id:
        return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = apply_proposal(proposal_id, project_path, confirm=True)
    return JSONResponse({"ok": result.ok, "message": result.message})


@app.post("/proposal/approve")
def proposal_approve(payload: dict = Body(...)):
    proposal_id = str(payload.get("id", "")).strip()
    project = payload.get("project")
    note = payload.get("note") or None
    project_path = project or str(Path.cwd())
    if not proposal_id:
        return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = record_approval(proposal_id, project_path, note=note)
    return JSONResponse({"ok": result.ok, "message": result.message})


@app.post("/proposal/apply")
def proposal_apply(payload: dict = Body(...)):
    proposal_id = str(payload.get("id", "")).strip()
    project = payload.get("project")
    project_path = project or str(Path.cwd())
    if not proposal_id:
        return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = auto_apply_docs_only(proposal_id, project_path)
    return JSONResponse({"ok": result.ok, "message": result.message})


@app.get("/proposal/download")
def proposal_download(id: str):
    proposals_dir = data_dir() / "proposals"
    patch = proposals_dir / f"{id}.patch"
    if not patch.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    try:
        data = patch.read_text(encoding="utf-8")
    except Exception:
        return JSONResponse({"error": "bad patch"}, status_code=400)
    return HTMLResponse(content=data, media_type="text/plain")


@app.get("/jarvis/state")
def jarvis_state():
    listen = get_listen_state()
    mic = get_microphone_config()
    capture = get_capture_state()
    sessions = _load_interviews(limit=20)
    return JSONResponse(
        {
            "listen": {"enabled": listen.enabled, "mode": listen.mode},
            "microphone": {
                "device": mic.device,
                "sample_rate": mic.sample_rate,
                "chunk_ms": mic.chunk_ms,
                "mode": mic.mode,
            },
            "capture": {"active": capture.active, "provider": capture.provider, "mode": capture.mode},
            "sessions": sessions,
        }
    )


@app.post("/jarvis/session/start")
def jarvis_session_start(payload: dict = Body(...)):
    title = str(payload.get("title", "")).strip()
    if not title:
        return JSONResponse({"error": "missing title"}, status_code=400)
    session = create_session(title)
    return JSONResponse({"session_id": session.id, "created_at": session.created_at, "title": session.title})


@app.get("/jarvis/session")
def jarvis_session(session_id: str):
    try:
        session = load_session(session_id)
        summary = session_summary(session_id)
        coaching = coaching_summary(session_id)
    except FileNotFoundError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    return JSONResponse(
        {
            "id": session.id,
            "title": session.title,
            "turns": [
                {"role": turn.role, "text": turn.text, "question_type": turn.question_type} for turn in session.turns
            ],
            "summary": summary,
            "coaching": coaching,
        }
    )


@app.post("/jarvis/session/turn")
def jarvis_session_turn(payload: dict = Body(...)):
    session_id = str(payload.get("session_id", "")).strip()
    role = str(payload.get("role", "")).strip()
    text = str(payload.get("text", "")).strip()
    if not session_id or role not in {"interviewer", "candidate"} or not text:
        return JSONResponse({"error": "session_id, valid role, and text are required"}, status_code=400)
    try:
        session = add_turn(session_id, role, text)
        summary = session_summary(session_id)
        coaching = coaching_summary(session_id)
    except FileNotFoundError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)
    return JSONResponse(
        {"session_id": session.id, "turn_count": len(session.turns), "summary": summary, "coaching": coaching}
    )


@app.get("/jarvis/mic/devices")
def jarvis_mic_devices():
    try:
        devices = list_input_devices()
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "message": str(exc), "devices": []})
    return JSONResponse(
        {
            "ok": True,
            "devices": [
                {
                    "index": device.index,
                    "name": device.name,
                    "max_input_channels": device.max_input_channels,
                    "default_sample_rate": device.default_sample_rate,
                }
                for device in devices
            ],
        }
    )


@app.post("/jarvis/mic/record")
def jarvis_mic_record(payload: dict = Body(...)):
    duration = float(payload.get("duration", 3))
    try:
        path = record_microphone_clip(duration_s=duration)
    except RuntimeError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    return JSONResponse({"ok": True, "recording": str(path)})


@app.get("/runtime/approvals")
def runtime_approvals():
    payload = [item.__dict__ for item in list_pending_approvals()]
    return JSONResponse({"items": payload})


@app.post("/runtime/approvals/approve")
def runtime_approvals_approve(payload: dict = Body(...)):
    approval_id = str(payload.get("id", "")).strip()
    project = payload.get("project") or str(Path.cwd())
    profile = str(payload.get("profile", "personal")).strip() or "personal"
    note = str(payload.get("note", "")).strip()
    if not approval_id:
        return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = approve_runtime_action(approval_id, str(Path(project).resolve()), profile=profile, note=note)
    return JSONResponse({"ok": True, "message": result.message, "action": result.action})


@app.post("/runtime/approvals/reject")
def runtime_approvals_reject(payload: dict = Body(...)):
    approval_id = str(payload.get("id", "")).strip()
    note = str(payload.get("note", "")).strip()
    if not approval_id:
      return JSONResponse({"ok": False, "message": "missing id"}, status_code=400)
    result = reject_runtime_action(approval_id, note=note)
    return JSONResponse({"ok": True, "message": result.message, "action": result.action})


@app.post("/chat")
def chat(payload: dict = Body(...)):
    ok, msg = check_backend()
    if not ok:
        return JSONResponse({"error": f"backend check failed: {msg}"}, status_code=400)

    message = str(payload.get("message", "")).strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    agent = str(payload.get("agent", "auto"))
    project = payload.get("project")
    history = payload.get("history", [])
    project_path = project or str(Path.cwd())
    assistant_result = handle_assistant_core(
      message,
      project_path=project_path,
      backend_status="MODEL CORE // ONLINE",
      backend_detail=msg,
    )
    if assistant_result.handled:
      return JSONResponse({"agent": "assistant-core", "response": assistant_result.message, "intent": assistant_result.intent})
    runtime_result = maybe_execute_runtime_action(message, project_path, source="web.chat", note=f"project={project_path}")
    if runtime_result.handled:
      return JSONResponse({"agent": "runtime", "response": runtime_result.message, "action": runtime_result.action})

    trace = start_trace(project_path, agent if agent != "auto" else None, source="web.chat")
    with span(trace, "web.chat", {"agent": agent}):
        if agent == "auto":
            with span(trace, "router.pick", {"mode": "keyword"}):
                agent = pick_agent(message)
            record_handoff(trace, "auto", agent, "router.pick", task=message)
        ctx_lines = []
        if isinstance(history, list):
            for h in history[-10:]:
                role = str(h.get("role", "user"))
                content = str(h.get("content", ""))
                ctx_lines.append(f"{role}: {content}")
        if ctx_lines:
            combined = "Conversation so far:\n" + "\n".join(ctx_lines) + "\n\nCurrent user message:\n" + message
        else:
            combined = message

        output = run_task(combined, get_agent(agent), project_path, trace=trace, source="web.chat")
    return JSONResponse({"agent": agent, "response": output, "run_file": _latest_run_file(project_path)})


@app.post("/chat/stream")
def chat_stream(payload: dict = Body(...)):
    ok, msg = check_backend()
    if not ok:
        return JSONResponse({"error": f"backend check failed: {msg}"}, status_code=400)

    message = str(payload.get("message", "")).strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    agent = str(payload.get("agent", "auto"))
    project = payload.get("project")
    history = payload.get("history", [])
    project_path = project or str(Path.cwd())
    assistant_result = handle_assistant_core(
        message,
        project_path=project_path,
        backend_status="MODEL CORE // ONLINE",
        backend_detail=msg,
    )
    if assistant_result.handled:
      def assistant_event_stream():
        yield "event: meta\ndata: {\"agent\": \"assistant-core\"}\n\n"
        payload_json = json.dumps({"delta": assistant_result.message})
        yield f"data: {payload_json}\n\n"
        yield "event: done\ndata: {}\n\n"
      return StreamingResponse(assistant_event_stream(), media_type="text/event-stream")
    runtime_result = maybe_execute_runtime_action(message, project_path, source="web.chat.stream", note=f"project={project_path}")
    if runtime_result.handled:
      def runtime_event_stream():
        yield "event: meta\ndata: {\"agent\": \"runtime\"}\n\n"
        payload_json = json.dumps({"delta": runtime_result.message})
        yield f"data: {payload_json}\n\n"
        yield "event: done\ndata: {}\n\n"
      return StreamingResponse(runtime_event_stream(), media_type="text/event-stream")

    trace = start_trace(project_path, agent if agent != "auto" else None, source="web.chat.stream")
    with span(trace, "web.chat.stream", {"agent": agent}):
        if agent == "auto":
            with span(trace, "router.pick", {"mode": "keyword"}):
                agent = pick_agent(message)
            record_handoff(trace, "auto", agent, "router.pick", task=message)

    ctx_lines = []
    if isinstance(history, list):
        for h in history[-10:]:
            role = str(h.get("role", "user"))
            content = str(h.get("content", ""))
            ctx_lines.append(f"{role}: {content}")
    if ctx_lines:
        combined = "Conversation so far:\n" + "\n".join(ctx_lines) + "\n\nCurrent user message:\n" + message
    else:
        combined = message

    def event_stream():
        yield "event: meta\ndata: {\"agent\": \"%s\"}\n\n" % agent
        for chunk in stream_task(combined, get_agent(agent), project_path, trace=trace, source="web.chat.stream"):
            payload = json.dumps({"delta": chunk})
            yield f"data: {payload}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def start(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
