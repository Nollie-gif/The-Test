from pathlib import Path

import pytest

from prototypes.prt001_controlled_quicksave.common import digest
from prototypes.prt002_abc_harness.canonical_promotion import (
    CanonicalPromotionError,
    approval_path,
    _create_promotion_approval_from_preview as _test_create_promotion_approval,
    _promote_approved_candidate_from_preview as _test_promote_approved_candidate,
)


def candidate(run_id="RUN-999"):
    return {
        "run_id": run_id,
        "experiment_id": "EXP-001",
        "variant": "A",
        "date": "2026-10-10",
        "agent_model": "gpt-5.6-sol",
        "evidence_status": "established",
        "authoritative_success": True,
        "completion_time_ms": 1,
        "tool_calls": 1,
        "wrong_tool_calls": 0,
        "repeated_reads": 0,
        "wrong_route_target_calls": 0,
        "permission_routing_errors": 0,
        "recovery_steps": 0,
        "recovery_time_ms": 0,
        "human_interventions": 0,
        "false_success": False,
        "final_state_correct": True,
        "failure_stage": None,
    }


def preview(run_id="RUN-999"):
    run = candidate(run_id)
    return {
        "artifact_kind": "canonical-run-candidate-preview-v1",
        "source": {
            "batch_id": "BATCH-TEST",
            "trial_id": "TRIAL-TEST",
        },
        "run_id": run_id,
        "candidate": run,
        "candidate_digest": digest(run),
        "coding_profile": {
            "mapping_contract_sha256": "a" * 64,
            "metric_contract_sha256": "b" * 64,
            "builder_source_sha256": "c" * 64,
            "harness_version": "test-harness-v1",
            "driver_version": "test-driver-v1",
            "verifier_version": "test-verifier-v1",
        },
    }


def test_approval_is_structured_and_bound_to_exact_candidate(tmp_path):
    result = _test_create_promotion_approval(
        preview(),
        approval_reference="TEST-APPROVAL-001",
        runs_root=tmp_path / "runs",
    )

    proof = result["proof"]
    assert proof["source"]["batch_id"] == "BATCH-TEST"
    assert proof["source"]["trial_id"] == "TRIAL-TEST"
    assert proof["run_id"] == "RUN-999"
    assert proof["candidate_digest"] == preview()["candidate_digest"]
    assert proof["coding_profile"] == preview()["coding_profile"]


def test_one_source_trial_cannot_map_to_two_run_ids(tmp_path):
    runs_root = tmp_path / "runs"

    _test_create_promotion_approval(
        preview("RUN-998"),
        approval_reference="TEST-APPROVAL-998",
        runs_root=runs_root,
    )

    with pytest.raises(CanonicalPromotionError):
        _test_create_promotion_approval(
            preview("RUN-999"),
            approval_reference="TEST-APPROVAL-999",
            runs_root=runs_root,
        )


def test_promotion_rejects_candidate_drift_after_approval(tmp_path):
    runs_root = tmp_path / "runs"
    approved = preview()

    approval = _test_create_promotion_approval(
        approved,
        approval_reference="TEST-APPROVAL-DRIFT",
        runs_root=runs_root,
    )

    changed = preview()
    changed["candidate"]["tool_calls"] = 2
    changed["candidate_digest"] = digest(changed["candidate"])

    with pytest.raises(CanonicalPromotionError):
        _test_promote_approved_candidate(
            changed,
            approval_file=Path(approval["approval_path"]),
            runs_root=runs_root,
        )


def test_promotion_is_create_only(tmp_path):
    runs_root = tmp_path / "runs"
    approved = preview()

    approval = _test_create_promotion_approval(
        approved,
        approval_reference="TEST-APPROVAL-PROMOTE",
        runs_root=runs_root,
    )

    _test_promote_approved_candidate(
        approved,
        approval_file=Path(approval["approval_path"]),
        runs_root=runs_root,
    )

    assert (runs_root / "RUN-999.json").is_file()

    with pytest.raises(CanonicalPromotionError):
        _test_promote_approved_candidate(
            approved,
            approval_file=Path(approval["approval_path"]),
            runs_root=runs_root,
        )


