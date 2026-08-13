---
id: EXP-001
title: Quicksave Environment Comparison
status: DESIGNED
related_ids: [RSH-001, OBS-001, OBS-002]
date: 2026-08-13
author: Nollie + ChatGPT
---
# EXP-001 — Quicksave Environment Comparison

## Parent research track

- RSH-001 — Persistence Orchestration Offload

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

## Primary metrics

- authoritative success rate;
- authoritative final-state correctness;
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

## Initial hypothesis

Variant C should reduce routing failures, tool churn, recovery cost, and procedural cognitive load without weakening persistence safety, provided the composite action preserves the existing validation and receipt boundary rather than bypassing it.

## Important distinction

This experiment does **not** test whether the Mutation/Lifecycle Gate is useful. The gate may remain the correct backend safety architecture in every variant.

The experiment tests the **agent-facing interface to that architecture**.

## Source observations

- OBS-001
- OBS-002

## Status

DESIGNED — no controlled comparative run recorded yet.
