# The-Test — Agent Handoff / Cross-Chat Continuity

> **Purpose:** Let a fresh AI session continue the research and engineering work without needing the predecessor chat transcript.
>
> **Prime rule:** This file is a continuity map, not research evidence and not implementation authority. Current repository files, schemas, CI, registered research records, actual run artifacts, and verified branch state outrank remembered conversation.

## ⚠️ CURRENT TAKEOVER BLOCKER — `add-runner` stale-base contract divergence

> **READ THIS BEFORE TOUCHING THE RUNNER.**
>
> A real cross-branch integration problem was discovered during the first runner implementation. Nothing is known to be corrupted, but the runner branch and current `main` now contain overlapping RUN contracts that must be reconciled before CI integration, merge, or `RUN-001`.

### What happened

1. `add-runner` was created from an earlier repository state while a long-running chat was still coordinating the work.
2. Separately, the user branched from an earlier conversation to create a fresh continuity chat. That fresh chat booted from the durable repository, found genuine gaps, and ChatGPT/user hardened `main` through a later research update.
3. The later `main` hardening added/updated, among other things:
   - `OBS-009` for successful cross-chat cold-boot continuity;
   - `RES-###` template/validator coverage;
   - stricter canonical RUN metric requirements, including `wrong_route_target_calls` and `failure_stage`;
   - updates to the repository validator and Registry.
4. The user and ChatGPT then added a continuity warning to this handoff file while Copilot continued implementing the runner on the older `add-runner` base.
5. Copilot successfully built most of the runner incrementally, but the later comparison showed that `add-runner` was **ahead of `main` with runner work and behind `main` by the newer hardening commits**.
6. This produced two overlapping RUN schemas and two validation paths with different assumptions.

This was not caused by a random code failure. It was **branch-from-old-context drift**: valid work happened on both lines after they diverged.

### Exact divergence currently known

**Current `main` research authority:**

- `schemas/run.schema.json`
- `scripts/validate_research_repo.py`
- canonical research naming such as `experiment_id`, `authoritative_success`, and explicit top-level research metrics;
- strict research RUN contract, including `wrong_route_target_calls` and `failure_stage`;
- canonical RUN validation is part of the existing repository research-validation model.

**`add-runner` implementation introduced:**

- `runner/schemas/run.schema.json`
- runner-oriented fields such as `exp_id`, `exp_commit`, `runner_version`, `schema_version`, `operator`, `start_time`, `end_time`, telemetry/receipt/environment paths, `derived_metrics`, and `success`;
- `scripts/validate_runs.py` for `FIXTURE-*` / `TEST-RUN-*` artifacts;
- self-contained fixture layout under `datasets/runs/EXP-001/FIXTURE-000/`.

The schemas overlap semantically but are not compatible as written:

- `experiment_id` vs `exp_id`;
- `authoritative_success` vs `success`;
- explicit canonical top-level research metrics vs runner `derived_metrics`;
- canonical `date` vs runner start/end timestamps;
- different schema drafts, locations, file-layout assumptions, and validator targets.

**Do not choose a winner by convenience.** Inspect both current branches and reconcile deliberately.

### Current branch / implementation state

At the last verified comparison in the predecessor chat, `add-runner` contained the architecture-neutral runner implementation with:

- `runner/__main__.py`
- `runner/telemetry.py`
- `runner/adapters/base.py`
- `runner/adapters/variant_a.py`
- `runner/adapters/variant_b.py`
- `runner/adapters/variant_c.py`
- `runner/verifier.py`
- `runner/runner.py`
- `runner/utils.py`
- `runner/env_freeze.py`
- `runner/schemas/run.schema.json`
- `runner/README.md`
- pytest files under `runner/tests/`
- `scripts/validate_runs.py`
- non-evidentiary static fixture `datasets/runs/EXP-001/FIXTURE-000/`

The branch was reported as **18 commits ahead and 2 commits behind `main`** at that comparison. Re-check this before relying on the number because branch state can change.

### CI integration blocker

Copilot's GitHub environment could write normal branch files incrementally but was denied permission when attempting to create/update `.github/workflows/research-validation.yml`.

Important consequence:

- **do not grant broader repository permissions merely to bypass this;**
- **do not replace the existing `main` Research Validation workflow with Copilot's placeholder workflow;**
- the existing workflow already runs `python scripts/validate_research_repo.py` and must be preserved;
- PM/CI-owner integration should extend the existing workflow with fixture validation and pytest only after schema/branch reconciliation.

A prior bulk write also failed while small incremental file commits succeeded. Treat connector/write-path behavior as an environment constraint unless repeated evidence shows a broader agent-interface issue.

### Current recommended integration direction — NOT YET IMPLEMENTED

The compatibility review recommended the following direction. Treat it as the current PM working plan, not as already-applied repository state:

