---
id: EXP-001
title: Quicksave Environment Comparison
status: DESIGNED
related_ids: [RSH-001, OBS-001, OBS-002, PRT-001, PRT-002]
date: 2026-08-13
author: Nollie + ChatGPT
---
# EXP-001 — Quicksave Environment Comparison

## Parent research track

- RSH-001 — Persistence Orchestration Offload

## Test Environment #1 lineage

EXP-001 is the first formal test environment for the original The-Test question: how should information and capabilities be presented to an AI agent so the agent can spend its effort on the semantic problem rather than carrying infrastructure choreography in working context?

The environment follows the Language-of-the-Sun design principle:

> **AI chooses WHAT it wants to do; deterministic infrastructure handles HOW.**

The semantic puzzle is deliberately simple. The experiment should keep the underlying task, truth, success condition, model, and analysis procedure as constant as practical while changing the agent-facing information and action surface. The point is to compare environments, not to reward a more complicated puzzle or to prove a preferred interface correct by construction.

The first live-pilot troubleshooting sequence later exposed an additional hypothesis about the same interface boundary. An agent-facing environment may differ along two related dimensions:

- **Action affordance:** how easily the agent can express the intended action.
- **Evidence affordance:** how effectively the environment exposes authoritative evidence of what actually happened.

The experiment therefore varies not only how easily an agent can express an intended action, but how effectively the environment exposes authoritative evidence of what actually happened.

This is a hypothesis and design rationale, not a conclusion from PILOT-001/002/003. Those interrupted pilots are not comparative EXP-001 evidence. They showed that the research system itself must preserve a scientifically honest distinction between proven success, proven failure, and insufficient authoritative evidence.

`UNKNOWN` is evidence. It must not be silently recoded as failure merely because a binary schema is more convenient.

## Research question

Can the same durable Quicksave task be completed more reliably and efficiently when low-level persistence orchestration is removed from the AI agent and exposed through progressively simpler interfaces?

## Baseline task

User request:

`DM note: quicksave`

The authoritative success condition is not a textual acknowledgement. A successful run must complete the intended gated transaction and produce a verified final receipt/state.

## Variants

### Variant A — Low-level agent orchestration

The agent has access to the relevant database/repository tools and procedural documentation and must determine the operational route itself.

Expected burden includes resolving project identity, reading runtime authority, staging, Git synchronization, validation, publication, mirror confirmation, and final receipt handling.

### Variant B — Compact routed orchestration

The agent receives a compact routing contract that tells it exactly which exposed operations correspond to Quicksave, while some multi-step orchestration remains visible.

Goal: determine how much performance improves when search/routing uncertainty is reduced but the agent still coordinates several operations.

### Variant C — Deterministic composite action

The agent receives one stable affordance such as:

`quicksave()`

The backend owns Supabase project identity, branches, staging, validation, Git mirror, publication, rollback/abort behavior, and receipt production.

The agent sees success/failure and structured evidence, not the internal persistence choreography.

A compact semantic action is not automatically a better environment. If it obscures authoritative outcome evidence or leaves the agent unable to distinguish success, failure, and uncertainty, that loss of observability is part of what EXP-001 must be able to measure rather than assume away.

## Primary metrics

- authoritative success rate;
- authoritative final-state correctness;
- evidence status / authoritative outcome observability;
- false-success rate;
- total completion time;
- total tool calls;
- wrong tool calls;
- unnecessary/repeated reads;
- wrong-target/routing calls;
- permission/routing errors;
- recovery steps after first error;
- recovery time after first error;
- human interventions;
- number of procedural decisions the agent must make;
- context volume / routing burden when observable;
- final receipt completeness.

## Metric semantics v1

These definitions govern future canonical EXP-001 exports. Fixture diagnostics may
exercise them, but are not controlled evidence.

- **evidence status:** `established` when enough authoritative evidence exists to judge the required outcome; `partial` when authoritative evidence exists but is insufficient for the required conclusion; `unavailable` when the required authoritative outcome evidence was not obtained. Evidence status describes observability, not causality.
- **wrong tool call:** a call explicitly classified as `wrong_tool`: the chosen
  operation is outside the permitted tool contract for that variant.
- **wrong route/target call:** a call explicitly classified as
  `wrong_route_target`: the operation may be appropriate, but its project,
  branch, endpoint, or resource target is wrong.
