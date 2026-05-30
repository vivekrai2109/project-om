# Ollama Runtime

Use this directory for local model packaging through Ollama.

- `Modelfile.omnira-platform` is the initial placeholder packaging spec.
- Pull a local Qwen model first, for example `ollama pull qwen2.5:7b`.
- Start the local runtime with `ollama serve`.
- Enable the provider in the API with `ENABLE_OLLAMA=true` and point `OLLAMA_BASE_URL` at the local Ollama endpoint.
- TODO: add packaging instructions for OMNIRA Lite and OMNIRA Code.
