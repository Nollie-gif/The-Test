import json
from pathlib import Path

import pytest

from prototypes.prt001_controlled_quicksave.common import digest
from prototypes.prt002_abc_harness.api_driver import (
    DISPOSABLE_PILOT_CONFIG,
    SUCCESS_CLAIM,
    DRIVER_REGISTRATION_FILENAME,
    DriverConfig,
    create_disposable_pilot_batch,
    run_next_trial,
)
from prototypes.prt002_abc_harness.exp001_api_driver import (
    EXP001_API_MODEL,
    create_exp001_api_batch,
    run_exp001_next,
)
from prototypes.prt002_abc_harness.canonical_export import (
    CanonicalExportError,
    build_canonical_run_candidate,
    map_coded_evidence_to_candidate,
    promote_canonical_run,
)
from prototypes.prt002_abc_harness.evidence import (
    archive_external_batch,
)


class SuccessfulTransport:
    def __init__(self):
        self.counter = 0

    def _response_id(self):
        self.counter += 1
        return f"resp-export-{self.counter}"

    @staticmethod
    def _outputs(payload):
        return [
            item
            for item in payload["input"]
            if isinstance(item, dict)
            and item.get("type") == "function_call_output"
        ]

    def _call(self, name, arguments):
        call_id = f"call-{self.counter + 1}-{name}"
        return {
            "id": self._response_id(),
            "output": [
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": json.dumps(arguments),
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }

    def _final(self):
        return {
            "id": self._response_id(),
            "output": [],
            "output_text": SUCCESS_CLAIM,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        }

    def create(self, payload):
        tool_names = {
            tool["name"]
            for tool in payload["tools"]
        }
        outputs = self._outputs(payload)

        if tool_names == {"quicksave"}:
            if not outputs:
                return self._call("quicksave", {})
            return self._final()

        if "read_quicksave_route" in tool_names:
            if len(outputs) == 0:
                return self._call("read_quicksave_route", {})
            if len(outputs) == 1:
                route_result = json.loads(outputs[-1]["output"])
                return self._call(
                    "execute_quicksave_route",
                    {
                        "route_token":
                            route_result["data"]["route_token"]
                    },
                )
            if len(outputs) == 2:
                return self._call("verify_quicksave", {})
            return self._final()

        if len(outputs) == 0:
            return self._call(
                "read_prepared_transaction",
                {},
            )
        if len(outputs) == 1:
            prepared = json.loads(outputs[-1]["output"])
            return self._call(
                "commit_prepared_transaction",
                {
                    "transaction_id":
                        prepared["data"]["transaction_id"]
                },
            )
        if len(outputs) == 2:
            return self._call("verify_final_state", {})
        return self._final()


class CrashTransport:
    def create(self, _payload):
        raise KeyboardInterrupt("synthetic hard stop")


def make_batch(tmp_path: Path, *, config=None):
    batch = create_exp001_api_batch(
        tmp_path / "external",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )

    if config is not None:
        registration_path = batch.batch_dir / DRIVER_REGISTRATION_FILENAME
        registration = json.loads(registration_path.read_text(encoding="utf-8"))
        registration["model_config"] = config.as_dict()
        registration.pop("registration_digest", None)
        registration["registration_digest"] = digest(registration)
        registration_path.write_text(
            json.dumps(registration, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    return batch


def archived_success_batch(tmp_path: Path, *, config=None):
    batch = make_batch(tmp_path, config=config)

    for _ in batch.trial_specs:
        if config is None:
            outcome = run_exp001_next(batch, SuccessfulTransport())
        else:
            outcome = run_next_trial(
                batch,
                SuccessfulTransport(),
                config=config,
            )
        assert outcome.trial_status == "COMPLETE"
        assert outcome.result["verifier_proof"]["authoritative_success"] is True

    archive_external_batch(batch.batch_dir)
    return batch


def snapshot_tree(root: Path):
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(root))] = path.read_bytes()
    return snapshot


def test_complete_archived_trial_builds_canonical_candidate(tmp_path):
    batch = archived_success_batch(tmp_path)
    spec = batch.trial_specs[0]

    before = snapshot_tree(batch.batch_dir)

    preview = build_canonical_run_candidate(
        batch.batch_dir,
        trial_id=spec.trial_id,
        proposed_run_id="RUN-999",
    )

    candidate = preview["candidate"]

    assert preview["promotion_authorized"] is False
    assert preview["network_performed"] is False
    assert preview["mutation_performed"] is False
    assert preview["candidate_digest"] == digest(candidate)

    assert candidate["run_id"] == "RUN-999"
    assert candidate["experiment_id"] == "EXP-001"
    assert candidate["variant"] == "A"
    assert candidate["agent_model"] == EXP001_API_MODEL
    assert candidate["evidence_status"] == "established"
    assert candidate["authoritative_success"] is True
    assert candidate["final_state_correct"] is True
    assert candidate["failure_stage"] is None
    assert candidate["false_success"] is False
    assert candidate["tool_calls"] == 3
    assert candidate["recovery_time_ms"] == 0
    assert candidate["context_volume"] == 40
    assert candidate["procedural_decisions"] is None
    assert candidate["receipt_complete"] is None

    assert snapshot_tree(batch.batch_dir) == before


def test_clean_unknown_mapping_preserves_permitted_nulls():
    coded = {
        "experiment_id": "EXP-001",
        "variant": "B",
        "date": "2026-08-20",
        "agent_model": EXP001_API_MODEL,
        "evidence_status": "unavailable",
        "authoritative_success": None,
        "completion_time_ms": 123,
        "tool_calls": 1,
        "wrong_tool_calls": 0,
        "repeated_reads": 0,
        "wrong_route_target_calls": 0,
        "permission_routing_errors": 0,
        "recovery_steps": 0,
        "recovery_time_ms": 0,
        "human_interventions": 0,
        "false_success": False,
        "final_state_correct": None,
        "failure_stage": None,
        "context_volume": None,
        "procedural_decisions": None,
        "receipt_complete": None,
        "notes": "Clean UNKNOWN terminal boundary.",
    }

    candidate = map_coded_evidence_to_candidate(
        proposed_run_id="RUN-999",
        coded_evidence=coded,
    )

    assert candidate["authoritative_success"] is None
    assert candidate["final_state_correct"] is None
    assert candidate["failure_stage"] is None
    assert candidate["context_volume"] is None
    assert candidate["receipt_complete"] is None


def test_interrupted_stop_required_evidence_is_rejected(
    tmp_path,
    monkeypatch,
):
    batch = make_batch(tmp_path)
    opened = []
    original = batch.open_trial

    def capture(trial_id):
        trial = original(trial_id)
        opened.append(trial)
        return trial

    monkeypatch.setattr(batch, "open_trial", capture)

    with pytest.raises(
        KeyboardInterrupt,
        match="synthetic hard stop",
    ):
        run_exp001_next(batch, CrashTransport())

    opened[0].telemetry.close()

    with pytest.raises(
        CanonicalExportError,
        match="ARCHIVED_VALID",
    ):
        build_canonical_run_candidate(
            batch.batch_dir,
            trial_id=batch.trial_specs[0].trial_id,
            proposed_run_id="RUN-999",
        )


def test_archived_tampering_is_rejected(tmp_path):
    batch = archived_success_batch(tmp_path)
    spec = batch.trial_specs[0]
    receipt_path = (
        batch.trial_dir(spec)
        / "api-driver-receipt.json"
    )

    receipt = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )
    receipt["terminal_error"] = "tampered"
    receipt_path.write_text(
        json.dumps(receipt),
        encoding="utf-8",
    )

    with pytest.raises(
        CanonicalExportError,
        match="ARCHIVED_VALID",
    ):
        build_canonical_run_candidate(
            batch.batch_dir,
            trial_id=spec.trial_id,
            proposed_run_id="RUN-999",
        )


