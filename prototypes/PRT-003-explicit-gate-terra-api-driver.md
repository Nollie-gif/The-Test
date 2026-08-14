---
id: PRT-003
title: Explicit-Gate Terra API Driver
status: IMPLEMENTED
related_ids: [RSH-001, EXP-001, PRT-001, PRT-002, OBS-001, OBS-002]
date: 2026-08-14
author: Nollie + ChatGPT
---
# PRT-003 — Explicit-Gate Terra API Driver

## Purpose

PRT-003 connects the existing PRT-002 synthetic A/B/C harness to one fixed API
pilot. It is a **driver**, not a new experiment and not a canonical RUN
exporter.

The fixed initial pilot configuration is:

- model: \`gpt-5.6-terra\`;
- reasoning effort: \`medium\`;
- maximum model turns per trial: \`8\`;
- maximum output tokens per API turn: \`512\`.

The same configuration is pre-registered beside every batch. It must remain
identical for variants A, B, and C. The experiment changes the cockpit/tool
surface, never the pilot.

## Scope and authority

PRT-003 calls only the functions exposed by the already implemented PRT-002
variant contract over a fresh synthetic PRT-001 target.

It has no Mission 10, GitHub, Supabase, filesystem, database, production, or
canonical research-run authority. It writes only external \`BATCH-*\` /
\`TRIAL-*\` artifacts and rejects any output path inside this repository.

No PRT-003 artifact is a \`RUN-###\` record or experimental evidence.

## Completion-claim rule

The common instruction requires one exact final line:

- \`CLAIM: quicksave_complete\` — the agent claims success;
- \`CLAIM: unable\` — the agent does not claim success.

Only the exact success line becomes an explicit \`agent_success_claim\`
telemetry event. The independent PRT-001 verifier remains authoritative for
synthetic final-state correctness. A claim without verifier success is therefore
recorded as a false-success condition rather than being treated as proof.

This common textual rule does not add a visible tool or alter the A/B/C tool
surfaces.

## Live-run controls

The driver is safe by default:

1. \`create-batch\` creates a full immutable, balanced PRT-002 batch and
   driver-registration sidecar but makes no API request.
2. \`plan-next\` prints the exact next request plan without opening a trial or
   touching the network.
3. \`run-next\` can make **one** API trial only when both \`--live\` and
   \`--confirm-live-run\` are present.
4. The API key is read only at live-run time from \`OPENAI_API_KEY\`; it is
   never written to source, batch artifacts, logs, or GitHub.
5. The OpenAI project remains separately protected by its organization hard
   spend limit.

The driver uses the Responses API function-calling loop and records response
IDs, token counts when returned, model-turn count, tool telemetry, and the
independent verifier outcome beside the external trial.

## Research data boundary

Batch research uses only the official API with synthetic or authorized data. `store: false` is required in request payloads for data minimisation; it does not claim zero provider retention. Refusals are observations. Browser automation/scraping, safeguard bypass, hidden-prompt extraction, and competitor-model training are out of scope.
## Batch workflow

After a separate PM authorization for a real non-canonical trial:

\`\`\`bash
# No API call: create an external pre-registered batch.
python -m prototypes.prt002_abc_harness.api_driver create-batch \\
  --outdir /safe/external/output \\
  --operator Nollie \\
  --source-revision <PRT-002-main-SHA> \\
  --driver-source-revision <PRT-003-main-SHA>

# No API call: inspect the next pre-registered trial.
python -m prototypes.prt002_abc_harness.api_driver plan-next \\
  --batch-dir /safe/external/output/BATCH-...

# Exactly one paid synthetic API trial, only after an explicit go-ahead.
python -m prototypes.prt002_abc_harness.api_driver run-next \\
  --batch-dir /safe/external/output/BATCH-... \\
  --live --confirm-live-run
\`\`\`

The final command is intentionally not part of this implementation PR's test
run and must not be invoked merely to make a check green.

## Promotion boundary

PRT-003 does not satisfy the EXP-001 promotion gate. Before any canonical
\`RUN-001\` is considered, the project still needs approved mapping semantics,
a real authoritative verifier for the scope being evidenced, passing
validation/CI, and PM review.

## Related records

- RSH-001
- EXP-001
- PRT-001
- PRT-002
- OBS-001
- OBS-002
