"""Fail-closed EXP-001 canonical RUN candidate/export boundary.

This module is deliberately offline. It never opens a trial, invokes a model,
uses an API key, resumes an interrupted trial, or automatically promotes
anything.

Canonical promotion is a separate explicit operation after a read-only
candidate has been built from immutable archived EXP-001 evidence.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from prototypes.prt001_controlled_quicksave.common import digest, payload_digest
from prototypes.prt001_controlled_quicksave.target import TARGET_VERSION
from prototypes.prt001_controlled_quicksave.verifier import (
    IndependentQuicksaveVerifier,
)
from runner.runner import compute_derived_metrics

from .api_driver import (
    DRIVER_OUTCOME_FILENAME,
    DRIVER_RECEIPT_FILENAME,
    DRIVER_REGISTRATION_FILENAME,
    DRIVER_VERSION,
    SUCCESS_CLAIM,
    UNABLE_CLAIM,
)
from .evidence import validate_external_batch
from .completion_cycle import FROZEN_MODEL_SETTINGS, build_completion_cycle
from .exp001_api_driver import EXP001_API_MODEL, EXP001_DRIVER_CONFIG, load_exp001_api_batch
from .research_cycle_batch import ORDER_POLICY, RESEARCH_CYCLE_MODE
from .harness import (
    EXPERIMENT_ID,
    EXPECTED_PAYLOAD,
    HARNESS_VERSION,
    INITIAL_PAYLOAD,
    PROMPT_REVISION,
    TASK_REQUEST,
    VARIANTS,
    VERIFICATION_SCOPE,
    agent_instruction,
)


class CanonicalExportError(RuntimeError):
    """Raised when evidence cannot safely map into a canonical RUN."""


_RUN_ID_RE = re.compile(r"RUN-[0-9]{3,}\Z")
_APPROVAL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_ALLOWED_FAILURE_STAGES = {
    "agent_interface",
    "transport",
    "target_operation",
    "verification",
    "receipt_evidence",
    "run_limit",
}

_COUNT_FIELDS = (
    "tool_calls",
    "wrong_tool_calls",
    "repeated_reads",
    "wrong_route_target_calls",
    "permission_routing_errors",
    "recovery_steps",
    "human_interventions",
)

_CODED_FIELDS = (
    "experiment_id",
    "variant",
    "date",
    "agent_model",
    "evidence_status",
    "authoritative_success",
    "completion_time_ms",
    "tool_calls",
    "wrong_tool_calls",
    "repeated_reads",
    "wrong_route_target_calls",
    "permission_routing_errors",
    "recovery_steps",
    "recovery_time_ms",
    "human_interventions",
    "false_success",
    "final_state_correct",
    "failure_stage",
    "context_volume",
    "procedural_decisions",
    "receipt_complete",
    "notes",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schema_path() -> Path:
    return _repository_root() / "schemas" / "run.schema.json"


def _require_run_id(value: object) -> str:
    if not isinstance(value, str) or not _RUN_ID_RE.fullmatch(value):
        raise CanonicalExportError(
            "proposed run_id must match RUN-[0-9]{3,}"
        )
    return value


def _require_approval_reference(value: object) -> str:
    if not isinstance(value, str) or not _APPROVAL_RE.fullmatch(value):
        raise CanonicalExportError(
            "approval reference must be a short opaque identifier"
        )
    return value


def _read_object(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise CanonicalExportError(f"{label}: missing or unsafe file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalExportError(f"{label}: invalid JSON") from exc
    if not isinstance(value, dict):
        raise CanonicalExportError(f"{label}: must contain an object")
    return value


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.is_symlink():
        raise CanonicalExportError("events.jsonl: missing or unsafe file")

    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CanonicalExportError("events.jsonl: unreadable") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CanonicalExportError(
                f"events.jsonl line {line_number}: invalid JSON"
            ) from exc
        if not isinstance(event, dict):
            raise CanonicalExportError(
                f"events.jsonl line {line_number}: event must be an object"
            )
        events.append(event)

    return events


def _parse_start_date(events: list[Mapping[str, Any]]) -> str:
    started = [
        event
        for event in events
        if event.get("event_type") == "trial_started"
    ]
    if len(started) != 1:
        raise CanonicalExportError(
            "terminal evidence must contain exactly one trial_started event"
        )

    raw = started[0].get("timestamp")
    if not isinstance(raw, str):
        raise CanonicalExportError(
            "trial_started timestamp is missing"
        )

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanonicalExportError(
            "trial_started timestamp is invalid"
        ) from exc

    if parsed.tzinfo is None:
        raise CanonicalExportError(
            "trial_started timestamp must include a timezone"
        )

    return parsed.date().isoformat()


def _validate_candidate(candidate: Mapping[str, Any]) -> None:
    if candidate.get("experiment_id") != EXPERIMENT_ID:
        raise CanonicalExportError(
            "candidate experiment_id must be EXP-001"
        )

    if candidate.get("variant") not in VARIANTS:
        raise CanonicalExportError(
            "candidate variant is outside frozen A/B/C"
        )

    stage = candidate.get("failure_stage")
    if stage is not None and stage not in _ALLOWED_FAILURE_STAGES:
        raise CanonicalExportError(
            "candidate failure_stage is outside frozen vocabulary"
        )

    authoritative = candidate.get("authoritative_success")
    evidence_status = candidate.get("evidence_status")

    if authoritative is not None and evidence_status != "established":
        raise CanonicalExportError(
            "an authoritative terminal verdict requires established evidence"
        )

    if authoritative is True:
        if candidate.get("final_state_correct") is not True:
            raise CanonicalExportError(
                "authoritative success requires final_state_correct=true"
            )
        if stage is not None:
            raise CanonicalExportError(
                "authoritative success requires failure_stage=null"
            )

    schema = _read_object(_schema_path(), label="run schema")
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(dict(candidate)), key=str)
    if errors:
        joined = "; ".join(error.message for error in errors)
        raise CanonicalExportError(
            f"candidate does not satisfy canonical RUN schema: {joined}"
        )


def map_coded_evidence_to_candidate(
    *,
    proposed_run_id: str,
    coded_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Pure schema mapping used after evidence has already been coded.

    This function cannot promote anything. It exists so UNKNOWN/null semantics
    can be regression-tested independently from a concrete driver version.
    """

    run_id = _require_run_id(proposed_run_id)

    missing = [
        field for field in _CODED_FIELDS
        if field not in coded_evidence
    ]
    if missing:
        raise CanonicalExportError(
            f"coded evidence is missing fields: {missing}"
        )

    candidate = {
        "run_id": run_id,
        **{
            field: coded_evidence[field]
            for field in _CODED_FIELDS
        },
    }

    _validate_candidate(candidate)
    return candidate