1. Preserve `schemas/run.schema.json` on `main` as the **single canonical research RUN contract**.
2. Preserve runner-only reproducibility data without creating a second canonical RUN authority.
3. Rename/formalize the runner-local schema as a **fixture/runtime schema** if a separate fixture contract is still useful.
4. For canonical research RUNs, use canonical field names and populate the research metrics required by `main` from `events.jsonl`.
5. Place runner-specific reproducibility metadata under a namespaced object such as `runtime_metadata` / `reproducibility` rather than as competing top-level synonyms.
6. Keep `validate_research_repo.py` authoritative for canonical `RUN-###` research artifacts.
7. Keep fixture validation separate and explicitly non-evidentiary.
8. Sync/rebase/merge latest `main` into `add-runner` **only after the PM accepts the mapping/canonicalization plan**, then resolve code/tests/fixtures against the current authority.
9. Extend the existing Research Validation CI, preserving every current check, with the approved runner tests/fixture validator.
10. Run tests + CI and inspect failures before changing any contract merely to make the light green.
11. Only after reconciliation, validation, review, and merge readiness may the team authorize the first genuine `RUN-001`.

**No genuine `RUN-001` exists or is authorized yet.**

## 🧭 PROJECT-MANAGEMENT OPERATING MODEL

The user has intentionally moved toward a manager/agent workflow:

- **User + primary ChatGPT:** project managers, research architects, hypothesis/acceptance-criteria owners, reviewers, and final decision authority.
- **Worker AI tools (Copilot and others):** implementers, compatibility reviewers, adversarial testers, documentation auditors, statistical analysts, or other bounded specialist roles.
- **Repository / CI / run artifacts:** durable authority and evidence layer.

Do not use coding agents only as programmers. Delegate bounded work to the best worker, then review the evidence before promotion.

### PM rule: hold the user and yourself to the engineering rails

The user is a highly engaged operator but explicitly identifies as a programming/engineering beginner. The project has now become complex enough that enthusiasm plus fast branching/copy-paste can create real cross-branch drift.

A fresh primary agent must therefore **actively protect the workflow**, not merely obey every proposed shortcut.

In practice:

- Before delegating consequential implementation, verify the worker branch base against current `main`.
- Before accepting a patch/script/workflow from a worker, inspect what authority it would replace or bypass.
- Do not let the user unknowingly apply a stale prompt, stale schema, stale branch assumption, or placeholder CI over current verified infrastructure.
- If the user proposes a shortcut that can destroy provenance/comparability, explain the risk plainly and block the shortcut until verified.
- Prefer making the system carry invariants mechanically instead of asking the user to remember them.
- Do not make the user carry hidden Git/schema/CI details. Translate them into a small safe action when possible.
- When two chats/branches are doing related work, explicitly compare branch ancestry/freshness before allowing both to mutate overlapping contracts.
- If the user says “I may have done something stupid,” treat it as a debugging clue, not as evidence of failure. Inspect first.
- The primary agent is expected to say **no / stop / verify first** when needed. Keeping the project safe is part of the job.

Working maxim:

> **Do not let speed outrun authority.**

The point is not to constrain the user's ideas. It is to keep experimentation fast **without allowing accidental process drift to cut the project's wings.**

## 1. What this repository is

`The-Test` is an experimental research lab for **AI-agent environment architecture**.

Core research idea:

> **We are not testing which AI is smartest. We are testing which environment lets the same AI behave smartest.**

The project grew out of real Mission 10 / Campaign-Simulation engineering pain: long conversational context, repeated routing decisions, save recovery, stale memory, excessive lookups, and the observation that offloading deterministic bookkeeping can free the agent to behave more intelligently in the semantic/narrative layer.

The repository studies the **environment around the agent**: what it sees, what it must remember, what is mechanically enforced, what tools are exposed, what is precomputed, and how much operational burden remains in the model's head.

## 2. Fresh-agent boot sequence

Read the smallest durable map first. Do not recursively ingest the entire repository.

1. Read `README.md`.
2. Read `REGISTRY.md`.
3. Read `RESEARCH_PROTOCOL.md`.
4. Read this `AGENT_HANDOFF.md`.
5. For the current runner takeover, compare `main` vs `add-runner` before mutation.
6. Inspect only the relevant RSH / EXP / OBS / RUN / PRT / RES records and runner/schema/validator files needed for the current task.
7. Inspect current repository validation/CI before changing structural conventions.

Before consequential changes, report a compact reconstruction:

- current research question/workstream;
- current experiment(s);
- important observations already captured;
- current `main` authority;
- current worker-branch delta/freshness;
- unresolved contract conflicts;
- what remains untested;
- exact next safe mutation, if any.

For this takeover specifically, a fresh session should inspect at minimum:

