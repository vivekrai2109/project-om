# Owner Commands

## Runtime Control
- `start jarvis`
- `pause jarvis`
- `stop jarvis`
- `kill jarvis`
- `jarvis status`

## OMNIRA Backend Control
- `start omnira`
- `stop omnira`
- `restart omnira`
- `omnira status`

## Memory And Learning
- `privacy status`
- `disable memory`
- `enable memory`
- `stop training on my data`
- `start training on my data`
- `disable observation`
- `enable observation`
- `disable profile learning`
- `enable profile learning`
- `enable internet learning`
- `disable internet learning`

## Compute Mode
- `set compute mode to lean`: prefer smaller models and shorter responses for cheaper local execution
- `set compute mode to balanced`: use the default OMNIRA routing profile
- `set compute mode to performance`: prefer larger token budgets and stronger reasoning effort

## Model Pinning
- `pin model to omnira-reasoning-qwen-7b-v0.1`
- `use only model omnira-platform-qwen-7b-v0.1`
- `unpin model`
- `clear pinned model`

## Internet Learning Scope
- `set internet learning domains to finance, cloud and coding`
- `add internet learning domain legal`
- `remove internet learning domain legal`

## Readiness
- `learning readiness`
- `training readiness`
- `readiness status`

## Notes
- internet learning remains safe-domain only and owner-controlled
- profile learning is separate from generic observation capture
- compute mode now changes both model selection and token budget across commander, agent runs, and streaming