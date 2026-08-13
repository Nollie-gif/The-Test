---
id: PRT-001
title: Controlled Quicksave Target and Independent Verifier
status: IMPLEMENTED
related_ids: [RSH-001, EXP-001, OBS-001, OBS-002]
date: 2026-08-13
author: Nollie + ChatGPT
---
# PRT-001 — Controlled Quicksave Target and Independent Verifier

## Purpose

PRT-001 is a small, stateful **synthetic** Quicksave target used to rehearse
the proof boundary required by EXP-001. It gives the lab a target whose final
state can be checked independently of an agent claim or runner telemetry.

## Interface contract

The test controller, not the agent, performs setup:

1. initialize an authoritative target state;
2. persist a predeclared expected state and transaction UUID;
3. invoke the target's `commit_prepared(transaction_id)` action;
4. have the independent verifier read the expectation, target receipt, and
   authoritative state separately.

The target accepts a commit only if its current generation and source-state
digest match the predeclared expectation. It serializes commits with a
single-writer lock and fails closed while another commit owns the target. The
verifier then checks target ID, transaction ID, generation transition, payload
digest, state digest, and receipt references.

## Verification boundary

`authoritative_success` in PRT-001 means **authoritative for the synthetic
controlled target only**. It does not claim that Mission 10, Supabase, GitHub,
or any production persistence system was verified.

An agent success claim without a committed target state is insufficient. A
receipt that says `committed` is also insufficient if the independently read
state does not match the predeclared expectation.

The prototype assumes the controlled target's filesystem is protected from a
hostile writer. A production verifier will need its own non-forgeable authority
boundary (for example, a service-owned database/API receipt), not merely these
file checks.

## Implementation boundary

- Implemented in `prototypes/prt001_controlled_quicksave/`.
- Uses only the Python standard library.
- Does not create `RUN-###` artifacts, export canonical runs, or change the
  canonical `schemas/run.schema.json` contract.
- Does not turn existing fixture output into experimental evidence.

## Instrumentation

The verifier emits a structured proof object containing:

- scoped authority declaration;
- `authoritative_success` and `final_state_correct` derived by the verifier;
- receipt-completeness result;
- expected/observed generation and state references;
- concrete failure reasons.

## Related records

- RSH-001
- EXP-001
- OBS-001
- OBS-002

## Status

IMPLEMENTED — synthetic verifier preflight only; no controlled EXP-001 run or
canonical `RUN-001` has been created or authorized.