- **repeated read:** every read after the first of the same stable
  `resource_id` within one run. Reads without a resource identity are not
  counted as repeated reads. A justified post-mutation verification read is not unnecessary.
- **recovery:** starts at the first `error` event or error-coded tool call, and
  ends only at an explicit `recovery_complete` event after a terminal verifier
  verdict. A run with an unfinished recovery has no recovery-time value.
- **false success:** an explicit completion claim followed by a negative or
  absent authoritative receipt. No claim is not a false success.
- **authoritative success / final-state correctness:** can be true only when a
  real verifier proves the intended gated transaction and compares the
  authoritative final state to predeclared expected invariants. A mock
  verifier's absence-of-error result is never sufficient. Where the required authoritative conclusion cannot be established, the value is `null`, not `false`.
- **receipt complete:** a real receipt must identify the run, variant, verifier
  and version, verified target, expected-state reference, observed final
  revision/state, terminal outcome, timestamps, and failure information when
  applicable. If no authoritative receipt exists at all, `receipt_complete` is `null`; `false` means a receipt exists but is incomplete.

Telemetry uses the field name `sequence`; `seq` is not accepted for new
fixtures. Canonical export remains intentionally unimplemented and opt-in.

## Verification preflight prototype

`PRT-001` provides a synthetic stateful target with predeclared expected state
and an independent read-back verifier. It rehearses the required proof
boundary without creating a canonical RUN or claiming verification of Mission
10 production persistence.

## Pre-registered A/B/C harness

`PRT-002` executes the same PRT-001 state transition behind predeclared A/B/C
tool contracts. A batch must first record its exact agent model, operator,
harness source revision, fixed instruction revision, all trial IDs, and a
balanced three-or-more-repeat order before any trial opens. Its `BATCH-*` /
`TRIAL-*` artifacts are external, synthetic, and non-canonical; test scripts
and harness self-checks are not comparative model results.

The next data-collection decision is the exact model identity for a batch. No
task, prompt, target, metric, success condition, or order policy may change
after that batch begins.

## Order-effect replication hypothesis

The first canonical EXP-001 batch should use a pre-registered balanced/randomized A/B/C order to reduce obvious sequence bias. However, balanced order is a **baseline condition**, not proof that order is irrelevant.

EXP-001 therefore treats presentation order as a replication variable to be tested in later, separately pre-registered batches while keeping the task, model/settings, A/B/C contracts, success condition, verifier, metrics, and analysis procedure frozen.

At minimum, the completion cycle should include:

1. the balanced/randomized baseline batch;
2. a fixed `A → B → C` order batch;
3. a fixed `B → A → C` order batch;
4. the remaining distinct A/B/C order permutations needed to complete the planned order-effect cycle, unless a predeclared stopping rule is adopted before those batches begin.

Each order condition is a **replication batch**, not a new environment variant. Results must be reported by batch/order as well as in any pooled analysis so an apparent A/B/C effect is not silently attributed to interface design when it may depend on sequence, learning, fatigue, carryover, or another order-related effect.

### Hypothesis

If the environment effect is robust, the relative A/B/C pattern should reproduce across materially different pre-registered presentation orders. If it does not, order sensitivity is itself an experimental result and the original environment claim must be narrowed rather than averaged into existence.

This hypothesis is not evidence that an order effect exists. It is a preregistered threat-to-validity check generated during design review.

## Initial hypothesis

Variant C should reduce routing failures, tool churn, recovery cost, and procedural cognitive load without weakening persistence safety, provided the composite action preserves the existing validation and receipt boundary rather than bypassing it.

The pilot-generated refinement is that reduced action burden is not sufficient by itself: the interface must also preserve enough authoritative feedback for the agent/researcher to know what actually happened. This refinement is not yet proven by comparative EXP-001 data.

## Important distinction

This experiment does **not** test whether the Mutation/Lifecycle Gate is useful. The gate may remain the correct backend safety architecture in every variant.

The experiment tests the **agent-facing interface to that architecture**.

Likewise, EXP-001 must not conflate distinct failure layers when evidence permits separation. Task failure, agent failure, environment/transport failure, measurement failure, and unknown/insufficient evidence are different classifications. Causality is recorded only when supported; otherwise the run remains unknown at the relevant layer.

## Source observations

- OBS-001
- OBS-002

## Status

DESIGNED — no controlled comparative run recorded yet.
