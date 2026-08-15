"""Offline validation and archival checks for external PRT-003 batches.

This module deliberately treats an external PRT-003 batch as a non-canonical
prototype artifact.  It never opens a trial, makes a network request, retries
an interrupted request, or creates a ``RUN-*`` record.

The optional mutations are immutable evidence artifacts only.  A terminal batch
may receive an ``evidence-manifest.json``.  A hard process interruption may
receive an ``interruption-disposition.json`` that records its STOP state, but
never converts it into a final receipt, retry, resume, or RUN artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from prototypes.prt001_controlled_quicksave.common import digest, now_iso

from .api_driver import (
    DRIVER_OUTCOME_FILENAME,
    DRIVER_RECEIPT_FILENAME,
    DRIVER_REGISTRATION_FILENAME,
    DRIVER_VERSION,
    load_api_batch,
)
from .harness import DISPOSABLE_SINGLE_TRIAL_MODE, PreregisteredBatch, TrialSpec


EVIDENCE_MANIFEST_FILENAME = "evidence-manifest.json"
EVIDENCE_MANIFEST_KIND = "noncanonical-api-driver-evidence-manifest"
EVIDENCE_STATUS = "synthetic-prototype-only-not-a-RUN"
INTERRUPTION_DISPOSITION_FILENAME = "interruption-disposition.json"
INTERRUPTION_DISPOSITION_KIND = "noncanonical-api-driver-interruption-disposition"
PILOT_APPROVAL_PROOF_FILENAME = "pilot-approval-proof.json"
PILOT_APPROVAL_PROOF_KIND = "noncanonical-api-driver-pilot-approval-proof"

_FINAL_ARTIFACTS = ("result.json", DRIVER_OUTCOME_FILENAME, DRIVER_RECEIPT_FILENAME)
_ALLOWED_TRIAL_CHILDREN = {
    "trial.json",
    "events.jsonl",
    "target",
    *_FINAL_ARTIFACTS,
}
_FORBIDDEN_EVIDENCE_KEYS = {
    "authorization",
    "api_key",
    "openai_api_key",
    "instructions",
    "input",
    "payload",
    "raw_response",
    "response_body",
    "raw_error",
    "error_body",
    "messages",
}
_OPAQUE_APPROVAL_REFERENCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


class EvidenceValidationError(RuntimeError):
    """Raised when an external batch cannot be safely archived."""


def _require_opaque_approval_reference(value: object) -> str:
    """Accept a short opaque decision reference, never an email or a file path."""

    if not isinstance(value, str) or not _OPAQUE_APPROVAL_REFERENCE.fullmatch(value):
        raise EvidenceValidationError(
            "approval reference must be an opaque identifier; do not use names, emails, or paths"
        )
    return value


def _file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _read_object(path: Path, *, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file() or path.is_symlink():
        errors.append(f"{label}: missing or unsafe file")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        errors.append(f"{label}: invalid JSON")
        return None
    if not isinstance(value, dict):
        errors.append(f"{label}: must contain a JSON object")
        return None
    _check_forbidden_keys(value, label=label, errors=errors)
    return value


def _check_forbidden_keys(value: Any, *, label: str, errors: list[str]) -> None:
    """Reject field names that would carry raw credential/request material.

    The check is intentionally about field names, never values: a response ID or
    a safe digest must not accidentally be treated as a secret merely because it
    contains an arbitrary character sequence.
    """

    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            if isinstance(raw_key, str) and raw_key.casefold() in _FORBIDDEN_EVIDENCE_KEYS:
                errors.append(f"{label}: forbidden raw evidence field {raw_key!r}")
            _check_forbidden_keys(child, label=label, errors=errors)
    elif isinstance(value, list):
        for child in value:
            _check_forbidden_keys(child, label=label, errors=errors)


def _read_events(path: Path, *, errors: list[str]) -> dict[str, int]:
    counts = {
        "api_request_started_count": 0,
        "api_response_observed_count": 0,
        "api_request_incomplete_count": 0,
    }
    if not path.is_file() or path.is_symlink():
        errors.append("events.jsonl: missing or unsafe file")
        return counts

    previous_sequence = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        errors.append("events.jsonl: unreadable")
        return counts

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"events.jsonl line {line_number}: invalid JSON")
            continue
        if not isinstance(event, dict):
            errors.append(f"events.jsonl line {line_number}: event must be an object")
            continue
        _check_forbidden_keys(event, label=f"events.jsonl line {line_number}", errors=errors)
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or sequence <= previous_sequence:
            errors.append(f"events.jsonl line {line_number}: sequence must be strictly increasing")
        else:
            previous_sequence = sequence
        event_type = event.get("event_type")
        if not isinstance(event_type, str) or not event_type:
            errors.append(f"events.jsonl line {line_number}: missing event_type")
            continue
        if event_type == "api_request_started":
            counts["api_request_started_count"] += 1
        elif event_type == "api_response_observed":
            counts["api_response_observed_count"] += 1
        elif event_type == "api_request_incomplete":
            counts["api_request_incomplete_count"] += 1
    return counts


def _verify_trial_identity(
    trial: Mapping[str, Any],
    *,
    batch: PreregisteredBatch,
    spec: TrialSpec,
    errors: list[str],
) -> None:
    if trial.get("artifact_kind") != "noncanonical-preregistered-abc-trial":
        errors.append("trial.json: wrong artifact kind")
    if trial.get("evidence_status") != EVIDENCE_STATUS:
        errors.append("trial.json: wrong evidence status")
    if trial.get("batch_id") != batch.batch_id:
        errors.append("trial.json: batch ID does not match batch.json")
    if trial.get("batch_preregistration_digest") != batch.preregistration_digest:
        errors.append("trial.json: preregistration digest does not match batch.json")
    if trial.get("trial_spec") != spec.as_dict():
        errors.append("trial.json: trial spec does not match pre-registration")
    if trial.get("trial_spec_digest") != digest(spec.as_dict()):
        errors.append("trial.json: trial spec digest does not match pre-registration")


def _verify_final_artifacts(
    trial_dir: Path,
    *,
    batch: PreregisteredBatch,
    spec: TrialSpec,
    events: Mapping[str, int],
    errors: list[str],
) -> str | None:
    result = _read_object(trial_dir / "result.json", label="result.json", errors=errors)
    outcome = _read_object(
        trial_dir / DRIVER_OUTCOME_FILENAME,
        label=DRIVER_OUTCOME_FILENAME,
        errors=errors,
    )
    receipt = _read_object(
        trial_dir / DRIVER_RECEIPT_FILENAME,
        label=DRIVER_RECEIPT_FILENAME,
        errors=errors,
    )
    if result is None or outcome is None or receipt is None:
        return None

    if result.get("artifact_kind") != "noncanonical-synthetic-abc-trial-result":
        errors.append("result.json: wrong artifact kind")
    if result.get("evidence_status") != EVIDENCE_STATUS:
        errors.append("result.json: wrong evidence status")
    if result.get("batch_id") != batch.batch_id:
        errors.append("result.json: batch ID does not match batch.json")
    if result.get("batch_preregistration_digest") != batch.preregistration_digest:
        errors.append("result.json: preregistration digest does not match batch.json")
    if result.get("trial_id") != spec.trial_id:
        errors.append("result.json: trial ID does not match pre-registration")
    if result.get("trial_spec_digest") != digest(spec.as_dict()):
        errors.append("result.json: trial spec digest does not match pre-registration")
    verifier_proof = result.get("verifier_proof")
    if not isinstance(verifier_proof, Mapping):
        errors.append("result.json: verifier proof is missing")

    if outcome.get("artifact_kind") != "noncanonical-api-driver-outcome":
        errors.append(f"{DRIVER_OUTCOME_FILENAME}: wrong artifact kind")
    if outcome.get("evidence_status") != EVIDENCE_STATUS:
        errors.append(f"{DRIVER_OUTCOME_FILENAME}: wrong evidence status")
    if outcome.get("driver_version") != DRIVER_VERSION:
        errors.append(f"{DRIVER_OUTCOME_FILENAME}: wrong driver version")
    if outcome.get("result_path") != "result.json":
        errors.append(f"{DRIVER_OUTCOME_FILENAME}: result path must be relative result.json")

    if receipt.get("artifact_kind") != "noncanonical-api-driver-receipt":
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: wrong artifact kind")
    if receipt.get("evidence_status") != EVIDENCE_STATUS:
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: wrong evidence status")
    if receipt.get("driver_version") != DRIVER_VERSION:
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: wrong driver version")
    if receipt.get("request_journal_path") != "events.jsonl":
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: request journal path must be relative events.jsonl")
    if receipt.get("result_digest") != digest(result):
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: result digest does not match result.json")
    if isinstance(verifier_proof, Mapping) and receipt.get("verifier_proof_digest") != digest(verifier_proof):
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: verifier proof digest does not match result.json")

    trial_status = receipt.get("trial_status")
    if trial_status not in {"COMPLETE", "INCOMPLETE"}:
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: trial status must be COMPLETE or INCOMPLETE")
        return None
    expected_acceptance = "SYNTHETIC_COMPLETE_NOT_A_RUN" if trial_status == "COMPLETE" else "NOT_ACCEPTED"
    if receipt.get("acceptance_status") != expected_acceptance:
        errors.append(f"{DRIVER_RECEIPT_FILENAME}: acceptance status conflicts with trial status")
    if outcome.get("trial_status") != trial_status:
        errors.append(f"{DRIVER_OUTCOME_FILENAME}: trial status conflicts with receipt")

    for field, expected in (
        ("request_attempts", events["api_request_started_count"]),
        ("unknown_request_attempts", events["api_request_incomplete_count"]),
    ):
        if receipt.get(field) != expected:
            errors.append(f"{DRIVER_RECEIPT_FILENAME}: {field} conflicts with events.jsonl")
        if outcome.get(field) != expected:
            errors.append(f"{DRIVER_OUTCOME_FILENAME}: {field} conflicts with events.jsonl")
    for field in ("model_response_ids", "usage", "terminal_error"):
        if outcome.get(field) != receipt.get(field):
            errors.append(f"{DRIVER_OUTCOME_FILENAME}: {field} conflicts with receipt")

    unresolved = (
        events["api_request_started_count"]
        - events["api_response_observed_count"]
        - events["api_request_incomplete_count"]
    )
    if unresolved != 0:
        errors.append("events.jsonl: finalized trial has unresolved request-start events")
    return str(trial_status)


def _trial_report(batch: PreregisteredBatch, spec: TrialSpec) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    trial_dir = batch.trial_dir(spec)
    report: dict[str, Any] = {
        "trial_id": spec.trial_id,
        "trial_storage_id": spec.storage_id,
        "variant": spec.variant,
    }
    if not trial_dir.exists():
        report["evidence_state"] = "NOT_OPENED"
        return report, errors
    if not trial_dir.is_dir() or trial_dir.is_symlink():
        report["evidence_state"] = "INVALID"
        errors.append("trial directory: missing or unsafe")
        return report, errors

    for child in trial_dir.iterdir():
        if child.name not in _ALLOWED_TRIAL_CHILDREN:
            errors.append(f"trial directory: unexpected artifact {child.name!r}")
    if not (trial_dir / "target").is_dir() or (trial_dir / "target").is_symlink():
        errors.append("trial directory: missing or unsafe synthetic target")

    trial = _read_object(trial_dir / "trial.json", label="trial.json", errors=errors)
    if trial is not None:
        _verify_trial_identity(trial, batch=batch, spec=spec, errors=errors)
    events = _read_events(trial_dir / "events.jsonl", errors=errors)
    report.update(events)

    final_artifact_count = sum((trial_dir / filename).exists() for filename in _FINAL_ARTIFACTS)
    if final_artifact_count:
        if final_artifact_count != len(_FINAL_ARTIFACTS):
            errors.append("trial directory: final evidence artifacts are incomplete")
            report["evidence_state"] = "INVALID"
            return report, errors
        trial_status = _verify_final_artifacts(
            trial_dir,
            batch=batch,
            spec=spec,
            events=events,
            errors=errors,
        )
        report["evidence_state"] = trial_status or "INVALID"
        return report, errors

    if events["api_request_started_count"]:
        report["evidence_state"] = "INTERRUPTED_STOP_REQUIRED"
        report["request_outcome"] = "UNKNOWN"
    else:
        report["evidence_state"] = "OPENED_NOT_FINALIZED"
    return report, errors


def _driver_registration(batch: PreregisteredBatch) -> dict[str, Any]:
    """Load the immutable PRT-003 registration without exposing raw request data."""

    path = batch.batch_dir / DRIVER_REGISTRATION_FILENAME
    try:
        registration = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceValidationError("driver registration is unreadable") from exc
    if not isinstance(registration, dict):
        raise EvidenceValidationError("driver registration must be a JSON object")

    candidate = dict(registration)
    recorded_digest = candidate.pop("registration_digest", None)
    if not isinstance(recorded_digest, str) or recorded_digest != digest(candidate):
        raise EvidenceValidationError("driver registration digest does not match immutable contents")
    if registration.get("batch_id") != batch.batch_id:
        raise EvidenceValidationError("driver registration belongs to a different batch")
    if registration.get("batch_preregistration_digest") != batch.preregistration_digest:
        raise EvidenceValidationError("driver registration does not match batch preregistration")
    return registration


def _interrupted_trial_records(
    batch: PreregisteredBatch,
    trial_reports: list[Mapping[str, Any]],
    *,
    errors: list[str],
) -> list[dict[str, Any]]:
    """Freeze only safe facts about hard-stopped trials, never request contents."""

    records: list[dict[str, Any]] = []
    for report in trial_reports:
        if report.get("evidence_state") != "INTERRUPTED_STOP_REQUIRED":
            continue
        storage_id = report.get("trial_storage_id")
        if not isinstance(storage_id, str):
            errors.append("interruption disposition: interrupted trial has no safe storage ID")
            continue
        journal_path = batch.batch_dir / "trials" / storage_id / "events.jsonl"
        if not journal_path.is_file() or journal_path.is_symlink():
            errors.append("interruption disposition: interrupted trial journal is missing or unsafe")
            continue
        records.append(
            {
                "trial_id": report.get("trial_id"),
                "trial_storage_id": storage_id,
                "variant": report.get("variant"),
                "event_journal_status": report.get("event_journal_status"),
                "request_outcome": report.get("request_outcome"),
                "api_request_started_count": report.get("api_request_started_count"),
                "api_response_observed_count": report.get("api_response_observed_count"),
                "api_request_incomplete_count": report.get("api_request_incomplete_count"),
                "unresolved_request_starts": report.get("unresolved_request_starts"),
                "request_journal_sha256": _file_sha256(journal_path),
            }
        )
    return records


def _pilot_scope(batch: PreregisteredBatch, registration: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact safe scope a future disposable pilot must keep frozen."""

    if not batch.trial_specs:
        raise EvidenceValidationError("batch has no pre-registered trial to freeze")
    registration_digest = registration.get("registration_digest")
    model_config = registration.get("model_config")
    live_guard = registration.get("live_run_guard")
    if not isinstance(registration_digest, str):
        raise EvidenceValidationError("driver registration has no immutable digest")
    if not isinstance(model_config, Mapping) or not isinstance(live_guard, Mapping):
        raise EvidenceValidationError("driver registration has no safe fixed pilot configuration")

    return {
        "scope_kind": "pre-registered-disposable-synthetic-pilot",
        "verification_scope": batch.manifest.get("verification_scope"),
        "batch_id": batch.batch_id,
        "batch_preregistration_digest": batch.preregistration_digest,
        "driver_registration_digest": registration_digest,
        "driver_version": registration.get("driver_version"),
        "model_config": dict(model_config),
        "scheduled_trials": [
            {
                "trial_id": spec.trial_id,
                "trial_storage_id": spec.storage_id,
                "ordinal": spec.ordinal,
                "variant": spec.variant,
                "trial_spec_digest": digest(spec.as_dict()),
            }
            for spec in batch.trial_specs
        ],
        "request_limits": {
            "max_api_trials": len(batch.trial_specs),
            "max_model_turns": live_guard.get("max_model_turns"),
            "max_output_tokens_per_turn": live_guard.get("max_output_tokens_per_turn"),
        },
        "prohibitions": {
            "canonical_run_authorized": False,
            "retry_permitted": False,
            "resume_permitted": False,
        },
    }