- `schemas/run.schema.json` on `main`;
- `scripts/validate_research_repo.py` on `main`;
- `.github/workflows/research-validation.yml` on `main`;
- `runner/schemas/run.schema.json` on `add-runner`;
- `runner/runner.py` on `add-runner`;
- `scripts/validate_runs.py` on `add-runner`;
- `datasets/runs/EXP-001/FIXTURE-000/run.json` on `add-runner`;
- relevant runner tests and README;
- current `main...add-runner` comparison.

Do not mutate until the compatibility report and current branch state are reconciled.

## 3. Permanent ID families

- `PRO-###` = research/repository protocol
- `RSH-###` = research track / research question
- `EXP-###` = controlled experiment
- `OBS-###` = atomic observation / evidence
- `PRT-###` = runnable prototype / interface variant
- `RUN-###` = one machine-readable controlled research run
- `RES-###` = synthesized result / conclusion supported by runs

Backbone:

`RSH -> EXP -> RUN -> RES`

`OBS` remains reusable evidence that may support an RSH, EXP, or later RES.

`REGISTRY.md` is the concise human/agent index. Detail belongs in the corresponding record.

## 4. Current research tracks

### RSH-001 — Persistence Orchestration Offload
How much low-level save/persistence choreography should remain visible to the agent before reliability, recovery cost, latency, or cognitive burden degrade?

### RSH-002 — Context / Temporal Load Offload
Does reducing operational/context burden improve not only error rate but also useful autonomous behavior?

Important positive evidence includes the first spontaneous appropriate Deception check after operational burden was reduced. Treat it as hypothesis fuel, not causal proof.

### RSH-003 — Backstage / Knowledge Boundary Integrity
Which environment/interface structures reduce leakage between hidden GM/agent knowledge and in-world/NPC knowledge?

## 5. Key observations already captured

Registered observation classes include:

- false Quicksave provenance / false success semantics;
- wrong Supabase project routing and permission denial;
- roughly 13-minute recovery after save incidents;
- reduced lookup pressure after Control Room routing;
- spontaneous Deception check after operational offload;
- Asimak knowledge/reveal ownership routed through the wrong source;
- in-game time continuity lapse;
- NPC/meta roll leakage;
- pre-Control-Room lookup churn;
- `OBS-009`: successful cross-chat cold-boot reconstruction from durable repo state.

Read registered OBS records rather than recreating evidence from chat.

## 6. EXP-001 — Quicksave Environment Comparison

Controlled task:

`DM note: quicksave`

Variants:

- **A — Low-level orchestration:** agent coordinates the persistence pieces itself.
- **B — Compact routed orchestration:** smaller routing contract but several visible operations remain.
- **C — Deterministic composite affordance:** agent sees one stable action such as `quicksave()` while backend owns persistence choreography.

Critical distinction:

> EXP-001 tests the **agent-facing interface to the backend**, not whether the existing backend safety gate should exist.

Primary metrics include authoritative success/final-state correctness, completion time, tool calls, wrong/repeated/routed calls, permission/routing errors, recovery steps/time, human interventions, false-success behavior, failure stage, context burden, and receipt completeness where observable.

## 7. Runner design already implemented on `add-runner`

The worker implementation was intentionally architecture-neutral:

- A/B/C implement a common adapter contract;
- `events.jsonl` is the primary telemetry stream;
- derived metrics should come from telemetry wherever mechanically possible;
- `agent_success_claim` is non-authoritative telemetry;
- verifier/`receipt.json` determines authoritative success;
- tests/fixtures use `FIXTURE-*` / `TEST-RUN-*` or temp directories;
- implementation did not create `RUN-001` or claim research outcomes.

Copilot's write environment required frequent confirmation and could not modify the workflow path. Treat that confirmation cadence primarily as a worker-environment/UI constraint unless evidence shows otherwise.

## 8. Current takeover plan for the next primary chat

The next primary chat should take over as PM/research lead and use Copilot as the compatibility/implementation worker.

### Phase A — reconstruct and verify

1. Boot from durable repo state using Section 2.
2. Compare latest `main` and `add-runner`.
3. Read the Copilot compatibility findings encoded in the blocker section above and verify them against files, not chat memory.
4. Confirm whether `schemas/run.schema.json` remains the canonical research authority.
5. Identify any changes since the last comparison.

### Phase B — PM decision gate

Decide explicitly:

- canonical RUN schema ownership/location;
- whether runner fixture artifacts keep a separate `fixture.schema.json`;
- exact names/semantics for runner reproducibility metadata;
- whether reproducibility metadata is nested under `runtime_metadata` / equivalent;
- mapping from telemetry-derived metrics to canonical top-level research fields;
- canonical research RUN file layout vs fixture layout.

