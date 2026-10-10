"""Freeze canonical EXP-001 coding at trial finalization."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from prototypes.prt001_controlled_quicksave.common import digest
from prototypes.prt001_controlled_quicksave.verifier import (
    IndependentQuicksaveVerifier,
)

from .harness import HARNESS_VERSION


CANONICAL_PROMOTION_SOURCE_FILENAME = "canonical-promotion-source.json"
CANONICAL_PROMOTION_SOURCE_KIND = "canonical-promotion-source-v1"


class CanonicalSourceError(RuntimeError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _events(path: Path) -> list[dict[str, Any]]:
    result = []
    with path.open(encoding="utf-8") as journal:
        for line in journal:
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise CanonicalSourceError("event journal contains a non-object")
            result.append(event)
    return result


def _run_date(events: list[Mapping[str, Any]]) -> str:
    for event in events:
        if event.get("event_type") != "trial_started":
            continue
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, str):
            break
        try:
            return datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            ).date().isoformat()
        except ValueError as exc:
            raise CanonicalSourceError(
                "trial start timestamp is invalid"
            ) from exc
    raise CanonicalSourceError("trial start timestamp is missing")


def _failure_stage(
    events: list[Mapping[str, Any]],
    *,
    authoritative_success: bool,
    terminal_error: object,
    transport_error_kind: object,
) -> str | None:
    if authoritative_success or terminal_error is None:
        return None

    if transport_error_kind is not None:
        return "transport"

    for event in reversed(events):
        event_type = event.get("event_type")

        if event_type == "driver_stop":
            if event.get("stage") == "model_turn_limit":
                return "run_limit"
            return None

        if event_type != "driver_error":
            continue

        stage = event.get("stage")
        if stage == "api_driver":
            continue
        if stage in {"tool_arguments", "agent_interface"}:
            return "agent_interface"
        if stage == "target_commit":
            return "target_operation"
        if stage == "verification":
            return "verification"

    return None


def _context_volume(
    events: list[Mapping[str, Any]],
    recorded_usage: Mapping[str, Any],
) -> int | None:
    responses = [
        event
        for event in events
        if event.get("event_type") == "api_response_observed"
    ]
    if not responses:
        return None

    observed = []
    for event in responses:
        usage = event.get("usage")
        if not isinstance(usage, Mapping):
            return None
        value = usage.get("input_tokens")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return None
        observed.append(value)

    recorded = recorded_usage.get("input_tokens")
    if (
        not isinstance(recorded, int)
        or isinstance(recorded, bool)
        or recorded < 0
        or recorded != sum(observed)
    ):
        return None

    return recorded


def build_exp001_promotion_source(
    *,
    batch,
    spec,
    outcome,
    driver_version: str,
) -> dict[str, Any]:
    trial_dir = batch.trial_dir(spec)
    result = outcome.result

    proof = result.get("verifier_proof")
    diagnostics = result.get("diagnostic_metrics")

    if not isinstance(proof, Mapping):
        raise CanonicalSourceError("verifier proof is missing")
    if not isinstance(diagnostics, Mapping):
        raise CanonicalSourceError("diagnostic metrics are missing")

    authoritative_success = proof.get("authoritative_success")
    final_state_correct = proof.get("final_state_correct")

    if not isinstance(authoritative_success, bool):
        raise CanonicalSourceError(
            "frozen verifier did not establish authoritative success"
        )
    if not isinstance(final_state_correct, bool):
        raise CanonicalSourceError(
            "frozen verifier did not establish final-state correctness"
        )

    events = _events(trial_dir / "events.jsonl")

    canonical_fields = {
        "experiment_id": result["experiment_id"],
        "variant": result["variant"],
        "date": _run_date(events),
        "agent_model": result["agent_model"],
        "evidence_status": "established",
        "authoritative_success": authoritative_success,
        "completion_time_ms": result["completion_time_ms"],
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
        "recovery_time_ms": diagnostics["recovery_time_ms"],
        "human_interventions": diagnostics["human_interventions"],
        "false_success": result["false_success"],
        "final_state_correct": final_state_correct,
        "failure_stage": _failure_stage(
            events,
            authoritative_success=authoritative_success,
            terminal_error=outcome.terminal_error,
            transport_error_kind=outcome.transport_error_kind,
        ),
        "context_volume": _context_volume(
            events,
            outcome.usage,
        ),
        "procedural_decisions": None,
        "receipt_complete": None,
    }

    root = _repo_root()
    packet = {
        "artifact_kind": CANONICAL_PROMOTION_SOURCE_KIND,
        "source": {
            "batch_id": batch.batch_id,
            "trial_id": spec.trial_id,
        },
        "canonical_fields": canonical_fields,
        "coding_profile": {
            "mapping_contract_sha256": _sha256_file(
                root
                / "experiments"
                / "EXP-001-QUICKSAVE"
                / "CANONICAL_RUN_MAPPING.md"
            ),
            "metric_contract_sha256": _sha256_file(
                root
                / "experiments"
                / "EXP-001-QUICKSAVE"
                / "METRIC_CONTRACT.md"
            ),
            "builder_source_sha256": _sha256_file(Path(__file__)),
            "harness_version": HARNESS_VERSION,
            "driver_version": driver_version,
            "verifier_version": IndependentQuicksaveVerifier.version,
        },
        "source_evidence": {
            "batch_preregistration_digest": batch.preregistration_digest,
            "trial_spec_digest": result["trial_spec_digest"],
        },
    }

    packet["packet_digest"] = digest(packet)
    return packet
