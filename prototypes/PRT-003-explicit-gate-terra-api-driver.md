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

## Disposable single-trial pilot mode

The ordinary PRT-002 A/B/C schedule remains a balanced nine-trial research
batch. A separately labelled **disposable single-trial pilot** may instead
freeze exactly one Variant-C synthetic trial. It is not comparative research
and cannot create a canonical run.

Its fixed guardrails are: `gpt-5.6-terra`, medium reasoning, at most four
model turns, at most 512 output tokens per turn, an 8,000-byte pre-transport
payload ceiling, and a conservative `$0.10` cumulative cost envelope using
the pre-registered input/output price constants. It sets `store: false` and
does not use conversation persistence, recap/summary/compaction fields,
background continuation, or external retrieval.

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
6. If a process stops after the durable \`api_request_started\` journal event
   but before a final receipt, the batch is blocked. \`inspect-interrupted\`
   produces a read-only \`STOP_REQUIRED\` report; it never retries, resumes,
   finalizes, or opens another trial.
7. A later offline-only disposition may record that hard stop in one immutable
   \`interruption-disposition.json\`. It binds only safe journal facts and
   remains \`NOT_ACCEPTED\`; it never becomes a result, receipt, retry, resume,
   API authorization, or \`RUN-*\` record.
8. A future disposable pilot may receive one immutable
   \`pilot-approval-proof.json\` before its first trial opens. It freezes the
   exact batch, driver registration, full pre-registered schedule, fixed model
   limits, and an opaque decision reference. The proof is explicitly **not** a
   live API authorization; the CLI still requires both explicit live flags and
   a separate human authorization.

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

# No API call and no mutation: inspect an interrupted batch. A STOP_REQUIRED
# result means do not retry or resume the trial.
python -m prototypes.prt002_abc_harness.api_driver inspect-interrupted \\
  --batch-dir /safe/external/output/BATCH-...

# No API call: create one immutable STOP disposition only for a verified hard
# crash. It does not repair, retry, resume, or finalize the interrupted trial.
python -m prototypes.prt002_abc_harness.api_driver record-interruption-disposition \\
  --batch-dir /safe/external/output/BATCH-...

# No API call: before any future disposable pilot opens a trial, freeze its
# exact scope with an opaque non-personal decision ID. This is not a live-run
# authorization; the later live command still needs both explicit flags and a
# separate human authorization.
python -m prototypes.prt002_abc_harness.api_driver create-pilot-approval-proof \\
  --batch-dir /safe/external/output/BATCH-... \\
  --approval-reference PM-DECISION-001

# No API call and no mutation: validate a redacted external-evidence report.
# STOP_REQUIRED means preserve the artifacts and do not retry, resume, or repair.
python -m prototypes.prt002_abc_harness.api_driver validate-external-evidence \\
  --batch-dir /safe/external/output/BATCH-...

# No API call: only after every pre-registered trial is terminal and the
# previous command reports ARCHIVE_READY, bind the safe artifacts with one
# immutable evidence-manifest.json. This is still non-canonical and not a RUN.
python -m prototypes.prt002_abc_harness.api_driver archive-external-evidence \\
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