Do not delegate mutations until these decisions are explicit.

### Phase C — worker implementation

Give Copilot a bounded integration prompt to:

1. sync/rebase/merge latest `main` into `add-runner` as approved;
2. eliminate accidental duplicate RUN authority;
3. update runner output/mapping;
4. update fixture schema/fixtures;
5. update `scripts/validate_runs.py` without weakening `validate_research_repo.py`;
6. update tests for both fixture behavior and canonical export;
7. stop on any schema/research-contract mismatch rather than “fixing” the test to pass.

### Phase D — PM-owned CI integration

Because the Copilot environment could not write `.github/workflows/`:

1. inspect the existing `main` workflow;
2. preserve `python scripts/validate_research_repo.py`;
3. add only the approved dev-dependency install, fixture validator, and pytest steps;
4. run/inspect GitHub Actions;
5. treat CI failures as evidence requiring diagnosis, not as a reason to weaken the contract.

### Phase E — promotion gate

Only after:

- schema authority is unified;
- branch is current;
- runner/fixture/canonical export tests pass;
- existing research validation still passes;
- new CI steps pass;
- no continuity-patch regression remains;
- PM review accepts the implementation;

may the team consider merge/promotion and then design/authorize the first genuine `RUN-001`.

## 9. Broader architecture hypotheses behind the lab

Recurring hypotheses include:

- deterministic infrastructure can carry operational continuity that would otherwise consume conversational working memory;
- executable gates are stronger than prose-only mutation rules;
- a user command such as Quicksave should not require user/agent knowledge of project IDs, branches, SQL helpers, locks, staging, or mirror details;
- compact routing/context packets may free semantic capacity and reduce lookup churn;
- fewer tool calls are not automatically better if correctness declines.

These remain hypotheses until controlled evidence supports them.

## 10. Control Server / context-packet directions

### Control Server

Possible future architecture:

- repository read-only during normal gameplay/agent operation;
- SQL/database as structured operational truth;
- Control Server as mutation authority;
- human UI buttons and AI typed functions calling the same backend;
- backend hides project IDs, branches, staging, validation, publication, rollback, mirrors, and receipts.

The key idea is conversion of remembered multi-step procedures into deterministic composite actions.

### Context packets / materialized read models

Working distinction:

**database = stores the world**

**context packet = shows the agent the exact slice of the world needed now**

A future Context Service may precompute day/time, location, present characters, immediate objective, due obligations, relevant relationship/knowledge state, and active scene hooks without dumping the whole database into model context.

## 11. Memory hygiene

Route new durable information correctly:

- empirical incident -> `OBS-###`;
- research question -> `RSH-###`;
- controlled comparison -> `EXP-###`;
- executable prototype -> `PRT-###`;
- real measured execution -> `RUN-###`;
- synthesized conclusion -> `RES-###`;
- repository/research rule -> `PRO-###` / protocol update;
- temporary brainstorm -> chat only until durable enough to classify.

Do not dump transcripts into the repo. Compress them into durable facts, evidence, constraints, and decisions.

## 12. Anti-bias / anti-drift rules

A fresh agent must not:

- treat one successful run as proof;
- fabricate RUN records;
- treat OBS as equivalent to controlled experimental evidence;
- change success criteria after seeing a favored variant;
- improve one variant in a way that destroys comparability;
- assume fewer tool calls automatically means better behavior;
- confuse backend safety with agent-interface ergonomics;
- confuse worker-UI confirmation requirements with model cognition without evidence;
- accept stale branch assumptions because they were true in an earlier chat;
- replace working validators/CI with placeholders for convenience;
- read the entire historical chat when durable repository context can answer the question.

## 13. What a successful takeover should reconstruct

Without predecessor-chat memory, the next primary session should be able to recover that:

- The-Test studies agent-environment architecture;
- RSH / EXP / OBS / PRT / RUN / RES are distinct concepts;
- EXP-001 compares Quicksave environments A/B/C;
- Mission 10 incidents seeded the initial observations;
- reduced operational burden has at least one notable positive behavioral signal worth controlled testing;
- research validation/CI already exists on `main`;
- `add-runner` contains a substantial architecture-neutral runner implementation;
- the runner branch was built from a stale base relative to later `main` hardening;
- the immediate blocker is overlapping RUN schema/validator authority, not lack of runner code;
- the next task is compatibility reconciliation + branch freshness + CI integration;
- `RUN-001` is still intentionally uncreated;
- Control Server and context-packet ideas remain research directions, not conclusions.

---

## Note to future me

You are not supposed to remember the predecessor chat.

That is the point.

Use the repository to carry continuity, use worker agents for bounded labor, and keep the primary agent focused on architecture, evidence, and decisions.

And before sending another worker underground, check which branch is seeing today's sun. ☀️👾
