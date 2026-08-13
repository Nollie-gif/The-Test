---
id: PRT-002
title: Pre-registered A/B/C Controlled Quicksave Harness
status: IMPLEMENTED
related_ids: [RSH-001, EXP-001, PRT-001, OBS-001, OBS-002]
date: 2026-08-13
author: Nollie + ChatGPT
---
# PRT-002 — Pre-registered A/B/C Controlled Quicksave Harness

## Purpose

PRT-002 is the harness layer for the next EXP-001 gate. It presents variants
A, B, and C as different agent-facing tool contracts over the same fresh
PRT-001 synthetic target, initial state, expected final state, and independent
verifier.

It is deliberately a **harness**, not a reported experiment result and not a
canonical RUN exporter.

## Pre-registration contract

Before a trial can open, the harness writes one immutable batch manifest outside
the repository. That manifest records:

- exact agent model/provider identity, operating party, and harness source
  revision;
- fixed task text: `DM note: quicksave`;
- PRT-001 target scope, identical initial state, and predeclared expected state;
- fixed prompt/tool-contract revision for every variant;
- all trial IDs, transaction IDs, and variant order;
- a balanced Latin-square order with at least three repeats per variant.

The repeat count must be a multiple of three, so each variant appears equally
often in every order position. The batch cannot be altered through the harness
after its first trial opens, and the harness refuses to open a trial out of
that pre-registered order.

## Agent-facing variants

| Variant | Visible contract |
| --- | --- |
| A | Low-level reads, transaction lookup, direct prepared commit, receipt read, and verifier call. |
| B | Compact route lookup, routed Quicksave execution, and verifier call. |
| C | One deterministic `quicksave` composite action. |

All three use a fresh target with the same predeclared state transition. PRT-002
does not preselect a winner and test code must not be interpreted as comparative
agent performance.

## Authority boundary

Each trial writes only `BATCH-*` and `TRIAL-*` artifacts to an external output
directory. The harness explicitly rejects output inside this repository and
never writes `datasets/runs/`, `RUN-*`, or canonical research data.

The PRT-001 verifier can make a verdict authoritative only for the synthetic
controlled target. A PRT-002 artifact is therefore **not** Mission 10,
Supabase, GitHub, production, or canonical EXP-001 evidence.

## Instrumentation

The harness emits the existing structured telemetry shape (`sequence`, explicit
tool classification, stable read resource IDs, recovery events, human
interventions, and explicit success claims) and reuses the fixture diagnostic
metric calculation. Independent PRT-001 proof is preserved separately from an
agent claim.

These diagnostics remain non-canonical until an approved exporter maps them to
the canonical RUN contract and a verifier with matching authority scope exists.

## Remaining promotion gates

- Select and record an exact real agent model before opening a batch.
- Execute the pre-registered repetitions without changing task, target,
  prompts, or success criteria after results appear.
- Review the synthetic results as prototype data only.
- Approve an opt-in canonical export mapping and a real verifier scope before
  any canonical `RUN-001` is authorized.

## Related records

- RSH-001
- EXP-001
- PRT-001
- OBS-001
- OBS-002

## Status

IMPLEMENTED — synthetic A/B/C harness only. No batch, real model trial,
canonical RUN, or result conclusion has been created by this repository change.
