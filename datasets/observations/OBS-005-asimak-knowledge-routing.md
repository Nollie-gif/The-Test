# OBS-005 — Asimak Knowledge Ownership / Routing Error

## Evidence class

Real-play observation.

## Source system

Mission 10 NPC/hook continuity.

## Observation

During a Seatower scene, the agent initially allowed Gork to become the player-facing source for the Asimak lead.

A later targeted authority check showed that the active Asimak hook/lead belonged to Ravengard's knowledge/action path rather than Gork being the correct player-facing entry point.

The scene was locally corrected.

## Why this matters to The-Test

The underlying information existed, but the agent used the wrong **knowledge owner / reveal route**.

This is a different class of failure from missing memory. It tests whether the agent-facing representation preserves:

- who knows a fact;
- who may reveal it;
- whether knowledge is private, institutional, inferred, or player-facing;
- which durable hook owns the actionable lead.

## Candidate interface lesson

A future context packet should not merely return facts such as `Asimak exists`. It should encode the minimum useful provenance/authority needed for correct use, for example:

- `known_by`
- `reveal_authority`
- `player_facing_entry`
- `confidence / evidence`
- `related_hook`

The goal is not to dump more prose into context. It is to make the critical relationship machine-readable and immediately visible.

## Related records

- RSH-003
- PRO-001
- OBS-003
- OBS-007

## Research status

Historical source observation; candidate input for future context-packet experiments.
