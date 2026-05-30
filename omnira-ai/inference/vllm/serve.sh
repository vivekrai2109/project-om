#!/usr/bin/env bash

# TODO: replace the placeholder model path with a real exported OMNIRA model.
python -m vllm.entrypoints.openai.api_server \
  --model /models/omnira-platform-qwen-7b-v0.1 \
  --host 0.0.0.0 \
  --port 8001
