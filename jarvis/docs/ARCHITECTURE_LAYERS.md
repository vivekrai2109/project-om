# Architecture (Layers)

Below is a layered view of the agentic application:

```mermaid
flowchart TB
  subgraph Clients
    UI[Web UI]
    CLI[CLI]
    API[HTTP API]
  end

  subgraph AppLayer[Application Layer]
    ORCH[Orchestrator]
    PLAN[Planner]
    ROUTE[Router]
    PERM[Tool Permissions]
  end

  subgraph Agents[Specialist Agents]
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

  subgraph Data[Data Layer]
    MEM[Project Memory]
    RUNS[Run Logs]
    QUEUE[Queue]
    REG[Tool Registry]
    MODELS[Model Registry]
  end

  subgraph Model[Model Backend]
    OPENAI[OpenAI API]
    VLLM[vLLM + gpt-oss-20b]
  end

  UI --> ORCH
  CLI --> ORCH
  API --> ORCH

  ORCH --> PLAN
  ORCH --> ROUTE
  ORCH --> PERM

  ROUTE --> Agents
  PLAN --> Agents

  ORCH --> MEM
  ORCH --> RUNS
  ORCH --> QUEUE
  PERM --> REG
  ORCH --> MODELS

  ORCH --> OPENAI
  ORCH --> VLLM
```

Notes:
- Orchestrator is the main control plane.
- Router selects agents automatically when needed.
- Planner produces multi-step task graphs.
- Model backend can be OpenAI or local vLLM.

