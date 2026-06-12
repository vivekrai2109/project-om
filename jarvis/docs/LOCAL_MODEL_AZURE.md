# Azure Model

This guide is one self-hosted model-serving path for Jarvis. It assumes you want to run `gpt-oss-20b` on your own Azure GPU VM and expose it through an OpenAI-compatible API.

## Stack
- Azure GPU VM
- Docker plus NVIDIA Container Toolkit
- vLLM server
- Jarvis configured with `backend: local`

## Frontend
- no frontend dependency
- Jarvis desktop and web surfaces talk to the backend through the normal backend adapter

## Backend
- Azure VM with NVIDIA GPU and drivers
- CUDA runtime
- Docker runtime
- vLLM process listening on port `8000`

## Jarvis
- set `backend: local`
- point `base_url` to the self-hosted vLLM endpoint
- keep approvals, memory, and policy local to Jarvis

## Models
- base model: `gpt-oss-20b`
- serving layer: `vLLM`
- later path: fine-tuned variant for Jarvis workloads

## Setup

### 1. Create the VM
1. Create an Azure VM with an NVIDIA GPU such as A10, L4, or better.
2. Install NVIDIA drivers and CUDA.
3. Install Docker and NVIDIA Container Toolkit.

### 2. Run vLLM

```bash
docker pull vllm/vllm-openai:latest

docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model <path-or-hf-repo>/gpt-oss-20b \
  --host 0.0.0.0 --port 8000
```

Notes:
- Download the model weights from the relevant open model release source.
- Open-weight models are not served through the OpenAI API by default, so you host them yourself.

### 3. Configure Jarvis

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

## Check
- `agenthub list-agents` works
- `agenthub run` calls succeed against your VM
- Token usage appears in run logs

## Next
- Collect your own task data
- Fine-tune `gpt-oss-20b` with LoRA or QLoRA
- Add evals to enforce your preferred style

