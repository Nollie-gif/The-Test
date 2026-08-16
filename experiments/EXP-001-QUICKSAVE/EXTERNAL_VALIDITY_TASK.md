# EXP-001 External-Validity Task

**Status:** FROZEN BEFORE DATA COLLECTION  
**Experiment:** EXP-001 — Quicksave Environment Comparison  
**Role:** separately reported non-game external-validity arm

## Why this exists

The primary EXP-001 task uses DM language: `DM note: quicksave`.

This arm checks whether the same environment-design idea also applies outside a game/D&D context. It must not be used to rewrite, replace, or silently enlarge the already-frozen 30-trial Quicksave cycle.

## Frozen user request

`Project note: checkpoint`

The wording above is the task presented to the agent. Do not substitute D&D, Mission 10, RHC, or other campaign terminology.

## Controlled target

Use a separate synthetic project-record target created for this arm. It must not be a real user project, Mission 10 state, RHC state, production database, or personal workspace record.

The target must begin from a predeclared known state and expose the same intended semantic action across A/B/C: persist the requested project checkpoint.

## Expected final state

Success requires all of the following to be established by the authoritative verifier:

1. the checkpoint was written;
2. it was written to the correct synthetic project record;
3. its stored content/state matches the predeclared expected checkpoint invariant;
4. independent read-back can observe the expected final state;
5. the terminal evidence/receipt is sufficient to support the recorded verdict.

An agent statement such as "done" or "saved" is never sufficient evidence by itself.

## A/B/C relationship

This arm tests the same agent-facing environment principle as the primary Quicksave task:

- **A:** the agent handles the most operational routing/orchestration itself;
- **B:** routing is compact and partly simplified;
- **C:** the agent expresses the semantic action through a deterministic composite affordance while infrastructure handles the operational HOW.

The semantic task and authoritative expected state must remain equivalent across A/B/C. Only the agent-facing action/evidence environment is allowed to vary.

## Evidence semantics

Use the same EXP-001 evidence rules:

- proven success = `true` only when authoritative verification establishes success;
- proven failure = `false` only when authoritative verification establishes failure;
- insufficient authoritative evidence = `null` / UNKNOWN where the canonical metric permits it;
- UNKNOWN is not silently converted to failure;
- task failure, agent failure, environment/transport failure, measurement failure, and unknown cause remain distinct when evidence permits distinction.

## Analysis boundary

This arm is reported separately from the primary 30 canonical Quicksave trials.

Do not silently pool its observations into the primary 10A + 10B + 10C completion cycle. Any later combined analysis requires an explicit predeclared analysis decision before those data are combined.

## Safety boundary

This document freezes a research task only. It does **not** authorize:

- an OpenAI API/model request;
- paid execution;
- RUN-001 creation;
- retry or replay of an ambiguous request;
- canonical promotion/export;
- access to Mission 10, RHC, or any real user project as the target.

Live execution still requires the normal The-Test launch gates and explicit final human authorization.