def create_interruption_disposition(batch_dir: Path) -> dict[str, Any]:
    """Write one immutable STOP record for a hard crash; it cannot finalize a trial."""

    batch = load_api_batch(Path(batch_dir))
    report = validate_external_batch(batch.batch_dir)
    if report.get("validation_status") != "STOP_REQUIRED":
        raise EvidenceValidationError(
            "an interruption disposition requires a verified hard-stop external batch"
        )
    trial_reports = report.get("trials")
    if not isinstance(trial_reports, list):
        raise EvidenceValidationError("validated batch did not expose safe trial reports")
    errors: list[str] = []
    interrupted_trials = _interrupted_trial_records(batch, trial_reports, errors=errors)
    if errors or not interrupted_trials:
        raise EvidenceValidationError(
            "an interruption disposition requires a readable request-started crash record"
        )

    disposition: dict[str, Any] = {
        "artifact_kind": INTERRUPTION_DISPOSITION_KIND,
        "evidence_status": EVIDENCE_STATUS,
        "recorded_at": now_iso(),
        "batch_id": batch.batch_id,
        "batch_preregistration_digest": batch.preregistration_digest,
        "source_validation_status": "STOP_REQUIRED",
        "disposition": "PRESERVE_STOPPED_NOT_A_FINAL_RECEIPT",
        "acceptance_status": "NOT_ACCEPTED",
        "retry_permitted": False,
        "resume_permitted": False,
        "live_run_authorized": False,
        "canonical_run_authorized": False,
        "network_performed": False,
        "interrupted_trials": interrupted_trials,
    }
    disposition["disposition_digest"] = digest(disposition)
    _write_json_new(batch.batch_dir / INTERRUPTION_DISPOSITION_FILENAME, disposition)
    return disposition