def _expected_variant_schedule() -> list[str]:
    return [trial.variant for trial in build_completion_cycle()]


def _validate_frozen_profile(
    batch,
    registration: Mapping[str, Any],
) -> None:
    manifest = batch.manifest

    exact_fields = {
        "artifact_kind": "noncanonical-preregistered-abc-batch",
        "harness_version": HARNESS_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "verification_scope": VERIFICATION_SCOPE,
        "task_request": TASK_REQUEST,
        "prompt_revision": PROMPT_REVISION,
        "batch_mode": RESEARCH_CYCLE_MODE,
        "variant_order_policy": ORDER_POLICY,
    }

    for field, expected in exact_fields.items():
        if manifest.get(field) != expected:
            raise CanonicalExportError(
                f"batch {field} differs from frozen EXP-001 profile"
            )

    if manifest.get("variants") != list(VARIANTS):
        raise CanonicalExportError(
            "batch variant set differs from frozen A/B/C profile"
        )

    if manifest.get("initial_payload") != INITIAL_PAYLOAD:
        raise CanonicalExportError(
            "batch initial payload differs from frozen profile"
        )

    if manifest.get("expected_payload") != EXPECTED_PAYLOAD:
        raise CanonicalExportError(
            "batch expected payload differs from frozen profile"
        )

    expected_instruction_digests = {
        variant: digest(agent_instruction(variant))
        for variant in VARIANTS
    }
    if (
        manifest.get("agent_instruction_digests")
        != expected_instruction_digests
    ):
        raise CanonicalExportError(
            "batch agent instruction digests differ from frozen profile"
        )

    if manifest.get("repeats_per_variant") != 10:
        raise CanonicalExportError(
            "batch repeat count differs from frozen EXP-001 10-per-variant plan"
        )

    if manifest.get("frozen_model_settings") != dict(FROZEN_MODEL_SETTINGS):
        raise CanonicalExportError(
            "batch model settings differ from frozen EXP-001 profile"
        )

    expected_schedule = _expected_variant_schedule()
    observed_schedule = [
        spec.variant for spec in batch.trial_specs
    ]
    if observed_schedule != expected_schedule:
        raise CanonicalExportError(
            "batch execution schedule differs from frozen balanced schedule"
        )

    if manifest.get("agent_model") != EXP001_API_MODEL:
        raise CanonicalExportError(
            "batch model identity differs from frozen EXP-001 profile"
        )

    if registration.get("driver_version") != DRIVER_VERSION:
        raise CanonicalExportError(
            "driver version differs from frozen EXP-001 profile"
        )

    if (
        registration.get("model_config")
        != EXP001_DRIVER_CONFIG.as_dict()
    ):
        raise CanonicalExportError(
            "driver model/settings differ from frozen EXP-001 profile"
        )

    claim_protocol = registration.get("completion_claim_protocol")
    if not isinstance(claim_protocol, Mapping):
        raise CanonicalExportError(
            "driver completion claim protocol is missing"
        )

    if claim_protocol.get("success") != SUCCESS_CLAIM:
        raise CanonicalExportError(
            "driver success claim differs from frozen profile"
        )

    if claim_protocol.get("unable") != UNABLE_CLAIM:
        raise CanonicalExportError(
            "driver unable claim differs from frozen profile"
        )

    for field in ("source_revision",):
        value = manifest.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CanonicalExportError(
                f"batch {field} is not recorded"
            )

    driver_revision = registration.get("driver_source_revision")
    if (
        not isinstance(driver_revision, str)
        or not driver_revision.strip()
    ):
        raise CanonicalExportError(
            "driver source revision is not recorded"
        )


