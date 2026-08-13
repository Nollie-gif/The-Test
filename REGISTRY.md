# PRO-002 — Internal Research Registry / Labeling System

This file is the **arrangement map** for The-Test.

Its purpose is simple: keep the research navigable when the repository contains dozens or hundreds of experiments, observations, prototypes, and results.

## Rules

- Every durable research artifact receives a permanent typed ID.
- IDs are assigned sequentially inside their family.
- IDs are never reused.
- Every ID gets one short bullet here.
- Atomic observations receive their own `.md` file.
- Experiments may reference many observations; observations may later support many results.
- Keep registry descriptions deliberately short. Detail belongs in the linked file.
- New artifact type families require an explicit addition to this protocol before use.

## Label families

- `PRO-###` — protocol / methodology / repository organization.
- `EXP-###` — controlled experiment.
- `OBS-###` — atomic observation or evidence record.
- `PRT-###` — prototype or executable interface variant.
- `RES-###` — synthesized result/conclusion based on multiple observations or runs.

## Protocols

- **PRO-001 — Research Protocol** — Defines research question, metrics, comparison discipline, evidence classes, and anti-bias rules. → `RESEARCH_PROTOCOL.md`
- **PRO-002 — Internal Research Registry / Labeling System** — Defines IDs and keeps the compact reference map for all research artifacts. → `REGISTRY.md`

## Experiments

- **EXP-001 — Quicksave Environment Comparison** — Compare agent-driven low-level orchestration against compact routing and deterministic single-action save interfaces. → `experiments/EXP-001-QUICKSAVE/`

## Observations

- **OBS-001 — False Quicksave provenance incident** — A direct GitHub-side write was incorrectly labeled a Quicksave although the published generation had not advanced. → `datasets/observations/OBS-001-false-quicksave-provenance.md`
- **OBS-002 — Wrong Supabase project routing + ~13 minute recovery** — Correct `public.dm_runtime_read()` intent was sent to a stale/wrong Supabase project, returned permission denial, and recovery/save took roughly 13 minutes; this was the second similar long-recovery save incident. → `datasets/observations/OBS-002-wrong-project-routing-recovery.md`
- **OBS-003 — Control Room reduced lookup pressure** — Compact routing and smallest-authority guidance improved runtime flow by discouraging repository-wide rereads. → `datasets/observations/OBS-003-control-room-routing.md`
- **OBS-004 — Spontaneous Deception check after offload** — During Mission 10 play, the DM-agent independently called for a Deception roll, a behavior the user identified as a first after substantial temporal/operational knowledge had been offloaded. → `datasets/observations/OBS-004-spontaneous-check-after-offload.md`
- **OBS-005 — Exact NPC knowledge ownership error (Asimak)** — Gork was incorrectly used as the player-facing Asimak lead until a targeted authority check showed the hook belonged to Ravengard. → `datasets/observations/OBS-005-asimak-knowledge-routing.md`

## Prototypes

- None yet.

## Results

- None yet.

## Registry maintenance

When a new file is created:

1. assign the next ID;
2. create the detailed file;
3. add one short bullet here;
4. reference its source experiment/observation IDs inside the detailed file;
5. never renumber old records merely to make the index prettier.
