# Changelog

Concise, human-facing history of meaningful changes to The-Test. This is
not a substitute for `REGISTRY.md` or the individual `RSH-###` / `EXP-###`
/ `OBS-###` / `PRT-###` records — those remain the durable, structured
research evidence. This file exists so a human or agent can scan what
changed to the *repository itself* (infrastructure, gates, tooling) without
reading every commit or every research record.

**Historical scope:** enforced and maintained from 2026-08-21 forward.
Earlier repository history was not reconstructed into retroactive entries
— treat anything before this date as "see Git history," not "see
CHANGELOG."

## 2026-08-21

- Added this file and CI enforcement (`scripts/validate_change_ledger.py`,
  wired into `.github/workflows/research-validation.yml`): a pull request
  that touches `runner/`, `scripts/`, `.github/workflows/`, or `schemas/`
  must also touch this file, or a commit on the branch must carry a
  `Ledger-Exempt:` trailer. A separate, narrower rule requires
  `AGENT_HANDOFF.md` itself to be touched when the guarded-commit
  mechanics specifically change (`scripts/preflight_commit.py`,
  `scripts/install_preflight_hook.py`, `.githooks/pre-commit`) —
  deliberately *not* any workflow-file edit, since this repository's one
  workflow file is a plain test runner with no routing/authority logic of
  its own, and requiring a handoff update for every CI-job addition would
  be bureaucracy without a real cold-start/authority change behind it.
- **Adversarial review follow-up, same day:** the mechanism above was
  attacked and found to have two real gaps, not theoretical ones —
  reproduced in isolated worktrees before being fixed:
  - A PR could edit `scripts/validate_change_ledger.py` to empty its own
    `LEDGER_DOMAINS`; running the script *as committed on that branch*
    graded the weakened copy's diff as clean.
  - Fixing that by having CI run the checker from `origin/main` was
    itself proven insufficient by re-testing: the trusted copy correctly
    requires the ledger, but a PR can legitimately exempt that
    requirement with a trailer and still merge its neutered file
    content, which then becomes the trusted copy for every future PR.
  - Closed with `check_committed_ledger_script_is_sane()`: an
    unconditional, non-exemptable check that reads the PR's own proposed
    version of the checker via `git show` (parsed with `ast`, never
    executed) and independently verifies it still has a sane
    `LEDGER_DOMAINS`.
- Added RSH-004 (`research/RSH-004-agent-trust-boundary.md`) — see
  `REGISTRY.md` for the research record itself; noted here because it also
  changed CI-adjacent tooling posture (Actions pinned to commit SHAs).
- Pinned `actions/checkout` and `actions/setup-python` in
  `research-validation.yml` to commit SHAs instead of mutable version tags.
