"""Minimal EXP-001 canonical promotion boundary."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping

import jsonschema

from prototypes.prt001_controlled_quicksave.common import digest

from .canonical_source import (
    CANONICAL_PROMOTION_SOURCE_FILENAME,
    CANONICAL_PROMOTION_SOURCE_KIND,
)
from .evidence import validate_external_batch
from .exp001_api_driver import load_exp001_api_batch


class CanonicalPromotionError(RuntimeError):
    pass


_RUN_ID_RE = re.compile(r"RUN-[0-9]{3,}\Z")
_APPROVAL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")

_CODING_PROFILE_DIGEST_FIELDS = (
    "mapping_contract_sha256",
    "metric_contract_sha256",
    "builder_source_sha256",
)

_CODING_PROFILE_VERSION_FIELDS = (
    "harness_version",
    "driver_version",
    "verifier_version",
)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _schema_path() -> Path:
    return _repository_root() / "schemas" / "run.schema.json"


def _require_run_id(value: object) -> str:
    if not isinstance(value, str) or not _RUN_ID_RE.fullmatch(value):
        raise CanonicalPromotionError(
            "run_id must match RUN-[0-9]{3,}"
        )
    if value == "RUN-000":
        raise CanonicalPromotionError(
            "RUN-000 is permanently reserved"
        )
    return value


def _require_approval_reference(value: object) -> str:
    if not isinstance(value, str) or not _APPROVAL_RE.fullmatch(value):
        raise CanonicalPromotionError(
            "approval_reference must be a short opaque identifier"
        )
    return value


def _require_source(preview: Mapping[str, Any]) -> dict[str, str]:
    source = preview.get("source")
    if not isinstance(source, Mapping):
        raise CanonicalPromotionError("preview source is missing")

    batch_id = source.get("batch_id")
    trial_id = source.get("trial_id")

    if not isinstance(batch_id, str) or not batch_id:
        raise CanonicalPromotionError("source batch_id is missing")
    if not isinstance(trial_id, str) or not trial_id:
        raise CanonicalPromotionError("source trial_id is missing")

    return {
        "batch_id": batch_id,
        "trial_id": trial_id,
    }


def _require_coding_profile(
    preview: Mapping[str, Any],
) -> dict[str, str]:
    profile = preview.get("coding_profile")
    if not isinstance(profile, Mapping):
        raise CanonicalPromotionError("coding_profile is missing")

    result: dict[str, str] = {}

    for field in _CODING_PROFILE_DIGEST_FIELDS:
        value = profile.get(field)
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            raise CanonicalPromotionError(
                f"coding_profile {field} must be a SHA-256 digest"
            )
        result[field] = value

    for field in _CODING_PROFILE_VERSION_FIELDS:
        value = profile.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CanonicalPromotionError(
                f"coding_profile {field} must be recorded"
            )
        result[field] = value

    return result


def _validate_candidate(candidate: Mapping[str, Any]) -> None:
    try:
        schema = json.loads(
            _schema_path().read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalPromotionError(
            "canonical RUN schema could not be loaded"
        ) from exc

    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    errors = sorted(validator.iter_errors(dict(candidate)), key=str)
    if errors:
        raise CanonicalPromotionError(
            "candidate does not satisfy canonical RUN schema: "
            + "; ".join(error.message for error in errors)
        )


def _validated_preview(
    preview: Mapping[str, Any],
) -> tuple[
    dict[str, str],
    str,
    dict[str, Any],
    str,
    dict[str, str],
]:
    if not isinstance(preview, Mapping):
        raise CanonicalPromotionError("preview must be an object")

    if preview.get("artifact_kind") != "canonical-run-candidate-preview-v1":
        raise CanonicalPromotionError("unexpected candidate preview kind")

    source = _require_source(preview)
    run_id = _require_run_id(preview.get("run_id"))

    candidate = preview.get("candidate")
    if not isinstance(candidate, Mapping):
        raise CanonicalPromotionError("candidate is missing")

    candidate = dict(candidate)

    if candidate.get("run_id") != run_id:
        raise CanonicalPromotionError(
            "candidate run_id conflicts with preview"
        )

    candidate_digest = preview.get("candidate_digest")
    if (
        not isinstance(candidate_digest, str)
        or not _SHA256_RE.fullmatch(candidate_digest)
        or candidate_digest != digest(candidate)
    ):
        raise CanonicalPromotionError(
            "candidate digest does not match exact candidate"
        )

    coding_profile = _require_coding_profile(preview)
    _validate_candidate(candidate)

    return (
        source,
        run_id,
        candidate,
        candidate_digest,
        coding_profile,
    )


def approval_path(
    runs_root: Path,
    *,
    source_batch_id: str,
    source_trial_id: str,
) -> Path:
    if not source_batch_id or not source_trial_id:
        raise CanonicalPromotionError("source identity is incomplete")

    source_key = digest(
        {
            "source_batch_id": source_batch_id,
            "source_trial_id": source_trial_id,
        }
    )

    return (
        Path(runs_root).expanduser().resolve()
        / ".promotion-approvals"
        / f"SOURCE-{source_key}.json"
    )


def _write_json_new(
    path: Path,
    value: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.parent.is_symlink():
        raise CanonicalPromotionError(
            "refusing unsafe promotion directory"
        )

    if path.exists() or path.is_symlink():
        raise CanonicalPromotionError(
            f"refusing to overwrite existing artifact: {path.name}"
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
        try:
            os.link(temporary_path, path)
        except FileExistsError as exc:
            raise CanonicalPromotionError(
                f"refusing to overwrite existing artifact: {path.name}"
            ) from exc
    finally:
        temporary_path.unlink(missing_ok=True)


def _read_object(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise CanonicalPromotionError(
            "approval proof is missing or unsafe"
        )

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CanonicalPromotionError(
            "approval proof is invalid"
        ) from exc

    if not isinstance(value, dict):
        raise CanonicalPromotionError(
            "approval proof must contain an object"
        )

    return value


def _create_promotion_approval_from_preview(
    preview,
    *,
    approval_reference: str,
    runs_root: Path,
):
    (
        source,
        run_id,
        _candidate,
        candidate_digest,
        coding_profile,
    ) = _validated_preview(preview)

    approval_reference = _require_approval_reference(
        approval_reference
    )

    proof: dict[str, Any] = {
        "artifact_kind": "canonical-promotion-approval-v1",
        "approval_status": "APPROVED_FOR_EXACT_CANDIDATE",
        "approval_reference": approval_reference,
        "source": source,
        "run_id": run_id,
        "candidate_digest": candidate_digest,
        "coding_profile": coding_profile,
    }
    proof["proof_digest"] = digest(proof)

    path = approval_path(
        runs_root,
        source_batch_id=source["batch_id"],
        source_trial_id=source["trial_id"],
    )

    _write_json_new(path, proof)

    return {
        "proof": proof,
        "approval_path": str(path),
    }


def create_promotion_approval(
    batch_dir: Path,
    *,
    trial_id: str,
    run_id: str,
    approved_candidate_digest: str,
    approval_reference: str,
    runs_root: Path,
):
    if (
        not isinstance(approved_candidate_digest, str)
        or not _SHA256_RE.fullmatch(approved_candidate_digest)
    ):
        raise CanonicalPromotionError(
            "approved candidate digest must be a SHA-256 digest"
        )

    preview = build_canonical_candidate_preview(
        batch_dir,
        trial_id=trial_id,
        proposed_run_id=run_id,
    )

    if preview["candidate_digest"] != approved_candidate_digest:
        raise CanonicalPromotionError(
            "approved candidate digest no longer matches archived evidence"
        )

    return _create_promotion_approval_from_preview(
        preview,
        approval_reference=approval_reference,
        runs_root=runs_root,
    )


def _validated_approval(
    path: Path,
) -> dict[str, Any]:
    proof = _read_object(path)

    if proof.get("artifact_kind") != "canonical-promotion-approval-v1":
        raise CanonicalPromotionError(
            "unexpected approval proof kind"
        )

    recorded_digest = proof.get("proof_digest")
    unsigned = dict(proof)
    unsigned.pop("proof_digest", None)

    if (
        not isinstance(recorded_digest, str)
        or not _SHA256_RE.fullmatch(recorded_digest)
        or recorded_digest != digest(unsigned)
    ):
        raise CanonicalPromotionError(
            "approval proof digest is invalid"
        )

    _require_approval_reference(
        proof.get("approval_reference")
    )

    if proof.get("approval_status") != "APPROVED_FOR_EXACT_CANDIDATE":
        raise CanonicalPromotionError(
            "approval proof is not active"
        )

    return proof


def _promote_approved_candidate_from_preview(
    preview,
    *,
    approval_file: Path,
    runs_root: Path,
):
    (
        source,
        run_id,
        candidate,
        candidate_digest,
        coding_profile,
    ) = _validated_preview(preview)

    expected_approval = approval_path(
        runs_root,
        source_batch_id=source["batch_id"],
        source_trial_id=source["trial_id"],
    )

    supplied_approval = Path(approval_file).expanduser().resolve()
    if supplied_approval != expected_approval:
        raise CanonicalPromotionError(
            "approval proof does not belong to this source trial"
        )

    proof = _validated_approval(supplied_approval)

    expected_binding = {
        "source": source,
        "run_id": run_id,
        "candidate_digest": candidate_digest,
        "coding_profile": coding_profile,
    }

    for field, expected in expected_binding.items():
        if proof.get(field) != expected:
            raise CanonicalPromotionError(
                f"approval proof no longer matches {field}"
            )

    runs_root = Path(runs_root).expanduser().resolve()
    destination = runs_root / f"{run_id}.json"

    _write_json_new(destination, candidate)

    written = _read_object(destination)
    _validate_candidate(written)

    if digest(written) != candidate_digest:
        raise CanonicalPromotionError(
            "written canonical RUN digest changed"
        )

    return {
        "promotion_status": "PROMOTED_EXACTLY_ONCE",
        "run_id": run_id,
        "source": source,
        "candidate_digest": candidate_digest,
        "approval_reference": proof["approval_reference"],
        "output_path": str(destination),
    }


def build_canonical_candidate_preview(
    batch_dir: Path,
    *,
    trial_id: str,
    proposed_run_id: str,
):
    run_id = _require_run_id(proposed_run_id)
    batch_dir = Path(batch_dir).expanduser().resolve()

    report = validate_external_batch(batch_dir)
    if report.get("validation_status") != "ARCHIVED_VALID":
        raise CanonicalPromotionError(
            "canonical preview requires ARCHIVED_VALID evidence"
        )

    try:
        batch = load_exp001_api_batch(batch_dir)
    except Exception as exc:
        raise CanonicalPromotionError(
            "archived batch is not the frozen EXP-001 research cycle"
        ) from exc

    if not isinstance(trial_id, str) or not trial_id:
        raise CanonicalPromotionError(
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
        raise CanonicalPromotionError(
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
        raise CanonicalPromotionError(
            "archive validation report lacks the requested trial"
        )

    if report_trial.get("evidence_state") not in {
        "COMPLETE",
        "INCOMPLETE",
    }:
        raise CanonicalPromotionError(
            "requested trial is not terminal archived evidence"
        )

    if report_trial.get("api_request_incomplete_count", 0):
        raise CanonicalPromotionError(
            "ambiguous request outcome is not promotable"
        )

    packet_path = (
        batch.trial_dir(spec)
        / CANONICAL_PROMOTION_SOURCE_FILENAME
    )
    packet = _read_object(packet_path)

    if packet.get("artifact_kind") != CANONICAL_PROMOTION_SOURCE_KIND:
        raise CanonicalPromotionError(
            "unexpected canonical promotion source kind"
        )

    recorded_packet_digest = packet.get("packet_digest")
    unsigned_packet = dict(packet)
    unsigned_packet.pop("packet_digest", None)

    if (
        not isinstance(recorded_packet_digest, str)
        or not _SHA256_RE.fullmatch(recorded_packet_digest)
        or recorded_packet_digest != digest(unsigned_packet)
    ):
        raise CanonicalPromotionError(
            "canonical promotion source digest is invalid"
        )

    expected_source = {
        "batch_id": batch.batch_id,
        "trial_id": spec.trial_id,
    }
    if packet.get("source") != expected_source:
        raise CanonicalPromotionError(
            "canonical promotion source identity is inconsistent"
        )

    source_evidence = packet.get("source_evidence")
    if not isinstance(source_evidence, Mapping):
        raise CanonicalPromotionError(
            "canonical promotion source evidence binding is missing"
        )

    if (
        source_evidence.get("batch_preregistration_digest")
        != batch.preregistration_digest
    ):
        raise CanonicalPromotionError(
            "promotion source batch digest is inconsistent"
        )

    if (
        source_evidence.get("trial_spec_digest")
        != digest(spec.as_dict())
    ):
        raise CanonicalPromotionError(
            "promotion source trial digest is inconsistent"
        )

    canonical_fields = packet.get("canonical_fields")
    if not isinstance(canonical_fields, Mapping):
        raise CanonicalPromotionError(
            "canonical promotion source fields are missing"
        )

    if "run_id" in canonical_fields:
        raise CanonicalPromotionError(
            "source packet may not preassign a canonical RUN ID"
        )

    coding_profile = _require_coding_profile(
        {"coding_profile": packet.get("coding_profile")}
    )

    candidate = dict(canonical_fields)
    candidate["run_id"] = run_id
    _validate_candidate(candidate)

    return {
        "artifact_kind": "canonical-run-candidate-preview-v1",
        "source": expected_source,
        "run_id": run_id,
        "candidate": candidate,
        "candidate_digest": digest(candidate),
        "coding_profile": coding_profile,
        "promotion_authorized": False,
        "network_performed": False,
        "mutation_performed": False,
    }


def promote_approved_candidate(
    batch_dir: Path,
    *,
    trial_id: str,
    run_id: str,
    approval_file: Path,
    runs_root: Path,
):
    preview = build_canonical_candidate_preview(
        batch_dir,
        trial_id=trial_id,
        proposed_run_id=run_id,
    )

    return _promote_approved_candidate_from_preview(
        preview,
        approval_file=approval_file,
        runs_root=runs_root,
    )