def test_disposable_pilot_is_never_promotable(tmp_path):
    batch = create_disposable_pilot_batch(
        tmp_path / "pilot",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )

    outcome = run_next_trial(
        batch,
        SuccessfulTransport(),
        config=DISPOSABLE_PILOT_CONFIG,
    )
    assert outcome.trial_status == "COMPLETE"
    archive_external_batch(batch.batch_dir)

    with pytest.raises(
        CanonicalExportError,
        match="registration could not be loaded safely",
    ):
        build_canonical_run_candidate(
            batch.batch_dir,
            trial_id=batch.trial_specs[0].trial_id,
            proposed_run_id="RUN-999",
        )


def test_model_settings_drift_is_rejected(tmp_path):
    batch = make_batch(tmp_path)

    for _ in batch.trial_specs:
        outcome = run_exp001_next(batch, SuccessfulTransport())
        assert outcome.trial_status == "COMPLETE"

    drift = DriverConfig(
        model=EXP001_API_MODEL,
        reasoning_effort="high",
        max_model_turns=8,
        max_output_tokens_per_turn=1000,
    )

    registration_path = batch.batch_dir / DRIVER_REGISTRATION_FILENAME
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["model_config"] = drift.as_dict()
    registration.pop("registration_digest", None)
    registration["registration_digest"] = digest(registration)
    registration_path.write_text(
        json.dumps(registration, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    archive_external_batch(batch.batch_dir)

    with pytest.raises(
        CanonicalExportError,
        match="registration could not be loaded safely",
    ):
        build_canonical_run_candidate(
            batch.batch_dir,
            trial_id=batch.trial_specs[0].trial_id,
            proposed_run_id="RUN-999",
        )


def test_promotion_requires_exact_digest_and_writes_once(tmp_path):
    batch = archived_success_batch(tmp_path)
    spec = batch.trial_specs[0]

    preview = build_canonical_run_candidate(
        batch.batch_dir,
        trial_id=spec.trial_id,
        proposed_run_id="RUN-999",
    )

    runs_root = tmp_path / "canonical-runs"
    before = snapshot_tree(batch.batch_dir)

    with pytest.raises(
        CanonicalExportError,
        match="digest does not match",
    ):
        promote_canonical_run(
            batch.batch_dir,
            trial_id=spec.trial_id,
            run_id="RUN-999",
            approved_candidate_digest="0" * 64,
            approval_reference="TEST-APPROVAL-001",
            runs_root=runs_root,
            confirm_promotion=True,
        )

    assert not (runs_root / "RUN-999.json").exists()

    result = promote_canonical_run(
        batch.batch_dir,
        trial_id=spec.trial_id,
        run_id="RUN-999",
        approved_candidate_digest=preview[
            "candidate_digest"
        ],
        approval_reference="TEST-APPROVAL-001",
        runs_root=runs_root,
        confirm_promotion=True,
    )

    assert result["promotion_status"] == "PROMOTED_EXACTLY_ONCE"
    assert result["network_performed"] is False
    assert result["source_evidence_modified"] is False

    written = json.loads(
        (runs_root / "RUN-999.json").read_text(
            encoding="utf-8"
        )
    )
    assert written == preview["candidate"]

    assert snapshot_tree(batch.batch_dir) == before

    with pytest.raises(
        CanonicalExportError,
        match="duplicate canonical run_id",
    ):
        promote_canonical_run(
            batch.batch_dir,
            trial_id=spec.trial_id,
            run_id="RUN-999",
            approved_candidate_digest=preview[
                "candidate_digest"
            ],
            approval_reference="TEST-APPROVAL-001",
            runs_root=runs_root,
            confirm_promotion=True,
        )


def test_promotion_requires_explicit_confirmation(tmp_path):
    batch = archived_success_batch(tmp_path)
    spec = batch.trial_specs[0]

    preview = build_canonical_run_candidate(
        batch.batch_dir,
        trial_id=spec.trial_id,
        proposed_run_id="RUN-999",
    )

    with pytest.raises(
        CanonicalExportError,
        match="explicit confirm_promotion=True",
    ):
        promote_canonical_run(
            batch.batch_dir,
            trial_id=spec.trial_id,
            run_id="RUN-999",
            approved_candidate_digest=preview[
                "candidate_digest"
            ],
            approval_reference="TEST-APPROVAL-001",
            runs_root=tmp_path / "runs",
            confirm_promotion=False,
        )