def create_pilot_approval_proof(
    batch_dir: Path,
    *,
    approval_reference: str,
) -> dict[str, Any]:
    """Freeze one future pilot scope without authorising an API request."""

    batch = load_api_batch(Path(batch_dir))
    initial_report = validate_external_batch(batch.batch_dir)
    if initial_report.get("validation_status") != "ACTIVE_NOT_ARCHIVABLE":
        raise EvidenceValidationError(
            "pilot approval proof requires a verified active external batch before any request"
        )
    if any(batch.trial_dir(spec).exists() for spec in batch.trial_specs):
        raise EvidenceValidationError(
            "pilot approval proof must be created before any pre-registered trial opens"
        )
    registration = _driver_registration(batch)
    proof: dict[str, Any] = {
        "artifact_kind": PILOT_APPROVAL_PROOF_KIND,
        "evidence_status": EVIDENCE_STATUS,
        "created_at": now_iso(),
        "approval_reference": _require_opaque_approval_reference(approval_reference),
        "approval_status": "SCOPE_FROZEN_NOT_A_LIVE_AUTHORIZATION",
        "separate_explicit_live_authorization_required": True,
        "network_performed": False,
        "pilot_scope": _pilot_scope(batch, registration),
    }
    proof["proof_digest"] = digest(proof)
    _write_json_new(batch.batch_dir / PILOT_APPROVAL_PROOF_FILENAME, proof)
    return proof


