# Voice-Centric Operating Model

## Product Rule

Jarvis should feel like a spoken operator, not like a text console with a microphone button attached.

That means:
- voice is the primary control path
- visuals exist to confirm state, progress, approvals, and results
- keyboard input is a fallback, not the main interface contract

## User Experience Goal

The user should be able to say things like:
- search this repo for the auth failure path
- download the latest release artifact
- inspect why this build failed
- open the logs and summarize the error
- search the web for the package issue
- stage the fix, but ask before applying it
- manage this desktop task and tell me what happened

Jarvis should then:
- understand the spoken request
- route it to the right backend workflow
- execute bounded actions with approvals where needed
- speak back concise progress and outcomes
- show the important visuals without forcing the user into text-heavy interaction

## Capability Areas

### 1. Spoken Task Intake
- push-to-talk capture
- visible live listen mode
- transcript normalization
- intent routing into backend workflows

### 2. Operator Workflows
- repo search and code inspection
- web search and information gathering
- download and file retrieval workflows
- desktop and local-machine task handling
- error inspection, summary, and recovery guidance

### 3. Supervision
- explicit approval prompts for risky actions
- visible pending approval queue
- result history and audit trail

### 4. Visual Feedback
- assistant state: idle, listening, thinking, speaking, approval required, warning
- active session visibility
- approval and task status visibility
- compact summaries of what Jarvis is doing and what happened next

## UI Consequences

The desktop shell should emphasize:
- speak
- live listen
- approval actions
- result summaries
- session continuity

The desktop shell should de-emphasize:
- long-form manual typing
- dense operator panels that require reading everything
- dashboard-style controls that compete with the voice path

## Engineering Consequences

- the desktop shell must keep microphone capture and listen-state first-class
- voice capture should route into the same task/session pipeline as typed input
- all backend capabilities should be reachable from spoken requests
- desktop visuals should reflect what the backend is doing, not replace the backend logic itself

## Current Direction

Current implementation direction in this repo:
- `PySide6 + QML` cinematic shell as the production desktop path
- Python Jarvis core for routing, streaming, approvals, memory, sessions, and backend adapters
- OMNIRA remains the external model core behind the assistant shell

## Near-Term Gaps

- stronger voice-first shell layout with less emphasis on the text prompt
- richer spoken workflow support for search, download, and error handling tasks
- real audio-reactive visuals instead of mostly synthetic state animation
- pending approvals generated from actual risky operations instead of only manual staging