def _canonical_failure_stage(
    events: list[Mapping[str, Any]],
    authoritative_success: bool | None,
) -> str | None:
    if authoritative_success is True:
        return None

    if authoritative_success is None:
        return None

    for event in reversed(events):
        event_type = event.get("event_type")

        if event_type == "api_request_incomplete":
            return "transport"

        if event_type == "driver_stop":
            if event.get("stage") == "model_turn_limit":
                return "run_limit"
            return None

        if event_type == "driver_error":
            stage = event.get("stage")
            if stage in {"tool_arguments", "agent_interface"}:
                return "agent_interface"
            if stage == "target_commit":
                return "target_operation"
            if stage == "verification":
                return "verification"
            return None

    tool_calls = [
        event
        for event in events
        if event.get("event_type") == "tool_call"
    ]

    if tool_calls:
        last_call = tool_calls[-1]
        if last_call.get("result") == "error":
            stage = last_call.get("stage")
            if stage == "agent_interface":
                return "agent_interface"
            if stage == "target_commit":
                return "target_operation"
            if stage == "verification":
                return "verification"

    # A complete negative authoritative terminal verifier verdict establishes
    # failure at the proof boundary when no earlier terminal stage is proven.
    return "verification"


def _validate_recovery_metric(
    events: list[Mapping[str, Any]],
    recorded: object,
) -> int | None:
    qualifying_errors = [
        event
        for event in events
        if (
            (
                event.get("event_type") == "tool_call"
                and event.get("error_code")
            )
            or event.get("event_type")
            in {
                "error",
                "api_request_incomplete",
                "driver_error",
            }
        )
    ]

    recovery_complete = [
        event
        for event in events
        if event.get("event_type") == "recovery_complete"
    ]

    if not qualifying_errors:
        if recorded != 0:
            raise CanonicalExportError(
                "recovery_time_ms must be 0 when no qualifying error occurred"
            )
        return 0

    if not recovery_complete:
        if recorded is not None:
            raise CanonicalExportError(
                "unrecovered error must record recovery_time_ms=null"
            )
        return None

    first_complete = recovery_complete[0]
    event_value = first_complete.get("recovery_time_ms")

    if (
        not isinstance(event_value, int)
        or isinstance(event_value, bool)
        or event_value < 0
    ):
        raise CanonicalExportError(
            "recovery_complete lacks valid monotonic recovery_time_ms"
        )

    if recorded != event_value:
        raise CanonicalExportError(
            "result recovery_time_ms conflicts with recovery_complete"
        )

    return event_value