def require_valid_pilot_approval_proof(batch_dir: Path) -> None:
    """Require a frozen scope proof before the CLI can reach a live transport."""

    report = validate_external_batch(Path(batch_dir))
    if report.get("validation_status") != "ACTIVE_NOT_ARCHIVABLE":
        raise EvidenceValidationError(
            "a live pilot requires an active, non-interrupted external batch"
        )
    if report.get("pilot_approval_proof_status") != "VALID":
        raise EvidenceValidationError(
            "a valid immutable pilot approval proof is required before a live API request"
        )


def _validate_interruption_disposition(
    batch: PreregisteredBatch,
    trial_reports: list[Mapping[str, Any]],
    *,
    errors: list[str],
) -> str:
    """Check a disposition against the still-preserved interrupted evidence."""

    path = batch.batch_dir / INTERRUPTION_DISPOSITION_FILENAME
    if not path.exists():
        return "ABSENT"
    initial_error_count = len(errors)
    disposition = _read_object(path, label=INTERRUPTION_DISPOSITION_FILENAME, errors=errors)
    if disposition is None:
        return "INVALID"

    candidate = dict(disposition)
    recorded_digest = candidate.pop("disposition_digest", None)
    if not isinstance(recorded_digest, str) or recorded_digest != digest(candidate):
        errors.append("interruption disposition: digest does not match immutable contents")
    expected_records = _interrupted_trial_records(batch, trial_reports, errors=errors)
    if not expected_records:
        errors.append("interruption disposition: no current hard-stopped trial matches the record")
    if disposition.get("artifact_kind") != INTERRUPTION_DISPOSITION_KIND:
        errors.append("interruption disposition: wrong artifact kind")
    if disposition.get("evidence_status") != EVIDENCE_STATUS:
        errors.append("interruption disposition: wrong evidence status")
    if disposition.get("batch_id") != batch.batch_id:
        errors.append("interruption disposition: batch ID does not match batch.json")
    if disposition.get("batch_preregistration_digest") != batch.preregistration_digest:
        errors.append("interruption disposition: preregistration digest does not match batch.json")
    if disposition.get("source_validation_status") != "STOP_REQUIRED":
        errors.append("interruption disposition: source validation must remain STOP_REQUIRED")
    if disposition.get("disposition") != "PRESERVE_STOPPED_NOT_A_FINAL_RECEIPT":
        errors.append("interruption disposition: must preserve the stop without finalizing a receipt")
    if disposition.get("acceptance_status") != "NOT_ACCEPTED":
        errors.append("interruption disposition: acceptance must remain NOT_ACCEPTED")
    for field in (
        "retry_permitted",
        "resume_permitted",
        "live_run_authorized",
        "canonical_run_authorized",
        "network_performed",
    ):
        if disposition.get(field) is not False:
            errors.append(f"interruption disposition: {field} must remain false")
    if disposition.get("interrupted_trials") != expected_records:
        errors.append("interruption disposition: interrupted trial facts no longer match preserved evidence")
    return "VALID" if len(errors) == initial_error_count else "INVALID"


