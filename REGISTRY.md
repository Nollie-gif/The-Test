# PRO-002 — Internal Research Registry / Labeling System

This file is the **arrangement map** for The-Test.

Its purpose is simple: keep the research navigable when the repository contains dozens or hundreds of research tracks, experiments, observations, prototypes, runs, and results.

## Rules

- Every durable research artifact receives a permanent typed ID.
- IDs are assigned sequentially inside their family.
- IDs are never reused.
- Every durable research record gets one short bullet here.
- Atomic observations receive their own `.md` file.
- Research tracks receive their own `.md` file and act as the stable thematic anchor.
- Experiments live inside research tracks conceptually, but keep their own `EXP-###` identity because multiple experiments may test the same research question.
- Observations may predate experiments and may support multiple experiments/results.
- Controlled runs receive machine-readable `RUN-###` artifacts; runs are evidence instances, not long-form Registry entries by default.
- Keep registry descriptions deliberately short. Detail belongs in the linked file.
- New artifact type families require an explicit addition to this protocol before use.

## Label families

- `PRO-###` — protocol / methodology / repository organization.
- `RSH-###` — durable research track / research question.
- `EXP-###` — controlled experiment testing a research track.
- `OBS-###` — atomic observation or evidence record.
- `PRT-###` — prototype or executable interface variant.
- `RUN-###` — one machine-readable controlled run of an experiment.
- `RES-###` — synthesized result/conclusion based on multiple observations or runs.

`RUN-000` is permanently reserved for the example fixture and is never evidence.

## Primary tracking structure

The two main long-lived indexes are:

1. **Research tracks (`RSH-###`)** — what problem/question are we studying?
2. **Observations (`OBS-###`)** — what actually happened / what evidence do we have?

Controlled experiments (`EXP-###`) connect the two by deliberately testing hypotheses inside a research track.

Relationship model:

`RSH → EXP → RUN → RES`

with reusable evidence links:

`OBS → RSH`, `OBS → EXP`, `OBS → RES`.

## Structured metadata rule

Durable `RSH`, `EXP`, `OBS`, `PRT`, and `RES` Markdown records carry minimal YAML frontmatter:

- `id`
- `title`
- `status`
- `related_ids`
- `date`
- `author`

Use the matching file under `templates/` when creating a new record. Do not hand-invent a new metadata shape for one file.

## Protocols

- **PRO-001 — Research Protocol** — Defines research question, metrics, comparison discipline, evidence hierarchy, machine-readable run policy, and anti-bias rules. → `RESEARCH_PROTOCOL.md`
- **PRO-002 — Internal Research Registry / Labeling System** — Defines IDs and keeps the compact reference map for all research artifacts. → `REGISTRY.md`

## Research Tracks

- **RSH-001 — Persistence Orchestration Offload** — Tests how much low-level save/routing machinery should be hidden from the agent. → `research/RSH-001-persistence-orchestration-offload.md`
- **RSH-002 — Context / Temporal Load Offload** — Tests whether compact runtime context and reduced lookup burden improve continuity and semantic initiative. → `research/RSH-002-context-temporal-load.md`
- **RSH-003 — Backstage / Knowledge Boundary Integrity** — Tests how structured context can preserve knowledge ownership, reveal authority, and hidden/system boundaries. → `research/RSH-003-backstage-knowledge-boundaries.md`
- **RSH-004 — Agent Trust Boundary / Authority Derivation** — Adversarial study of whether untrusted public text can acquire operational authority; proposes "claim vs. ground-truth re-derivation" in place of the two-plane hypothesis. → `research/RSH-004-agent-trust-boundary.md`

## Experiments

- **EXP-001 — Quicksave Environment Comparison** — Under RSH-001; compare low-level orchestration against compact routing and deterministic single-action save interfaces. → `experiments/EXP-001-QUICKSAVE/`

## Observations

