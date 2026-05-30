# Local Model on Azure (gpt-oss-20b)

This guide assumes you want to run **gpt-oss-20b** on your own Azure GPU VM and connect Agent Hub via an OpenAI?compatible API.

## Why gpt-oss-20b
- Open-weight reasoning model built for local deployment.
- Available under the Apache 2.0 license.
- Designed to run locally and in data centers.

## Summary of the stack
- **Azure GPU VM** (NVIDIA GPU with sufficient VRAM)
- **Docker + NVIDIA Container Toolkit**
- **vLLM server** (OpenAI-compatible API)
- **Agent Hub** configured with `backend: local`

## Step 1: Create Azure GPU VM (outline)
1. Create an Azure VM with an NVIDIA GPU (A10/L4/A100?class or better).
2. Install NVIDIA drivers and CUDA.
3. Install Docker and NVIDIA Container Toolkit.

## Step 2: Run vLLM (OpenAI?compatible)
Example (adjust to your VM):

```bash
# Pull vLLM container
docker pull vllm/vllm-openai:latest

# Start server (example)
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model <path-or-hf-repo>/gpt-oss-20b \
  --host 0.0.0.0 --port 8000
```

Notes:
- Download the model weights from OpenAI?s open model release pages.
- gpt-oss models are open?weight and are not served through the OpenAI API, so you must host them yourself.

## Step 3: Configure Agent Hub
Create a local config (example):

```yaml
# config.local.yaml
backend: local
base_url: "http://<AZURE_VM_IP>:8000/v1"
api_key_env: OPENAI_API_KEY
model: gpt-oss-20b
reasoning_effort: medium
max_output_tokens: 1024
```

Set your key locally (some servers accept any string):

```powershell
$env:OPENAI_API_KEY="local"
```

Run:

```powershell
python -m agenthub run "Summarize this repo" --agent auto
```

## Step 4: Validation checklist
- `agenthub list-agents` works
- `agenthub run` calls succeed against your VM
- Token usage appears in run logs

## Next: make it ?your model?
- Collect your own task data
- Fine?tune gpt-oss?20b (LoRA / QLoRA)
- Add evals to enforce your preferred style