def _validate_pilot_approval_proof(
    batch: PreregisteredBatch,
    *,
    errors: list[str],
) -> str:
    """Check that a future-pilot scope proof is immutable and non-authorising."""

    path = batch.batch_dir / PILOT_APPROVAL_PROOF_FILENAME
    if not path.exists():
        return "ABSENT"
    initial_error_count = len(errors)
    proof = _read_object(path, label=PILOT_APPROVAL_PROOF_FILENAME, errors=errors)
    if proof is None:
        return "INVALID"

    candidate = dict(proof)
    recorded_digest = candidate.pop("proof_digest", None)
    if not isinstance(recorded_digest, str) or recorded_digest != digest(candidate):
        errors.append("pilot approval proof: digest does not match immutable contents")
    if proof.get("artifact_kind") != PILOT_APPROVAL_PROOF_KIND:
        errors.append("pilot approval proof: wrong artifact kind")
    if proof.get("evidence_status") != EVIDENCE_STATUS:
        errors.append("pilot approval proof: wrong evidence status")
    try:
        expected_scope = _pilot_scope(batch, _driver_registration(batch))
    except EvidenceValidationError as exc:
        errors.append(f"pilot approval proof: {exc}")
        expected_scope = None
    try:
        _require_opaque_approval_reference(proof.get("approval_reference"))
    except EvidenceValidationError:
        errors.append("pilot approval proof: approval reference is not a safe opaque identifier")
    if proof.get("approval_status") != "SCOPE_FROZEN_NOT_A_LIVE_AUTHORIZATION":
        errors.append("pilot approval proof: must not claim live authorization")
    if proof.get("separate_explicit_live_authorization_required") is not True:
        errors.append("pilot approval proof: separate live authorization must remain required")
    if proof.get("network_performed") is not False:
        errors.append("pilot approval proof: network_performed must remain false")
    if expected_scope is not None and proof.get("pilot_scope") != expected_scope:
        errors.append("pilot approval proof: frozen scope does not match the registered batch")
    return "VALID" if len(errors) == initial_error_count else "INVALID"