def _coded_evidence_from_archived_trial(
    *,
    batch,
    spec,
) -> dict[str, Any]:
    trial_dir = batch.trial_dir(spec)

    trial = _read_object(
        trial_dir / "trial.json",
        label="trial.json",
    )
    result = _read_object(
        trial_dir / "result.json",
        label="result.json",
    )
    outcome = _read_object(
        trial_dir / DRIVER_OUTCOME_FILENAME,
        label=DRIVER_OUTCOME_FILENAME,
    )
    driver_receipt = _read_object(
        trial_dir / DRIVER_RECEIPT_FILENAME,
        label=DRIVER_RECEIPT_FILENAME,
    )
    events = _read_events(trial_dir / "events.jsonl")

    manifest = batch.manifest

    if trial.get("experiment_id") != EXPERIMENT_ID:
        raise CanonicalExportError(
            "trial experiment identity differs from EXP-001"
        )

    if trial.get("agent_model") != manifest.get("agent_model"):
        raise CanonicalExportError(
            "trial model identity conflicts with batch"
        )

    if trial.get("source_revision") != manifest.get("source_revision"):
        raise CanonicalExportError(
            "trial source revision conflicts with batch"
        )

    if trial.get("prompt_revision") != PROMPT_REVISION:
        raise CanonicalExportError(
            "trial prompt revision differs from frozen profile"
        )

    if trial.get("verification_scope") != VERIFICATION_SCOPE:
        raise CanonicalExportError(
            "trial verification scope differs from frozen profile"
        )

    if trial.get("task_request") != TASK_REQUEST:
        raise CanonicalExportError(
            "trial task request differs from frozen profile"
        )

    if (
        trial.get("agent_instruction_digest")
        != manifest["agent_instruction_digests"][spec.variant]
    ):
        raise CanonicalExportError(
            "trial agent instruction digest conflicts with batch"
        )

    expected_ref = trial.get("expected_state_reference")
    if not isinstance(expected_ref, Mapping):
        raise CanonicalExportError(
            "trial expected-state reference is missing"
        )

    if expected_ref.get("transaction_id") != spec.transaction_id:
        raise CanonicalExportError(
            "expected-state transaction identity is inconsistent"
        )

    expected_payload_digest = payload_digest(
        manifest["expected_payload"]
    )
    if (
        expected_ref.get("expected_payload_digest")
        != expected_payload_digest
    ):
        raise CanonicalExportError(
            "expected-state payload reference is inconsistent"
        )

    if outcome.get("trial_status") != "COMPLETE":
        raise CanonicalExportError(
            "only COMPLETE terminal trials are promotable"
        )

    if driver_receipt.get("trial_status") != "COMPLETE":
        raise CanonicalExportError(
            "driver receipt does not establish COMPLETE terminal state"
        )

    if outcome.get("terminal_error") is not None:
        raise CanonicalExportError(
            "COMPLETE trial cannot contain a terminal driver error"
        )

    if driver_receipt.get("terminal_error") is not None:
        raise CanonicalExportError(
            "COMPLETE receipt cannot contain a terminal driver error"
        )

    exact_result_fields = {
        "artifact_kind": "noncanonical-synthetic-abc-trial-result",
        "harness_version": HARNESS_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "variant": spec.variant,
        "agent_model": manifest["agent_model"],
        "source_revision": manifest["source_revision"],
        "prompt_revision": PROMPT_REVISION,
        "verification_scope": VERIFICATION_SCOPE,
        "trial_id": spec.trial_id,
    }
    for field, expected in exact_result_fields.items():
        if result.get(field) != expected:
            raise CanonicalExportError(
                f"result {field} conflicts with frozen trial evidence"
            )

    proof = result.get("verifier_proof")
    if not isinstance(proof, Mapping):
        raise CanonicalExportError(
            "authoritative verifier proof is missing"
        )

    proof_identity = {
        "verification_version": TARGET_VERSION,
        "verification_scope": VERIFICATION_SCOPE,
        "authoritative_for_scope": True,
        "verifier": IndependentQuicksaveVerifier.version,
        "transaction_id": spec.transaction_id,
    }
    for field, expected in proof_identity.items():
        if proof.get(field) != expected:
            raise CanonicalExportError(
                f"verifier proof {field} is missing or inconsistent"
            )

    if (
        proof.get("expected_generation")
        != expected_ref.get("expected_generation")
    ):
        raise CanonicalExportError(
            "verifier expected-generation reference is inconsistent"
        )

    if (
        proof.get("expected_payload_digest")
        != expected_ref.get("expected_payload_digest")
    ):
        raise CanonicalExportError(
            "verifier expected-payload reference is inconsistent"
        )

    authoritative_success = proof.get("authoritative_success")
    final_state_correct = proof.get("final_state_correct")

    if not isinstance(authoritative_success, bool):
        raise CanonicalExportError(
            "current frozen verifier must establish a boolean terminal verdict"
        )

    if not isinstance(final_state_correct, bool):
        raise CanonicalExportError(
            "current frozen verifier must establish final-state correctness"
        )

    if (
        authoritative_success is True
        and final_state_correct is not True
    ):
        raise CanonicalExportError(
            "verifier proof is internally inconsistent"
        )

    completion_time_ms = result.get("completion_time_ms")
    if (
        not isinstance(completion_time_ms, int)
        or isinstance(completion_time_ms, bool)
        or completion_time_ms < 0
    ):
        raise CanonicalExportError(
            "completion_time_ms is missing valid monotonic evidence"
        )

    diagnostics = result.get("diagnostic_metrics")
    if not isinstance(diagnostics, Mapping):
        raise CanonicalExportError(
            "result diagnostic metrics are missing"
        )

    recomputed = compute_derived_metrics(
        trial_dir / "events.jsonl"
    )

    for field in (*_COUNT_FIELDS, "agent_success_claims"):
        observed = diagnostics.get(field)
        expected = recomputed.get(field)
        if observed != expected:
            raise CanonicalExportError(
                f"diagnostic metric {field} conflicts with frozen telemetry"
            )

    recovery_time_ms = _validate_recovery_metric(
        events,
        diagnostics.get("recovery_time_ms"),
    )

    explicit_success_claim = bool(
        recomputed["agent_success_claims"]
    )
    false_success = bool(
        explicit_success_claim
        and authoritative_success is not True
    )

    if result.get("agent_success_claimed") != explicit_success_claim:
        raise CanonicalExportError(
            "agent success-claim summary conflicts with telemetry"
        )

    if result.get("false_success") != false_success:
        raise CanonicalExportError(
            "false_success conflicts with frozen claim/proof semantics"
        )

    usage = driver_receipt.get("usage")
    context_volume: int | None = None
    if isinstance(usage, Mapping):
        input_tokens = usage.get("input_tokens")
        if (
            isinstance(input_tokens, int)
            and not isinstance(input_tokens, bool)
            and input_tokens >= 0
        ):
            context_volume = input_tokens

    failure_stage = _canonical_failure_stage(
        events,
        authoritative_success,
    )

    coded = {
        "experiment_id": EXPERIMENT_ID,
        "variant": spec.variant,
        "date": _parse_start_date(events),
        "agent_model": manifest["agent_model"],
        "evidence_status": "established",
        "authoritative_success": authoritative_success,
        "completion_time_ms": completion_time_ms,
        "tool_calls": diagnostics["tool_calls"],
        "wrong_tool_calls": diagnostics["wrong_tool_calls"],
        "repeated_reads": diagnostics["repeated_reads"],
        "wrong_route_target_calls": diagnostics[
            "wrong_route_target_calls"
        ],
        "permission_routing_errors": diagnostics[
            "permission_routing_errors"
        ],
        "recovery_steps": diagnostics["recovery_steps"],
        "recovery_time_ms": recovery_time_ms,
        "human_interventions": diagnostics[
            "human_interventions"
        ],
        "false_success": false_success,
        "final_state_correct": final_state_correct,
        "failure_stage": failure_stage,
        "context_volume": context_volume,
        # No frozen observable procedural-decision counter exists in the
        # current terminal evidence. Null is required instead of guessing.
        "procedural_decisions": None,
        # PRT target/API-driver receipts are not the canonical authoritative
        # terminal receipt defined by METRIC_CONTRACT.md.
        "receipt_complete": None,
        "notes": (
            "Mapped from validated immutable archived EXP-001 evidence."
        ),
    }

    return coded


