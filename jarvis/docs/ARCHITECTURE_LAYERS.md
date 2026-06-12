# Architecture (Layers)

Below is a layered view of the current Jarvis operator platform:

```mermaid
flowchart TB
  subgraph Experience
    DESKTOP[Desktop Shell]
    WEB[Local Web UI]
    CLI[CLI]
    VOICE[Voice Capture]
  end

  subgraph Control[Control Layer]
    ORCH[Jarvis Supervisor]
    PLAN[Planner]
    ROUTE[Router]
    APPROVAL[Approval Engine]
    POLICY[Policy Engine]
  end

  subgraph Runtime[Agent Hub Runtime]
    HANDOFF[Task Envelopes]
    CODER[Coder]
    INFRA[Infra]
    DOCS[Docs]
    MON[Monitor]
    QA[QA]
    SEC[Security]
    REL[Release]
    RES[Research]
    DATA[Data]
  end

  subgraph Trust[Trust and State]
    MEM[Project Memory]
    RUNS[Run Logs]
    QUEUE[Queue]
    REG[Tool Registry]
    MODELS[Model Registry]
    AUDIT[Audit Log]
    PROFILE[Profiles]
  end

  subgraph Models[Model Platform]
    LOCAL[Local or Self-Hosted Models]
    OMNIRA[OMNIRA Endpoint]
    EXT[External Fallback Models]
  end

  DESKTOP --> ORCH
  WEB --> ORCH
  CLI --> ORCH
  VOICE --> ORCH

  ORCH --> PLAN
  ORCH --> ROUTE
  ORCH --> APPROVAL
  ORCH --> POLICY
  ORCH --> HANDOFF

  HANDOFF --> CODER
  HANDOFF --> INFRA
  HANDOFF --> DOCS
  HANDOFF --> MON
  HANDOFF --> QA
  HANDOFF --> SEC
  HANDOFF --> REL
  HANDOFF --> RES
  HANDOFF --> DATA
  ROUTE --> HANDOFF
  PLAN --> HANDOFF

  ORCH --> MEM
  ORCH --> RUNS
  ORCH --> QUEUE
  POLICY --> REG
  ORCH --> MODELS
  ORCH --> AUDIT
  ORCH --> PROFILE

  ORCH --> LOCAL
  ORCH --> OMNIRA
  ORCH --> EXT
```

Notes:
- Jarvis Supervisor is the owner-facing control plane.
- Specialist work should flow through task envelopes instead of ad hoc prompt chaining.
- Policy and approvals are separate control points, not side effects hidden inside agents.
- Local or self-hosted models are the preferred default, with OMNIRA or external providers used as configured.