def _safe_manifest_path(batch_dir: Path, raw_path: object, *, errors: list[str]) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
        errors.append("evidence manifest: artifact path must be a safe relative POSIX path")
        return None
    candidate = PurePosixPath(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        errors.append("evidence manifest: artifact path must remain inside the batch")
        return None
    unresolved = batch_dir
    for part in candidate.parts:
        unresolved = unresolved / part
        if unresolved.is_symlink():
            errors.append("evidence manifest: artifact may not be a symlink")
            return None
    resolved = unresolved.resolve()
    root = batch_dir.resolve()
    if root not in resolved.parents:
        errors.append("evidence manifest: artifact path escapes the batch")
        return None
    return resolved


def _expected_archive_paths(batch: PreregisteredBatch) -> list[str]:
    paths = ["batch.json", DRIVER_REGISTRATION_FILENAME]
    if (batch.batch_dir / PILOT_APPROVAL_PROOF_FILENAME).is_file():
        paths.append(PILOT_APPROVAL_PROOF_FILENAME)
    for spec in batch.trial_specs:
        trial_root = f"trials/{spec.storage_id}"
        paths.extend(f"{trial_root}/{filename}" for filename in ("trial.json", "events.jsonl", *_FINAL_ARTIFACTS))
    return paths


def _validate_existing_manifest(
    batch: PreregisteredBatch,
    *,
    errors: list[str],
) -> str:
    path = batch.batch_dir / EVIDENCE_MANIFEST_FILENAME
    if not path.exists():
        return "ABSENT"
    manifest = _read_object(path, label=EVIDENCE_MANIFEST_FILENAME, errors=errors)
    if manifest is None:
        return "INVALID"
    candidate = dict(manifest)
    recorded_digest = candidate.pop("manifest_digest", None)
    if not isinstance(recorded_digest, str) or recorded_digest != digest(candidate):
        errors.append("evidence manifest: digest does not match immutable contents")
    if manifest.get("artifact_kind") != EVIDENCE_MANIFEST_KIND:
        errors.append("evidence manifest: wrong artifact kind")
    if manifest.get("evidence_status") != EVIDENCE_STATUS:
        errors.append("evidence manifest: wrong evidence status")
    if manifest.get("batch_id") != batch.batch_id:
        errors.append("evidence manifest: batch ID does not match batch.json")
    if manifest.get("batch_preregistration_digest") != batch.preregistration_digest:
        errors.append("evidence manifest: preregistration digest does not match batch.json")
    if manifest.get("archive_status") != "TERMINAL_NONCANONICAL_BATCH":
        errors.append("evidence manifest: archive status is not terminal noncanonical")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("evidence manifest: artifacts must be a list")
        return "INVALID"
    expected_paths = set(_expected_archive_paths(batch))
    recorded_paths: set[str] = set()
    for entry in artifacts:
        if not isinstance(entry, Mapping):
            errors.append("evidence manifest: artifact entry must be an object")
            continue
        raw_path = entry.get("path")
        artifact_path = _safe_manifest_path(batch.batch_dir, raw_path, errors=errors)
        if isinstance(raw_path, str):
            if raw_path in recorded_paths:
                errors.append("evidence manifest: duplicate artifact path")
            recorded_paths.add(raw_path)
        if artifact_path is None or not artifact_path.is_file():
            errors.append("evidence manifest: declared artifact is missing")
            continue
        recorded_hash = entry.get("sha256")
        if not isinstance(recorded_hash, str) or recorded_hash != _file_sha256(artifact_path):
            errors.append("evidence manifest: artifact digest does not match")
    if recorded_paths != expected_paths:
        errors.append("evidence manifest: declared artifact inventory does not match terminal batch contract")
    return "VALID" if not errors else "INVALID"


def validate_external_batch(batch_dir: Path) -> dict[str, Any]:
    """Read and classify one external PRT-003 batch without mutating it.

    ``ARCHIVED_VALID`` is the only green result.  A merely active batch is not
    an archive, and an interrupted batch is deliberately a STOP rather than an
    error that an operator should repair or retry.
    """

    try:
        batch = load_api_batch(Path(batch_dir))
    except Exception:
        return {
            "artifact_kind": "noncanonical-api-driver-evidence-validation-report",
            "evidence_status": EVIDENCE_STATUS,
            "validation_status": "INVALID",
            "network_performed": False,
            "mutation_performed": False,
            "archive_permitted": False,
            "errors": ["batch registration could not be verified"],
            "next_safe_action": "STOP_AND_REVIEW_EXTERNAL_BATCH",
        }

    errors: list[str] = []
    batch_manifest = _read_object(batch.batch_dir / "batch.json", label="batch.json", errors=errors)
    registration = _read_object(
        batch.batch_dir / DRIVER_REGISTRATION_FILENAME,
        label=DRIVER_REGISTRATION_FILENAME,
        errors=errors,
    )
    if batch_manifest is not None and batch_manifest.get("artifact_kind") != "noncanonical-preregistered-abc-batch":
        errors.append("batch.json: wrong artifact kind")
    if batch_manifest is not None and batch_manifest.get("batch_mode") == DISPOSABLE_SINGLE_TRIAL_MODE:
        specs = batch.trial_specs
        if len(specs) != 1 or specs[0].variant != "C":
            errors.append("batch.json: disposable pilot must freeze exactly one Variant-C trial")
    if batch_manifest is not None and batch_manifest.get("evidence_status") != EVIDENCE_STATUS:
        errors.append("batch.json: wrong evidence status")
    if registration is not None and registration.get("artifact_kind") != "noncanonical-api-driver-registration":
        errors.append(f"{DRIVER_REGISTRATION_FILENAME}: wrong artifact kind")
    if registration is not None and registration.get("evidence_status") != EVIDENCE_STATUS:
        errors.append(f"{DRIVER_REGISTRATION_FILENAME}: wrong evidence status")
    if registration is not None and registration.get("driver_version") != DRIVER_VERSION:
        errors.append(f"{DRIVER_REGISTRATION_FILENAME}: wrong driver version")
    allowed_root_children = {
        "batch.json",
        DRIVER_REGISTRATION_FILENAME,
        "trials",
        EVIDENCE_MANIFEST_FILENAME,
        INTERRUPTION_DISPOSITION_FILENAME,
        PILOT_APPROVAL_PROOF_FILENAME,
    }
    for child in batch.batch_dir.iterdir():
        if child.name not in allowed_root_children:
            errors.append(f"batch directory: unexpected artifact {child.name!r}")
    trials_root = batch.batch_dir / "trials"
    known_storage_ids = {spec.storage_id for spec in batch.trial_specs}
    if trials_root.exists():
        if not trials_root.is_dir() or trials_root.is_symlink():
            errors.append("batch directory: trials location is unsafe")
        else:
            for child in trials_root.iterdir():
                if child.name not in known_storage_ids:
                    errors.append(f"batch directory: unknown trial artifact {child.name!r}")

    trial_reports: list[dict[str, Any]] = []
    for spec in batch.trial_specs:
        report, trial_errors = _trial_report(batch, spec)
        trial_reports.append(report)
        errors.extend(f"{spec.storage_id}: {error}" for error in trial_errors)

    states = {str(trial["evidence_state"]) for trial in trial_reports}
    interruption_disposition_status = _validate_interruption_disposition(
        batch,
        trial_reports,
        errors=errors,
    )
    pilot_approval_proof_status = _validate_pilot_approval_proof(batch, errors=errors)
    manifest_status = _validate_existing_manifest(batch, errors=errors)
    if errors:
        validation_status = "INVALID"
        next_safe_action = "STOP_AND_REVIEW_EXTERNAL_BATCH"
    elif "INTERRUPTED_STOP_REQUIRED" in states or "OPENED_NOT_FINALIZED" in states:
        validation_status = "STOP_REQUIRED"
        next_safe_action = "DO_NOT_RETRY_OR_RESUME"
    elif "NOT_OPENED" in states:
        validation_status = "ACTIVE_NOT_ARCHIVABLE"
        next_safe_action = "COMPLETE_OR_EXPLICITLY_STOP_EVERY_PREREGISTERED_TRIAL"
    elif manifest_status == "VALID":
        validation_status = "ARCHIVED_VALID"
        next_safe_action = "PRESERVE_EXTERNAL_NONCANONICAL_ARCHIVE"
    else:
        validation_status = "ARCHIVE_READY"
        next_safe_action = "OPTIONALLY_CREATE_IMMUTABLE_EVIDENCE_MANIFEST"

    return {
        "artifact_kind": "noncanonical-api-driver-evidence-validation-report",
        "evidence_status": EVIDENCE_STATUS,
        "batch_id": batch.batch_id,
        "batch_preregistration_digest": batch.preregistration_digest,
        "validation_status": validation_status,
        "archive_manifest_status": manifest_status,
        "interruption_disposition_status": interruption_disposition_status,
        "pilot_approval_proof_status": pilot_approval_proof_status,
        "archive_permitted": validation_status == "ARCHIVE_READY",
        "network_performed": False,
        "mutation_performed": False,
        "trials": trial_reports,
        "errors": errors,
        "next_safe_action": next_safe_action,
    }


def _write_json_new(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically create one immutable external evidence artifact."""

    if path.exists():
        raise EvidenceValidationError(
            f"immutable evidence artifact already exists and may not be overwritten: {path.name}"
        )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        prefix=".tmp.",
        suffix=".tmp",
    ) as temporary:
        json.dump(value, temporary, ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)
    try:
        if path.exists():
            raise EvidenceValidationError(
                f"immutable evidence artifact already exists and may not be overwritten: {path.name}"
            )
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def archive_external_batch(batch_dir: Path) -> dict[str, Any]:
    """Write one immutable manifest for a terminal, already-validated batch.

    This is not a recovery action and never writes a result/receipt for an
    interrupted trial.  It exists only to bind approved external artifacts by
    content digest after the batch is terminal.
    """

    report = validate_external_batch(Path(batch_dir))
    if report.get("validation_status") != "ARCHIVE_READY":
        raise EvidenceValidationError(
            "external batch is not archive-ready; do not repair, retry, or resume it"
        )
    batch = load_api_batch(Path(batch_dir))
    artifact_paths = _expected_archive_paths(batch)
    artifacts = [
        {"path": relative_path, "sha256": _file_sha256(batch.batch_dir / relative_path)}
        for relative_path in artifact_paths
    ]
    manifest: dict[str, Any] = {
        "artifact_kind": EVIDENCE_MANIFEST_KIND,
        "evidence_status": EVIDENCE_STATUS,
        "driver_version": DRIVER_VERSION,
        "archived_at": now_iso(),
        "archive_status": "TERMINAL_NONCANONICAL_BATCH",
        "batch_id": batch.batch_id,
        "batch_preregistration_digest": batch.preregistration_digest,
        "trial_count": len(batch.trial_specs),
        "artifacts": artifacts,
    }
    manifest["manifest_digest"] = digest(manifest)
    _write_json_new(batch.batch_dir / EVIDENCE_MANIFEST_FILENAME, manifest)
    return manifest