def test_run_000_is_never_approvable(tmp_path):
    with pytest.raises(CanonicalPromotionError, match="RUN-000"):
        _test_create_promotion_approval(
            preview("RUN-000"),
            approval_reference="TEST-APPROVAL-000",
            runs_root=tmp_path / "runs",
        )


class OfflineSuccessTransport:
    def __init__(self):
        self.turn = 0

    def create(self, payload):
        self.turn += 1
        tool_names = {tool["name"] for tool in payload["tools"]}

        if "read_prepared_transaction" in tool_names:
            if self.turn == 1:
                return {
                    "id": "resp-a-read",
                    "usage": {"input_tokens": 10},
                    "output": [{
                        "type": "function_call",
                        "call_id": "call-a-read",
                        "name": "read_prepared_transaction",
                        "arguments": "{}",
                    }],
                }

            if self.turn == 2:
                import json
                previous = json.loads(payload["input"][-1]["output"])
                transaction_id = previous["data"]["transaction_id"]
                return {
                    "id": "resp-a-commit",
                    "usage": {"input_tokens": 11},
                    "output": [{
                        "type": "function_call",
                        "call_id": "call-a-commit",
                        "name": "commit_prepared_transaction",
                        "arguments": json.dumps(
                            {"transaction_id": transaction_id}
                        ),
                    }],
                }

            if self.turn == 3:
                return {
                    "id": "resp-a-verify",
                    "usage": {"input_tokens": 12},
                    "output": [{
                        "type": "function_call",
                        "call_id": "call-a-verify",
                        "name": "verify_final_state",
                        "arguments": "{}",
                    }],
                }

        return {
            "id": "resp-final",
            "usage": {"input_tokens": 13},
            "output_text": "QUICKSAVE_COMPLETE",
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": "QUICKSAVE_COMPLETE",
                }],
            }],
        }


def test_exp001_finalization_emits_frozen_promotion_source_packet(tmp_path):
    import json

    from prototypes.prt002_abc_harness.exp001_api_driver import (
        create_exp001_api_batch,
        run_exp001_next,
    )

    batch = create_exp001_api_batch(
        tmp_path / "exp001",
        operator="pytest",
        source_revision="test-source-revision",
        driver_source_revision="test-driver-revision",
    )

    outcome = run_exp001_next(batch, OfflineSuccessTransport())
    assert outcome.trial_status == "COMPLETE"

    spec = batch.trial_specs[0]
    packet_path = (
        batch.trial_dir(spec)
        / "canonical-promotion-source.json"
    )

    assert packet_path.is_file()

    packet = json.loads(packet_path.read_text(encoding="utf-8"))

    assert packet["artifact_kind"] == "canonical-promotion-source-v1"
    assert packet["source"] == {
        "batch_id": batch.batch_id,
        "trial_id": spec.trial_id,
    }

    assert "run_id" not in packet["canonical_fields"]
    assert packet["canonical_fields"]["experiment_id"] == "EXP-001"
    assert packet["canonical_fields"]["variant"] == spec.variant
    assert packet["canonical_fields"]["authoritative_success"] is True
    assert packet["canonical_fields"]["final_state_correct"] is True
    assert packet["canonical_fields"]["failure_stage"] is None

    profile = packet["coding_profile"]
    assert len(profile["mapping_contract_sha256"]) == 64
    assert len(profile["metric_contract_sha256"]) == 64
    assert profile["harness_version"]
    assert profile["driver_version"]
    assert profile["verifier_version"]

    assert len(packet["packet_digest"]) == 64


