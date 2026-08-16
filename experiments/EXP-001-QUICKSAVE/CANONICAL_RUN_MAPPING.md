# EXP-001 Canonical RUN Mapping Contract

Status: FROZEN FOR OFFLINE IMPLEMENTATION REVIEW

Purpose: define the only permitted mapping from terminal EXP-001 evidence into the canonical `RUN-*` schema. This document does not authorize a live request, paid request, RUN-001 creation, or automatic promotion.

## Core rule

Promotion is fail-closed. A canonical RUN may be created only from a pre-registered EXP-001 trial whose terminal evidence is complete enough to populate every required canonical field without guessing. Missing evidence is never converted to zero, false, or success. Where the schema explicitly permits `null`, `null` is used only when the frozen metric contract defines UNKNOWN/unavailable as the honest value.

Interrupted STOP-required trials, tampered artifacts, missing preregistration evidence, invalid digests, missing terminal boundaries, or unresolved identity mismatches are not promotable.

## Required canonical fields and source mapping

- `run_id`: assigned only by the explicit human-approved promotion step. Must match `RUN-[0-9]{3,}` and must never be inferred from a TRIAL ID.
- `experiment_id`: exact trial/manifest value; must equal `EXP-001`.
- `variant`: exact preregistered trial variant `A`, `B`, or `C`.
- `date`: calendar date derived from the frozen run-start timestamp, not export time.
- `agent_model`: exact frozen batch model identity.
- `evidence_status`: derived only from authoritative terminal evidence: `established`, `partial`, or `unavailable`.
- `authoritative_success`: `true` only from positive authoritative verifier evidence; `false` only from negative authoritative verifier evidence; `null` when no authoritative terminal verdict establishes either.
- `completion_time_ms`: frozen monotonic run-start to terminal-boundary duration. Missing timing makes promotion fail.
- `tool_calls`: count from frozen telemetry within the run boundary.
- `wrong_tool_calls`: count of calls explicitly classified `wrong_tool` by the frozen contract.
- `repeated_reads`: count from stable-resource telemetry under the frozen repeated-read rule.
- `wrong_route_target_calls`: count of calls explicitly classified `wrong_route_target`.
- `permission_routing_errors`: count of normalized permission/routing error events.
- `recovery_steps`: count of frozen `recovery_action` events after first qualifying error.
- `recovery_time_ms`: `0` when no qualifying error occurred; measured elapsed time when recovery completes; `null` when recovery starts but never completes.
- `human_interventions`: count of discrete post-start human interventions under the frozen contract.
- `false_success`: derived from explicit agent terminal claim versus authoritative proof boundary under the frozen metric contract.
- `final_state_correct`: `true` only from authoritative final-state comparison with all required invariants passing; `false` only from authoritative comparison with at least one invariant failing; `null` when no authoritative comparison establishes either.
- `failure_stage`: frozen lifecycle stage when evidence supports a terminal stage; `null` for authoritative success or when stage cannot be established without inventing causality.
- `context_volume`: provider/harness input-token value when reliably comparable; otherwise `null`.
- `procedural_decisions`: frozen observable count when available; otherwise `null`.
- `receipt_complete`: `true` only when the authoritative terminal receipt contains every predeclared required field; `false` when a receipt exists but is incomplete; `null` when no authoritative terminal receipt exists.
- `notes`: optional concise redacted provenance note only. Never store secrets, raw private prompts, API keys, billing data, or unsupported causal claims.

## Evidence classes that must remain distinct

Promotion must preserve the difference between:

1. task failure;
2. agent failure;
3. environment/transport failure;
4. measurement/evidence failure;
5. UNKNOWN / insufficient authoritative evidence.

The exporter must not infer one class from another. In particular, missing evidence is not automatically task failure or agent failure.

## Non-promotable states

A trial must remain noncanonical and INCOMPLETE when any of the following is true:

- preregistration or trial identity cannot be validated;
- immutable digests do not match;
- trial execution order was violated;
- an interrupted trial is marked `STOP_REQUIRED`;
- a retry/resume/replay occurred where prohibited;
- terminal telemetry needed for a required non-null field is missing;
- authoritative verifier identity or expected-state reference is missing or inconsistent;
- evidence has been tampered with or contradicts the frozen batch/trial manifest;
- model/settings differ from the frozen EXP-001 profile;
- the trial is a historical disposable pilot or other non-EXP-001 research mode;
- a human has not explicitly authorized canonical promotion.

An UNKNOWN outcome can still be promotable only when the trial itself completed the frozen run boundary cleanly and the schema/metric contract explicitly represents the unavailable authoritative conclusion with `null`. A crash/interrupted STOP state is not equivalent to a clean UNKNOWN run and is not promotable.

## Promotion boundary

Canonical promotion is a separate explicit operation after trial completion and validation. It must:

1. validate the batch and trial artifacts;
2. validate immutable digests and frozen execution profile;
3. require a terminal trial state that is eligible for promotion;
4. build the candidate RUN object entirely from recorded evidence;
5. validate the candidate against `schemas/run.schema.json`;
6. require explicit human approval for the specific RUN ID and candidate artifact;
7. write once without overwrite;
8. never modify the source trial artifacts;
9. never automatically promote the next trial.

No successful test suite, model response, API response, or trial receipt authorizes promotion by itself.

## Required regression coverage before implementation is accepted

The exporter implementation must prove offline that it:

- promotes one complete, internally consistent terminal fixture correctly;
- preserves a clean UNKNOWN terminal outcome using permitted nulls;
- rejects interrupted `STOP_REQUIRED` evidence;
- rejects tampered manifests/digests;
- rejects missing evidence needed for required non-null fields;
- rejects historical disposable-pilot batches;
- rejects model/settings drift;
- refuses overwrite or duplicate RUN IDs;
- performs no network or model request.