- **OBS-001 — False Quicksave provenance incident** — RSH-001 / EXP-001; direct GitHub-side write was incorrectly labeled a Quicksave although the published generation had not advanced. → `datasets/observations/OBS-001-false-quicksave-provenance.md`
- **OBS-002 — Wrong Supabase project routing + ~13 minute recovery** — RSH-001 / EXP-001; correct `public.dm_runtime_read()` intent targeted a stale/wrong project, permission was denied, and recovery/save took roughly 13 minutes. → `datasets/observations/OBS-002-wrong-project-routing-recovery.md`
- **OBS-003 — Control Room reduced lookup pressure** — RSH-002; compact routing and smallest-authority guidance reduced broad/repeated lookup behavior. → `datasets/observations/OBS-003-control-room-routing.md`
- **OBS-004 — Spontaneous Deception check after offload** — RSH-002; DM-agent independently requested a meaningful Deception roll after operational/temporal knowledge had been substantially offloaded. → `datasets/observations/OBS-004-spontaneous-check-after-offload.md`
- **OBS-005 — Exact NPC knowledge ownership error (Asimak)** — RSH-003; Gork was incorrectly used as the player-facing Asimak lead until targeted authority checking restored Ravengard's route. → `datasets/observations/OBS-005-asimak-knowledge-routing.md`
- **OBS-006 — In-game time continuity lapse** — RSH-002; user had to remind the DM-agent of the established Day 19 time reference during play. → `datasets/observations/OBS-006-in-game-time-continuity-lapse.md`
- **OBS-007 — NPC referenced hidden roll/meta information** — RSH-003; NPC dialogue leaked backstage mechanical information about the player's roll/result. → `datasets/observations/OBS-007-npc-roll-meta-leak.md`
- **OBS-008 — Pre-Control-Room lookup churn** — RSH-002; normal scene play repeatedly caused broad/redundant lookups before compact routing reduced the pressure. → `datasets/observations/OBS-008-pre-control-room-lookup-churn.md`
- **OBS-009 — Cross-chat cold boot reconstructed the research frontier** — RSH-002; a fresh chat recovered the research state and exact next frontier from durable repo context without predecessor-chat memory. → `datasets/observations/OBS-009-cross-chat-cold-boot-continuity.md`

## Prototypes

- **PRT-001 — Controlled Quicksave Target and Independent Verifier** — RSH-001 / EXP-001; synthetic stateful target with predeclared invariants and independent final-state proof. → `prototypes/PRT-001-controlled-quicksave-target.md`
- **PRT-002 — Pre-registered A/B/C Controlled Quicksave Harness** — RSH-001 / EXP-001; balanced, model-identified synthetic harness over the PRT-001 target. → `prototypes/PRT-002-preregistered-abc-harness.md`
- **PRT-003 — Explicit-Gate Terra API Driver** — RSH-001 / EXP-001; fixed-pilot, external-only API bridge with dry-run and double live-run gate. → `prototypes/PRT-003-explicit-gate-terra-api-driver.md`

## Runs

- `RUN-000` — reserved example only → `datasets/runs/RUN-000-example.json`
- Real evidence begins at `RUN-001`.

## Results

- None yet. Use `templates/RES-template.md` for future synthesized results.

## Validation

- Local check: `python scripts/validate_research_repo.py`
- CI: `.github/workflows/research-validation.yml`
- The validator checks durable record frontmatter (including future `RES-###` records), ID uniqueness, related-ID existence, Registry coverage/paths, and the machine-readable run contract.

## Registry maintenance

When a new durable artifact is created:

1. classify it as `RSH`, `EXP`, `OBS`, `PRT`, `RES`, or `PRO`;
2. assign the next ID inside that family;
3. create the detailed file/folder from the appropriate template;
4. add one short bullet here;
5. add explicit `related_ids` in frontmatter and readable `Related records` links in the body;
6. run the validator;
7. never renumber old records merely to make the index prettier.

When a new observation appears before an experiment exists, tie it to the relevant `RSH-###`. Do **not** invent a synthetic experiment just to store it.

When a controlled experiment is run, create `RUN-###` under `datasets/runs/` and preserve failures as data.