def build_canonical_run_candidate(
    batch_dir: Path,
    *,
    trial_id: str,
    proposed_run_id: str,
) -> dict[str, Any]:
    """Build one read-only candidate from immutable archived evidence."""

    run_id = _require_run_id(proposed_run_id)
    batch_dir = Path(batch_dir).expanduser().resolve()

    report = validate_external_batch(batch_dir)
    if report.get("validation_status") != "ARCHIVED_VALID":
        raise CanonicalExportError(
            "canonical mapping requires ARCHIVED_VALID immutable evidence; "
            f"got {report.get('validation_status')!r}"
        )

    try:
        batch = load_exp001_api_batch(batch_dir)
    except Exception as exc:
        raise CanonicalExportError(
            "archived batch registration could not be loaded safely"
        ) from exc

    registration = _read_object(
        batch.batch_dir / DRIVER_REGISTRATION_FILENAME,
        label=DRIVER_REGISTRATION_FILENAME,
    )
    _validate_frozen_profile(batch, registration)

    if not isinstance(trial_id, str) or not trial_id:
        raise CanonicalExportError(
            "trial_id must be supplied explicitly"
        )

    spec = next(
        (
            candidate
            for candidate in batch.trial_specs
            if candidate.trial_id == trial_id
        ),
        None,
    )
    if spec is None:
        raise CanonicalExportError(
            "trial_id is not present in the archived preregistration"
        )

    report_trial = next(
        (
            item
            for item in report.get("trials", [])
            if item.get("trial_id") == trial_id
        ),
        None,
    )
    if not isinstance(report_trial, Mapping):
        raise CanonicalExportError(
            "archived evidence report does not contain the requested trial"
        )

    if report_trial.get("evidence_state") != "COMPLETE":
        raise CanonicalExportError(
            "requested trial is not a COMPLETE terminal trial"
        )

    coded = _coded_evidence_from_archived_trial(
        batch=batch,
        spec=spec,
    )

    candidate = map_coded_evidence_to_candidate(
        proposed_run_id=run_id,
        coded_evidence=coded,
    )

    return {
        "artifact_kind": "canonical-run-candidate-preview",
        "source_batch_id": batch.batch_id,
        "source_trial_id": spec.trial_id,
        "candidate": candidate,
        "candidate_digest": digest(candidate),
        "promotion_authorized": False,
        "network_performed": False,
        "mutation_performed": False,
    }


