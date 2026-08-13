# OBS-002 — Wrong Supabase Project Routing + Long Recovery

## Evidence class

Real-play observation.

## Source system

Mission 10 / WDR-002 Quicksave workflow.

## Observation

The agent attempted the correct first read operation:

`public.dm_runtime_read()`

but targeted the wrong/stale Supabase project reference:

`wzrqetssfojwzqblnlsz`

The connector returned:

`You do not have permission to perform this action`

The correct production Mission 10 project was later resolved as:

`wfdbehyzjktuovfonsvm`

After the initial routing failure, the complete recovery/save process took roughly 13 minutes.

The user identified this as the **second incident** in which a save-related error was followed by approximately 13 minutes of recovery work.

## Important distinction

The backend Mutation/Lifecycle Gate did not fail here. The failure occurred in the agent-facing routing layer before the intended procedure could proceed normally.

The system protected authoritative state, but the interaction cost was high.

## Qualitative agent signal

During recovery, the agent explicitly reminded itself that Quicksave means the complete gated save transaction rather than a convenient write labeled as a checkpoint. This suggests repeated procedural self-reconstruction even though the durable rule already existed.

User-facing diagnosis recorded during debugging:

> “μας ζάλισες.”

Humorous wording, useful signal: the workflow may be safe while still being ergonomically expensive for both agent and user.

## Candidate interface lesson

The runtime agent should ideally not know or select the production Supabase project ID at all. A stable higher-level operation should own target resolution and return a structured success/failure receipt.

## Metrics exposed by this incident

- wrong-target call: 1+
- permission/routing failure: yes
- human intervention: yes
- recovery duration: ~13 minutes
- false success: no on this incident; the agent correctly refused to report success until verified
- authoritative state protection: successful

## Related records

- EXP-001
- OBS-001

## Research status

Active source observation for controlled reproduction.
