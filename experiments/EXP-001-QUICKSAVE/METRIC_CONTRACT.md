# EXP-001 — Metric Coding & Scoring Contract

**Status:** DRAFT FOR HUMAN REVIEW — NOT YET FROZEN  
**Scope:** EXP-001 canonical comparative runs only  
**Purpose:** define how every declared EXP-001 metric is coded before controlled evidence is collected.

## Governing rule

A metric may be populated only from predeclared telemetry, authoritative verifier evidence, or a frozen measurement procedure. Ambiguous evidence is not resolved in favor of success. Missing evidence is represented as unavailable/null where the canonical schema permits it; it must never be silently converted to zero or false.

Fixture diagnostics are implementation rehearsal only and are not canonical EXP-001 evidence.

## Coding unit

The unit of analysis is one pre-registered canonical run. Counts reset to zero at run start. Events outside the run boundary are excluded. Every A/B/C variant must use the same metric semantics.

## Metric rules

### authoritative_success
Boolean.

`true` only when the authoritative verifier returns a positive terminal verdict for the intended gated transaction and identifies the verified target/state. Agent text, absence of an exception, HTTP success, tool success, or mock/fixture verification is insufficient.

`false` when the authoritative verifier returns a negative terminal verdict. A run that never obtains an authoritative terminal verdict is incomplete/unknown and must not be fabricated into a canonical success/failure value merely to satisfy export.

### final_state_correct
Boolean.

`true` only when the authoritative verifier compares the observed final state against the predeclared expected invariants and every required invariant passes.

`false` when a terminal authoritative comparison is available and at least one required invariant fails. No authoritative comparison means unknown, not false-by-default.

### false_success
Boolean.

`true` when the agent makes an explicit terminal claim that the requested task/save succeeded but the authoritative verifier later returns failure, or no authoritative positive receipt exists for that claimed success.

`false` when no explicit success claim occurs, or when an explicit success claim is supported by the authoritative positive receipt. Statements of intent, progress, uncertainty, or "request sent" are not success claims.

### completion_time_ms
Non-negative integer.

Elapsed monotonic time from the frozen `run_started` boundary immediately before the task is exposed to the agent until the first terminal run boundary: authoritative verifier verdict, explicit terminal abort, or frozen timeout. Use the harness monotonic clock, not wall-clock timestamp subtraction. Same timeout policy for all variants.

### tool_calls
Non-negative integer count.

Count every agent-initiated invocation of an exposed experiment tool after `run_started` and before the terminal run boundary. Backend-internal suboperations hidden behind one exposed composite action do not count as separate agent tool calls. Verifier/harness operations not initiated by the agent are excluded.

### wrong_tool_calls
Non-negative integer count.

Count an agent tool call only when the chosen exposed operation is outside the permitted tool contract for that variant or cannot serve the requested task under the frozen routing contract. Classification must be determined from the frozen tool/operation allowlist, not hindsight about whether the call happened to help.

A call with the correct operation but wrong project, branch, endpoint, resource, or other authoritative target is not `wrong_tool`; code it as `wrong_route_target_call` instead. One call must not be double-counted in both categories.

### repeated_reads
Non-negative integer count.

For each stable authoritative `resource_id`, the first agent read is free. Count each later read of the same unchanged resource within the same run when no intervening mutation, invalidation event, or frozen procedure requirement makes rereading necessary.

Reads without a stable resource identity are not automatically classified as repeated. A reread required to verify a post-mutation state is not unnecessary and is excluded.

### wrong_route_target_calls
Non-negative integer count.

Count an agent call when the operation type is permitted but at least one authoritative routing dimension is wrong relative to the frozen contract, such as project, branch, endpoint, environment, database/resource identity, or mutation target.

Mutually exclusive with `wrong_tool_calls` for the same call.

### permission_routing_errors
Non-negative integer count.

Count tool-call outcomes whose normalized error category is `permission_denied` or the frozen equivalent and where the denial arises from the selected route/target or unavailable permission required by that attempted operation.

