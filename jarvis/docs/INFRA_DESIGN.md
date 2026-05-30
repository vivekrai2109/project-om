# Infrastructure Design (Azure)

## Compute
- **Model Inference VM**: Azure GPU VM running vLLM + gpt-oss-20b.
- **Agent Hub Service**: Azure Container Apps or VM for orchestrator + web UI.
- **Worker**: same service or separate container for queue processing.

## Networking
- Public ingress for Web UI (optional).
- Private network between Agent Hub and GPU VM.
- TLS termination at ingress (reverse proxy).

## Storage
- Local disk for runs/memory (small-scale).
- Optional Azure Blob Storage for long-term logs.

## Observability
- Application logs (structured JSON).
- Metrics collection (Prometheus or Azure Monitor).

## Security
- API keys in Azure Key Vault.
- RBAC for VM and container access.
- Restrict inbound ports to UI and API.