def _write_json_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() or path.is_symlink():
        raise CanonicalExportError(
            f"refusing to overwrite canonical artifact: {path.name}"
        )

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=".tmp.",
        suffix=".tmp",
    ) as temporary:
        json.dump(
            dict(value),
            temporary,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        temporary.write("\n")
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)

    try:
        if path.exists() or path.is_symlink():
            raise CanonicalExportError(
                f"refusing to overwrite canonical artifact: {path.name}"
            )
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _reject_duplicate_run_id(
    runs_root: Path,
    run_id: str,
) -> None:
    if not runs_root.exists():
        return

    if runs_root.is_symlink() or not runs_root.is_dir():
        raise CanonicalExportError(
            "runs_root must be a normal directory"
        )

    for path in runs_root.glob("RUN-*.json"):
        if path.is_symlink() or not path.is_file():
            raise CanonicalExportError(
                "runs_root contains an unsafe canonical artifact"
            )

        existing = _read_object(
            path,
            label=f"existing canonical artifact {path.name}",
        )
        if existing.get("run_id") == run_id:
            raise CanonicalExportError(
                f"duplicate canonical run_id refused: {run_id}"
            )


def promote_canonical_run(
    batch_dir: Path,
    *,
    trial_id: str,
    run_id: str,
    approved_candidate_digest: str,
    approval_reference: str,
    runs_root: Path,
    confirm_promotion: bool,
) -> dict[str, Any]:
    """Explicitly write one human-approved candidate exactly once."""

    if confirm_promotion is not True:
        raise CanonicalExportError(
            "canonical promotion requires explicit confirm_promotion=True"
        )

    run_id = _require_run_id(run_id)
    approval_reference = _require_approval_reference(
        approval_reference
    )

    if (
        not isinstance(approved_candidate_digest, str)
        or not _SHA256_RE.fullmatch(approved_candidate_digest)
    ):
        raise CanonicalExportError(
            "approved candidate digest must be a lowercase SHA-256 digest"
        )

    preview = build_canonical_run_candidate(
        batch_dir,
        trial_id=trial_id,
        proposed_run_id=run_id,
    )

    if preview["candidate_digest"] != approved_candidate_digest:
        raise CanonicalExportError(
            "approved candidate digest does not match current immutable evidence"
        )

    candidate = preview["candidate"]
    _validate_candidate(candidate)

    runs_root = Path(runs_root).expanduser().resolve()
    batch_root = Path(batch_dir).expanduser().resolve()

    if (
        runs_root == batch_root
        or batch_root in runs_root.parents
        or runs_root in batch_root.parents
    ):
        raise CanonicalExportError(
            "canonical output must remain separate from source evidence"
        )

    _reject_duplicate_run_id(runs_root, run_id)

    destination = runs_root / f"{run_id}.json"
    _write_json_new(destination, candidate)

    written = _read_object(
        destination,
        label=f"written canonical artifact {destination.name}",
    )
    _validate_candidate(written)

    if digest(written) != approved_candidate_digest:
        raise CanonicalExportError(
            "written canonical artifact digest changed unexpectedly"
        )

    return {
        "promotion_status": "PROMOTED_EXACTLY_ONCE",
        "run_id": run_id,
        "candidate_digest": approved_candidate_digest,
        "approval_reference": approval_reference,
        "output_path": str(destination),
        "network_performed": False,
        "source_evidence_modified": False,
    }
