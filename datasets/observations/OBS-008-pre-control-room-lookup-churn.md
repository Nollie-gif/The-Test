# OBS-008 — Pre-Control-Room Lookup Churn

## Evidence class

Real-play observation.

## Source system

Mission 10 gameplay before/around DM Control Room adoption.

## Observation

Normal scene play repeatedly triggered broad or redundant repository/tool lookups, even for small beats where the relevant authority had already been established.

The later DM Control Room rule explicitly tried to reduce this behavior by classifying requests, reading the smallest authoritative source, loading scene essentials once, and using targeted lookups only at meaningful boundaries.

## Why this matters to The-Test

This provides the negative-side companion to OBS-003. OBS-003 records the behavioral improvement after compact routing; OBS-008 records the lookup-pressure problem that motivated it.

## Candidate interface lesson

The agent-facing environment should make the minimal correct context easy to consume and should not require repeated navigation across large repositories merely to maintain confidence.

## Related records

- RSH-002
- OBS-003
- OBS-004

## Research status

Historical baseline observation; candidate input for retrieval/context-load experiments.
