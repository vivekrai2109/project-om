# Repo Policy (Stage C: Auto-Apply Docs Only)

This policy defines what the agents are allowed to do in Stage A. The goal is
safe observation and reporting with no automatic modifications.

## Allowed
- Read files for context
- Scan for TODOs, FIXMEs, and stale references
- Report issues, risks, and opportunities
- Propose patches and write diff files under `data/proposals/`
- Auto-apply **docs-only** patches for `.md/.txt/.rst` via `agenthub auto-apply-docs`
- Users may manually apply proposals via `agenthub apply-proposal --confirm`

## Not Allowed
- Auto-apply patches that touch non-doc files
- Modifying source files directly outside approved patches
- Running destructive commands
- Pushing commits or tags

## Review Cadence
- Agents should propose patches only.
- All changes must be reviewed and applied manually.

## Escalation
- If a risk is critical, raise it immediately with a clear fix proposal.

