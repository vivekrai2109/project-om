# Naming Conventions

## Resource Naming
- Prefix: `ah` (Agent Hub)
- Environment: `dev`, `stg`, `prod`
- Region short code: `weu`, `eus`, `neu`, `sea`

Examples:
- `ah-prod-weu-gpu` (GPU VM)
- `ah-prod-weu-app` (Agent Hub service)
- `ah-prod-weu-logs` (storage)

## Code
- Python modules: `snake_case`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

## Files
- Docs: `UPPER_SNAKE_CASE.md` for design docs
- Config: `config.yaml`, `config.local.example.yaml`

