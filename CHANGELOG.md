# Changelog

Concise, human-facing history of meaningful changes to The-Test. This is
not a substitute for `REGISTRY.md` or the individual `RSH-###` / `EXP-###`
/ `OBS-###` / `PRT-###` records — those remain the durable, structured
research evidence. This file exists so a human or agent can scan what
changed to the *repository itself* (infrastructure, gates, tooling) without
reading every commit or every research record.

## 2026-08-21

- Added this file and `tools`-equivalent CI enforcement
  (`scripts/validate_change_ledger.py`, wired into
  `.github/workflows/research-validation.yml`): a pull request that touches
  `runner/`, `scripts/`, `.github/workflows/`, or `schemas/` must also touch
  this file, or a commit on the branch must carry a `Ledger-Exempt:`
  trailer. A separate, narrower rule requires `AGENT_HANDOFF.md` itself to
  be touched when the guarded-commit mechanics
  (`scripts/preflight_commit.py`, `scripts/install_preflight_hook.py`,
  `.githooks/pre-commit`, or a workflow file) change.
- Added RSH-004 (`research/RSH-004-agent-trust-boundary.md`) — see
  `REGISTRY.md` for the research record itself; noted here because it also
  changed CI-adjacent tooling posture (Actions pinned to commit SHAs).
- Pinned `actions/checkout` and `actions/setup-python` in
  `research-validation.yml` to commit SHAs instead of mutable version tags.