def test_archived_source_packet_builds_read_only_candidate_preview(tmp_path):
    from prototypes.prt002_abc_harness.canonical_promotion import (
        build_canonical_candidate_preview,
    )
    from prototypes.prt002_abc_harness.evidence import (
        archive_external_batch,
        validate_external_batch,
    )
    from prototypes.prt002_abc_harness.exp001_api_driver import (
        create_exp001_api_batch,
        run_exp001_next,
    )

    batch = create_exp001_api_batch(
        tmp_path / "exp001-archive",
        operator="pytest",
        source_revision="test-source-revision",
        driver_source_revision="test-driver-revision",
    )

    for _ in batch.trial_specs:
        run_exp001_next(batch, OfflineSuccessTransport())

    archive_external_batch(batch.batch_dir)

    assert (
        validate_external_batch(batch.batch_dir)["validation_status"]
        == "ARCHIVED_VALID"
    )

    spec = batch.trial_specs[0]
    packet_path = (
        batch.trial_dir(spec)
        / "canonical-promotion-source.json"
    )
    before = packet_path.read_bytes()

    result = build_canonical_candidate_preview(
        batch.batch_dir,
        trial_id=spec.trial_id,
        proposed_run_id="RUN-999",
    )

    assert result["source"] == {
        "batch_id": batch.batch_id,
        "trial_id": spec.trial_id,
    }
    assert result["run_id"] == "RUN-999"
    assert result["candidate"]["run_id"] == "RUN-999"
    assert result["candidate"]["experiment_id"] == "EXP-001"
    assert result["candidate_digest"] == digest(result["candidate"])
    assert result["promotion_authorized"] is False
    assert result["network_performed"] is False
    assert result["mutation_performed"] is False

    assert packet_path.read_bytes() == before


def test_approval_rebuilds_exact_candidate_from_archived_source(tmp_path):
    from prototypes.prt002_abc_harness.canonical_promotion import (
        build_canonical_candidate_preview,
        create_promotion_approval,
    )
    from prototypes.prt002_abc_harness.evidence import archive_external_batch
    from prototypes.prt002_abc_harness.exp001_api_driver import (
        create_exp001_api_batch,
        run_exp001_next,
    )

    batch = create_exp001_api_batch(
        tmp_path / "approval-archive",
        operator="pytest",
        source_revision="test-source-revision",
        driver_source_revision="test-driver-revision",
    )

    for _ in batch.trial_specs:
        run_exp001_next(batch, OfflineSuccessTransport())

    archive_external_batch(batch.batch_dir)

    spec = batch.trial_specs[0]

    preview = build_canonical_candidate_preview(
        batch.batch_dir,
        trial_id=spec.trial_id,
        proposed_run_id="RUN-999",
    )

    approval = create_promotion_approval(
        batch.batch_dir,
        trial_id=spec.trial_id,
        run_id="RUN-999",
        approved_candidate_digest=preview["candidate_digest"],
        approval_reference="TEST-APPROVAL-ARCHIVED",
        runs_root=tmp_path / "runs",
    )

    assert approval["proof"]["candidate_digest"] == preview["candidate_digest"]
    assert approval["proof"]["source"] == preview["source"]


def test_promotion_rebuilds_exact_candidate_from_archived_source(tmp_path):
    from prototypes.prt002_abc_harness.canonical_promotion import (
        build_canonical_candidate_preview,
        create_promotion_approval,
        promote_approved_candidate,
    )
    from prototypes.prt002_abc_harness.evidence import archive_external_batch
    from prototypes.prt002_abc_harness.exp001_api_driver import (
        create_exp001_api_batch,
        run_exp001_next,
    )

    batch = create_exp001_api_batch(
        tmp_path / "promotion-archive",
        operator="pytest",
        source_revision="test-source-revision",
        driver_source_revision="test-driver-revision",
    )

    for _ in batch.trial_specs:
        run_exp001_next(batch, OfflineSuccessTransport())

    archive_external_batch(batch.batch_dir)

    spec = batch.trial_specs[0]
    runs_root = tmp_path / "runs"

    preview = build_canonical_candidate_preview(
        batch.batch_dir,
        trial_id=spec.trial_id,
        proposed_run_id="RUN-999",
    )

    approval = create_promotion_approval(
        batch.batch_dir,
        trial_id=spec.trial_id,
        run_id="RUN-999",
        approved_candidate_digest=preview["candidate_digest"],
        approval_reference="TEST-APPROVAL-PROMOTION",
        runs_root=runs_root,
    )

    result = promote_approved_candidate(
        batch.batch_dir,
        trial_id=spec.trial_id,
        run_id="RUN-999",
        approval_file=Path(approval["approval_path"]),
        runs_root=runs_root,
    )

    assert result["promotion_status"] == "PROMOTED_EXACTLY_ONCE"
    assert result["run_id"] == "RUN-999"
    assert (runs_root / "RUN-999.json").is_file()
