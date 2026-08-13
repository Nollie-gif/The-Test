# The-Test

Experimental research lab for AI-agent interaction architecture.

> **We are not testing which AI is smartest. We are testing which environment lets it behave smartest.**

## Research goal

The-Test studies how much operational and procedural burden can be removed from an AI agent so that the agent can spend more of its cognitive budget on semantic judgment, reasoning, narration, and task execution.

The core question is not only *what information should an agent have?* It is also:

- how should that information be presented;
- which decisions should be deterministic instead of remembered;
- which operations should be exposed as simple affordances/tools;
- how much repository/database machinery should remain invisible to the agent;
- which environment produces the lowest error rate, recovery cost, tool churn, and human intervention.

## Core hypothesis

A strong agent may behave substantially better when infrastructure behaves like a well-designed game interface: complex machinery remains below the surface while the agent receives compact state, clear actions, deterministic transitions, and explicit receipts.

The research lineage comes from real Mission 10 observations: operational bookkeeping moved away from conversational memory, save authority was converted from prose rules into executable gates, and the DM Control Room reduced unnecessary repository lookups by routing the agent toward the smallest authoritative source.

## Repository map

- `RESEARCH_PROTOCOL.md` — research method, metrics, comparison rules, and anti-bias rules.
- `REGISTRY.md` — central internal labeling/index system. Start here when locating research artifacts.
- `experiments/` — one folder per controlled experiment (`EXP-###`).
- `datasets/observations/` — one Markdown record per real or synthetic observation (`OBS-###`).
- `prototypes/` — implementation prototypes used by controlled variants.

## ID families

- `PRO-###` — protocol or methodology record.
- `EXP-###` — controlled experiment.
- `OBS-###` — atomic observation/evidence record.
- `PRT-###` — prototype/interface implementation.
- `RES-###` — synthesized result or conclusion derived from multiple observations.

IDs are permanent. A file may be superseded or corrected, but IDs are never recycled.

## First experiment

`EXP-001` studies the Quicksave problem across different interaction environments: low-level agent orchestration, compact routing, and a deterministic single-action interface.

The first dataset begins with real Mission 10 incidents rather than invented benchmark data.
