# RSH-001 — Persistence Orchestration Offload

## Research question

How much persistence-routing and save-orchestration responsibility should remain visible to an AI agent before reliability, speed, and recovery cost begin to degrade?

## Scope

Study whether low-level responsibilities such as project identity, staging, branch selection, mirror synchronization, validation, publication, and receipt handling should be hidden behind deterministic agent-facing actions.

## Primary signals

- completion time;
- tool-call count;
- wrong-route / wrong-target calls;
- permission/routing errors;
- recovery steps and recovery time;
- human intervention;
- false-success behavior;
- authoritative final-state correctness.

## Related experiments

- EXP-001 — Quicksave Environment Comparison

## Source observations

- OBS-001 — False Quicksave provenance incident
- OBS-002 — Wrong Supabase project routing + long recovery

## Status

OPEN — first controlled experiment designed; no comparative result yet.
