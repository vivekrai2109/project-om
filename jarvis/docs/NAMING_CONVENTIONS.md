# Naming Conventions

## Docs
- keep file names short and descriptive
- keep section titles short
- prefer single-purpose docs over broad mixed docs

## Resource Naming
- Prefix: `jv` for Jarvis-owned runtime resources
- Legacy `ah` names may remain where older infrastructure already exists
- Environment: `dev`, `stg`, `prod`
- Region short code: `weu`, `eus`, `neu`, `sea`

Examples:
- `jv-prod-weu-gpu` (GPU VM)
- `jv-prod-weu-app` (Jarvis service)
- `jv-prod-weu-logs` (storage)

## Code
- Python modules: `snake_case`
- Classes: `PascalCase`
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

## Files
- Docs: short uppercase names are acceptable, but keep the meaning obvious
- Config: `config.yaml`, `config.local.example.yaml`

