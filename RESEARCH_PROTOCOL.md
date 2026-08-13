# PRO-001 — Research Protocol

## Purpose

The-Test evaluates **agent-environment architecture**, not model prestige or subjective impressions.

Primary research question:

> Which interaction environment gives an AI agent the best prerequisites to act accurately, efficiently, safely, and with minimal cognitive/procedural overhead?

## Experimental principle

Hold the task as constant as practical. Change the environment/interface. Measure the outcome.

Examples of environment variables:

- raw/low-level SQL + repository access;
- compact routing instructions;
- precomputed context packets/materialized read models;
- deterministic composite tools such as `quicksave()`;
- read-only repository access during runtime;
- server-owned project IDs, branches, locks, and persistence routing;
- human UI and agent tools sharing the same backend functions.

## What we measure

For each run, capture at minimum:

- success / failure;
- authoritative final-state correctness;
- total completion time;
- total tool calls;
- wrong tool calls;
- unnecessary/repeated reads;
- wrong-route or wrong-target calls;
- permission/routing errors;
- recovery steps after first error;
- recovery time after first error;
- human interventions required;
- false-success declarations;
- failure stage;
- context volume / amount of context required when observable;
- context/routing burden when observable;
- qualitative agent behavior worth preserving as an observation.

The point of the metric set is to measure both **backend correctness** and **agent effort**. A run can be safe and still be ergonomically poor.

## Research hierarchy

The repository uses three linked evidence layers:

1. `RSH-###` — a durable research track/question. It defines the problem being studied and may exist before any controlled experiment.
2. `EXP-###` — a controlled experiment designed to test one or more hypotheses inside an `RSH` track.
3. `OBS-###` — an atomic observation/evidence record. An observation may predate an experiment and may later support multiple experiments or results.

Relationship model:

`RSH → EXP → runs/results`

while observations may connect across the structure:

`OBS → RSH`, `OBS → EXP`, and later `OBS → RES`.

Do not force every observation into an experiment merely to give it a home. The research track is the stable thematic anchor.

## Comparison discipline

1. Define the task and expected authoritative outcome before running variants.
2. Define variants before reviewing their results.
3. Do not change the success criteria because one variant performed poorly.
4. Repeat important tests. One successful run is evidence, not proof.
5. Prefer median/aggregate behavior over a memorable single run.
6. Preserve failed runs. Failure is data.
7. Separate **backend correctness** from **agent ergonomics**. A gate can work perfectly while the agent interface around it performs badly.
8. Separate **truth storage** from **memory interface**. A database may be authoritative while a precomputed context packet is the better agent-facing representation.

## Research source classes

- **Real-play observation:** arose organically during actual usage.
- **Controlled reproduction:** intentionally recreates an observed condition.
- **Synthetic test:** constructed only for experiment coverage.
- **Prototype benchmark:** compares alternative interfaces over an identical task.

Each atomic observation receives an `OBS-###` record.

## Anti-bias rule

Do not test which design we like best. Test which design produces better measurable behavior.

A prototype does not become preferred architecture because it is elegant, new, or ours.

## Research-to-build boundary

The experiment specification owns the hypothesis and metrics. A programmer agent implements the specified prototype without silently redefining the experiment.

Preferred pipeline:

`observation → research track → hypothesis → controlled variants → prototype → repeated runs → result synthesis → architecture decision`

## Initial research lineage

Mission 10 produced several useful prior patterns:

- deterministic infrastructure can carry operational continuity that otherwise depends on conversational memory;
- executable gates are stronger than prose rules for mutation safety;
- a user request such as Quicksave should not require the user or agent to remember branches, SQL helpers, lock tokens, or lifecycle coupling;
- the agent should read the smallest authoritative thing needed and avoid repository-wide lookup churn during normal play;
- a blocked persistence gate should not freeze unrelated semantic/narrative work.

These are starting observations and hypotheses, not conclusions for The-Test.