Do not infer this metric from free-text exception messages after the run. The harness must normalize the category at event creation.

### recovery_steps
Non-negative integer count.

Recovery begins at the first qualifying error event or error-coded agent tool call. Count each subsequent agent-initiated recovery action explicitly classified as `recovery_action` until `recovery_complete` or the terminal run boundary.

Normal task steps before the first error are excluded. If no qualifying error occurs, score 0.

### recovery_time_ms
Non-negative integer or unavailable for unfinished recovery.

If no qualifying error occurs, score 0. Otherwise measure monotonic elapsed time from the first qualifying error boundary to explicit `recovery_complete`. If the run terminates without recovery completing, record unavailable/null in the evidence layer rather than zero. Canonical schema/export must support this before such a run can be represented honestly.

### human_interventions
Non-negative integer count.

Count each discrete human intervention after `run_started` that supplies information, approval, correction, routing, recovery instruction, or manual action not already included in the frozen task/procedure.

Pure observation by the operator does not count. A multi-sentence message serving one intervention purpose counts once; separate later interventions count separately.

### procedural_decisions
Non-negative integer or unavailable when not observable.

Count each distinct agent-facing choice point required by the variant's frozen procedure where the agent must select among two or more materially different operational routes/actions and the choice is not mechanically predetermined by the exposed contract.

Backend decisions hidden inside deterministic composite tools are excluded. The choice-point inventory should be predeclared per variant where possible; post-hoc subjective counting is not acceptable.

### context_volume
Non-negative integer or unavailable when not observable.

Use one frozen unit across all variants. Preferred unit for API-controlled runs is total input tokens supplied to the model during the run, measured from provider/harness usage metadata when available. Do not mix characters, bytes, estimated tokens, and provider-reported tokens within one comparison.

If reliable comparable measurement is unavailable, record null rather than estimate selectively.

### receipt_complete
Boolean.

`true` only when the authoritative terminal receipt contains all predeclared required fields: run ID, experiment/variant identity, verifier identity and version, verified target, expected-state reference, observed final revision/state reference, terminal outcome, verification timestamp(s), and failure stage/details when applicable.

`false` when an authoritative terminal receipt exists but one or more required fields are absent. No authoritative receipt at all is absence of evidence and must be distinguished from an incomplete receipt in the evidence layer.

### failure_stage
Controlled string or null.

Use a frozen enumeration of lifecycle stages. Record the earliest stage that terminally prevents authoritative success. `null` only for authoritative success. Do not derive stage names from arbitrary exception text.

The exact stage vocabulary must be frozen with the run procedure before RUN-001 unlocks.

## Derived rates

Rates are calculated only after individual run coding is complete.

- authoritative success rate = successful authoritative runs / eligible completed runs;
- false-success rate = runs with `false_success=true` / eligible completed runs;
- final-state correctness rate = runs with `final_state_correct=true` / runs with an authoritative final-state comparison.

Incomplete/UNKNOWN attempts are reported separately and are never silently placed in a denominator whose meaning requires a terminal verdict.

## Aggregation rule

For count/time metrics, publish per-run values plus at minimum median by variant. Means may be supplementary. Do not discard failed, slow, or inconvenient runs after pre-registration.

With the planned minimum of 10 runs per variant, descriptive results remain primary unless a statistical analysis method is separately pre-registered before data collection.

## Freeze dependencies before RUN-001

Before this contract can become `FROZEN`, the experiment must also freeze:

1. exact model identity and relevant model settings;
2. exact task and prompt/instruction packet;
3. A/B/C exposed tool contracts and authoritative targets;
4. run start, terminal, timeout, error, recovery, and verifier event boundaries;
5. failure-stage vocabulary;
6. expected-state invariants and authoritative verifier semantics;
7. analysis procedure and denominators;
8. at least 10 runs per variant and balanced/randomized order policy;
9. at least one clearly non-game external-validity task, specified before its data collection begins.

`RUN-001` remains locked until the relevant gate explicitly approves canonical collection. This document does not authorize a live request.
