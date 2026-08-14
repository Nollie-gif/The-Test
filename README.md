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

## Public scope and independence

This repository documents reproducible research methods and sanitized findings only. It contains no raw research outputs or private operational data. The project is independent and is not affiliated with, endorsed by, or sponsored by any model provider.
## Repository map

- `RESEARCH_PROTOCOL.md` — research method, metrics, comparison rules, evidence hierarchy, and anti-bias rules.
- `REGISTRY.md` — central internal labeling/index system. Start here when locating research artifacts.
- `research/` — one Markdown record per durable research track/question (`RSH-###`).
- `experiments/` — one folder per controlled experiment (`EXP-###`).
- `datasets/observations/` — one Markdown record per atomic real/synthetic observation (`OBS-###`).
- `prototypes/` — implementation prototypes used by controlled variants.

## ID families

- `PRO-###` — protocol or methodology record.
- `RSH-###` — durable research track/question.
- `EXP-###` — controlled experiment inside one or more research tracks.
- `OBS-###` — atomic observation/evidence record.
- `PRT-###` — prototype/interface implementation.
- `RES-###` — synthesized result or conclusion derived from multiple observations/runs.

IDs are permanent. A file may be superseded or corrected, but IDs are never recycled.

## Evidence hierarchy

The normal relationship is:

`RSH → EXP → runs/results`

Observations are reusable evidence and can attach directly to the research track and, where applicable, to a specific experiment:

`OBS → RSH`, `OBS → EXP`, `OBS → RES`.

This prevents us from inventing experiments just to store an observation and lets naturally occurring regression cases become future test material.

## First experiment

`EXP-001` studies the Quicksave problem across different interaction environments: low-level agent orchestration, compact routing, and a deterministic single-action interface.

The first dataset begins with real Mission 10 incidents rather than invented benchmark data.
