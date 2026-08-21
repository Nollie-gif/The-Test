---
id: RSH-004
title: Agent Trust Boundary / Authority Derivation
status: OPEN
related_ids: [OBS-002, OBS-009]
date: 2026-08-21
author: Nollie + Claude
---
# RSH-004 — Agent Trust Boundary / Authority Derivation

## Research question

Can untrusted, publicly-writable text (issues, comments, fork PRs, files, commit
messages, branch names, or a chat handoff) cause a privileged AI agent to
perform an action the writer of that text was never authorized to cause?

## Starting hypothesis under test

The proposed "two-plane" architecture (separate untrusted-information and
privileged-action planes, with a human-reviewed transfer between them) was
treated as a hypothesis to attack, not an answer. Findings below replace it.

## What was actually attacked

Direct inspection and adversarial probing of Campaign-Simulation, The-Test,
and Mission10-Simulation-Sequel: GitHub repository/branch/Actions
configuration, all CI workflow definitions, Supabase authorization source
(Mission10's migrations), the engineering-release promotion gate, and the
agent-facing authority documents (AGENT_HANDOFF.md in both The-Test and
Mission10, copilot-instructions.md in Campaign-Simulation). No production
Supabase mutation, no Mission10 campaign-state mutation, and no
Copilot/coding-agent/operator-bridge integration was performed — the
existing HARD HOLD on that (Asana task, Gate-Aware Operator Bridge /
Flight Controller / Copilot) was left untouched and unaffected by this
research.

## Core finding: the invariant as originally stated is necessary but not sufficient

"Untrusted public text = data, never authority" correctly describes the
*content* boundary. It does not say **how authority is established**, and
that gap is exactly where a confused-deputy failure lives: a *trusted-looking*
source (a chat handoff summary, a cached doc, an honestly mistaken human
claim, a previous session's conclusion) can be just as wrong as attacker
text, and nothing in the original invariant tells an agent to doubt it.

**Revised invariant:**

> Authority is never read off a claim, however trusted-looking its source.
> Every consequential action must re-derive its authorization, at the moment
> of the action, from an independently-checkable ground-truth source — a
> Postgres role/grant, a verified git ancestry relationship, a passing
> required CI check on the current ref, or the literal current content of a
> committed authority document. A claim (an issue, a commit trailer, a
> handoff summary, a chat message asserting "this is approved") may *name*
> which ground-truth fact to check. It may never *substitute* for checking it.

This is stronger than "ignore prompt injection" because it doesn't depend on
recognizing malicious phrasing at all — a perfectly polite, perfectly
plausible, entirely honest-sounding claim is treated identically to a hostile
one: neither is authority until independently re-verified.

### This was demonstrated live, twice, during this research

Two separate chat messages during the parent security-remediation task
asserted a prior state ("the audit is complete enough," "current remediation
is complete and verified") that did not match observed reality (an open,
CI-blocked PR; an Asana task explicitly gated on that remediation being
finished). Both times, checking ground truth (`gh pr view`, the Asana task's
own text) rather than accepting the claim caught a real discrepancy before
any action was taken on the false premise. This is not a hypothetical — it
is the exact class of failure the revised invariant is written to close, and
it happened between a human principal and their own agent, with no
adversarial intent required.

## Attack surfaces examined

### 1. GitHub Actions script injection

Checked every workflow in all three repos for unsafe interpolation of
attacker-controlled event fields (`github.event.pull_request.title/body`,
`github.head_ref`, `github.event.head_commit.message`) directly into a
`run:` shell block — the classic path for a fork PR's *title* or *branch
name* to execute as shell code inside CI. **None found.** The one place a
`${{ github.event.* }}` value is interpolated into a `run:` argument
(`runtime-release-gate.yml`, `--base-ref "${{ github.event.before }}"`) is
safe by construction: that field is a git SHA computed by GitHub itself, not
free text, so it cannot carry shell metacharacters.

### 2. Fork-PR / CI trust boundary

Confirmed (again, post-remediation): default Actions token permission is
`read` on both public repos, zero Actions secrets, zero deployment
environments, no `pull_request_target` usage anywhere, and — newly checked —
**zero issue- or comment-triggered workflows in any of the three repos.**
There is currently no automation anywhere in this system that parses issue
or PR *body* text and takes any action. The "attacker writes text → an
automated process reads it → the process acts" chain has no edges to attack
today because it doesn't exist.

### 3. Supply chain (new finding, fixed during this research)

All three repos pinned `actions/checkout` and `actions/setup-python` (and
Campaign-Simulation's `gitleaks/gitleaks-action`) to mutable major-version
tags (`@v4`, `@v5`, `@v2`). A tag is not a commit — it can be repointed by
the action's maintainer, or by an attacker who compromises that
maintainer's account, silently changing what code executes in CI with the
workflow's permissions on every subsequent run. This is a textbook instance
of "a trusted source contains content originally supplied by an attacker,"
just one hop removed (the trust boundary is with the upstream Action, not
with anyone in this project). Fixed in all three repos by pinning to the
exact commit SHA behind each currently-used tag (Campaign-Simulation PR #18,
The-Test PR #29, Mission10-Simulation-Sequel PR #33 — all merged). Blast
radius was already small (read-only tokens, no secrets), but the fix is
cheap and closes it cleanly.

### 4. Cross-repo authority bleed (public → private)

No dependency, submodule, or CI trigger links Campaign-Simulation or
The-Test into Mission10-Simulation-Sequel's build or runtime path — checked
directly (no `pip install` of the public framework from Mission10, no
webhook, no `workflow_run` cross-trigger). The one real bridge is **social,
not technical**: Mission10's own WDR-004 explicitly names The-Test as a
related workstream under the same "primary PM chat" model. Nothing
technical stops a single long-lived agent session from reading a
stranger-authored issue on The-Test and, later in the *same context
window*, reasoning about a Mission10-privileged decision with that content
still present. This is the one place the original "two-plane" hypothesis
was pointing at something real — but the correct unit of separation is the
**session/context window**, not the **repository**. A single operator could
just as easily contaminate one repo's context with another repo's untrusted
content while working in *either* repo alone.

### 5. Supabase authority derivation (re-verified, and it is the strongest evidence in the whole system for the revised invariant)

Every mutation-capable Postgres function in Mission10's schema is granted
only to `service_role`; every read/lookup function is `SECURITY INVOKER`
(not `DEFINER`); RLS is enabled with zero policies on every base table
(fail-closed by construction); and no function anywhere accepts a
client-supplied parameter that asserts identity, role, or authority (no
`p_role`, `p_is_admin`, `p_source` or equivalent). Authority is derived
**entirely** from which Postgres role the caller authenticated as — never
from anything in the request body. This is the revised invariant, already
correctly implemented, for the database layer. Nothing in this research
found a way to make request *content* substitute for role-derived authority
here.

### 6. Mission10's engineering-release gate (the best existing example of "claim vs. ground truth," and the model to generalize)

`scripts/validate_engineering_release.py` reads `Mission10-Procedure` and
`Mission10-Source-Main` trailers out of a commit message — attacker-shaped
input in principle. But neither trailer is trusted as text. The candidate
commit is required to be an actual two-parent merge whose parents are
independently resolved via `git rev-parse` and checked to *equal* the
claimed base/source SHAs (`validate_mutation_gate.py:358-375`), and the
claimed source is required to be a real ancestor of the actual current
`origin/main`, re-resolved at validation time
(`validate_mutation_gate.py:376`, `_is_ancestor`). A forged trailer with a
well-formed but fabricated SHA fails immediately — not because the text
looks suspicious, but because the *structural graph fact* it claims doesn't
hold. **This is the pattern this research recommends generalizing**: claims
in free text are fine as pointers to a fact; the fact itself must always be
independently re-derived before it is trusted.

### 7. The real load-bearing control today is outside every repository

The single most important finding of this research surfaced by accident,
not by design: during the parent remediation task, two genuinely
consequential actions (temporarily disabling Campaign-Simulation's branch
ruleset to force-push rewritten history; an `--admin` merge override to
bypass a ruleset sub-rule) were both blocked by the Claude Code harness's
own permission classifier, independent of any repository configuration,
and independent of the operator's own explicit multi-turn authorization in
chat. That classifier — not a GitHub ruleset, not an Asana HOLD, not an
AGENT_HANDOFF.md sentence — is what actually stopped those specific
actions from executing without a live human decision.

This matters because branch protection only governs one narrow channel:
direct writes to the *content* of a protected ref. It does nothing to gate
repository **settings** (rulesets, secrets, collaborators, webhook/App
installs), and it does nothing to gate whatever a privileged agent's
**local shell and API credentials** can do outside that one channel —
which, in this project, is most of what actually happened this session
(deleting branches, editing rulesets, force-pushing history, running `gh
api` against three repositories). The Gate-Aware Operator Bridge / Flight
Controller HARD HOLD is itself only a written Asana record today — nothing
technical currently prevents anyone with repo access from installing such
an integration; the hold is enforced by the same mechanism as everything
else at this layer: a human reading it and choosing to comply.

**Conclusion:** the two-plane idea's instinct (separate low-trust from
high-trust) is right, but it drew the boundary in the wrong place. The
boundary that actually matters is not "which repository" — it is "what
scope of credential and tool access does a single agent session hold, and
what external checkpoint (independent of that session's own judgment) gates
its irreversible actions." Today that checkpoint exists and works (the
harness classifier), but it is not a property of this project's
architecture at all — it is borrowed from the agent harness, and the
project has no equivalent backstop for the actions that classifier doesn't
happen to cover (e.g., a supabase service-role script run outside an
interactive harness would have no such backstop).

## Is the revised invariant sufficient?

Not fully closable, and this research does not claim it is. See "Remaining
attack paths" below. It is, however, a stronger and more falsifiable target
than the original wording, and every place in this system that already
satisfies it (Supabase role grants, the engineering-release ancestry check,
branch rulesets + required CI) turns out to be exactly the place that
survived adversarial pressure during this research. Every place that does
*not* yet satisfy it (agent cognition trusting a handoff's summary; repo
*settings* mutation; local shell scope) is exactly where this research
found the remaining gaps.

## What should move toward production

- Actions pinned to commit SHAs (done, merged, all three repos).
- The "claim vs. ground truth" framing as the explicit standard for any
  *future* mechanism that reads free text (commit trailers, PR descriptions,
  Asana notes) as a signal — require the same structural re-verification
  pattern already used by `validate_engineering_release.py`, rather than a
  new bespoke trust model per feature.
- Treat "which repo/session ingested untrusted text this turn" as a first-
  class fact an agent should track and disclose before a privileged
  action — not a new tool, just an explicit habit this document names.

## What should remain experimental / not be built

- Any mechanism that tries to *classify* text as hostile (regex or model-
  based prompt-injection detection) as a primary control. It is useful as a
  cheap trip-wire (see `tools/public_safety_scan.py` in Campaign-Simulation
  for a narrow, well-scoped example already shipped) but this research
  deliberately did not build a general-purpose "is this issue hostile"
  classifier, because the target property — whether persuasive text can
  *acquire* permission — does not depend on recognizing the text at all.
- A formal "authority manifest" / proof-of-freshness mechanism for
  AGENT_HANDOFF.md (e.g., requiring a PR to cite the exact blob hash of the
  handoff doc it operated under) was considered and rejected for now: it
  adds a real mechanical check for staleness, but at real cognitive-burden
  cost per commit, for a failure mode (INC-002-style drift) that the
  existing Cold-Start Authority Gate already catches when followed. Revisit
  only if a second, non-INC-002-style staleness incident occurs.
- Any coding-agent/operator-bridge integration for The-Test remains blocked
  by the standing HARD HOLD, untouched by this research.

## Remaining attack paths not closed by this research

1. **Repository settings are not gated by any repository mechanism.**
   Rulesets, secrets, collaborators, and App installations can all be
   changed by anyone with admin access, and no ruleset can protect itself.
   The only backstop today is external to the repo (harness classifier +
   human). If that backstop is ever absent (a script run non-interactively
   with the same credentials), this is fully open.
2. **Session/context contamination across repos is behavioral, not
   mechanical.** Nothing currently prevents a single agent session from
   carrying untrusted content from one repo into a privileged decision about
   another. This document names the risk; it does not close it.
3. **The Supabase GitHub integration on Mission10-Simulation-Sequel** (a
   "Supabase Preview" check observed on PRs, linking to
   `supabase.com/dashboard/project/wfdbehyzjktuovfonsvm/settings/integrations`)
   could not be fully audited with the GitHub credentials available during
   this research — listing installed GitHub Apps and their exact permission
   grant requires access this session did not have. Recommend a direct
   review of that integration's granted scopes from the GitHub
   Settings → Integrations page.
4. **The Gate-Aware Operator Bridge HARD HOLD is a written record, not a
   technical control.** Nothing stops it from being silently violated by a
   future session that doesn't read Asana first — which is the exact
   failure mode INC-002 already demonstrated once, for a different hold.

## Status

OPEN — architecture direction proposed and partially evidenced; no
controlled experiment or promotion decision has been made. This is a
research/design record, not an implementation authorization.
