# Hosting Plan

OMNIRA AI starts as a local-first development platform.

## MVP hosting

- FastAPI backend on local Docker Compose.
- Next.js frontend on local Docker Compose or direct Node.js runtime.
- PostgreSQL and Redis as local supporting services.
- Ollama as an optional next-step local model runtime.

## Future hosting

- vLLM for self-hosted OMNIRA models.
- Terraform-managed infrastructure for repeatable deployments.
- OpenTelemetry-backed observability and cost tracking.
- Optional provider adapters for cloud inference while keeping routing and orchestration provider-independent.
