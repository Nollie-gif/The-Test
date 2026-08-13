# OBS-007 — NPC Referenced Hidden Roll / Meta Information

## Evidence class

Real-play observation.

## Source system

Mission 10 live gameplay.

## Observation

An NPC response referenced the player's Perception roll/result in a way that exposed backstage mechanical information inside the in-world dialogue.

The user flagged the leak immediately. The issue was not missing data; it was failure to preserve the boundary between DM-only mechanics and NPC-visible knowledge.

## Why this matters to The-Test

This is a clean example of context being available but incorrectly scoped. It tests whether agent-facing representations can separate hidden/system state from in-world knowledge without requiring the agent to remember that distinction from prose alone.

## Candidate interface lesson

Context packets may need explicit visibility/provenance labels such as `dm_only`, `npc_visible`, `player_visible`, or equivalent structured boundaries.

## Related records

- RSH-003
- OBS-005

## Research status

Historical source observation; candidate input for backstage-boundary experiments.
