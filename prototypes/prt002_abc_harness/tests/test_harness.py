import json
import re
from collections import Counter
from pathlib import Path

import pytest

from prototypes.prt002_abc_harness import HarnessError, PreregisteredBatch
from prototypes.prt002_abc_harness import harness as harness_module


def make_batch(tmp_path, *, repeats_per_variant=3):
    return PreregisteredBatch.create(
        tmp_path / "prototype-output",
        agent_model="test-model/example-1",
        operator="pytest",
        source_revision="test-revision",
        repeats_per_variant=repeats_per_variant,
    )


def first_spec_for(batch, variant):
    return next(spec for spec in batch.trial_specs if spec.variant == variant)


def execute_minimum_success_path(trial):
    if trial.spec.variant == "A":
        prepared = trial.call("read_prepared_transaction")
        assert prepared["ok"] is True
        assert trial.call(
            "commit_prepared_transaction", transaction_id=prepared["data"]["transaction_id"]
        )["ok"] is True
        assert trial.call("verify_final_state")["ok"] is True
    elif trial.spec.variant == "B":
        route = trial.call("read_quicksave_route")
        assert route["ok"] is True
        assert trial.call(
            "execute_quicksave_route", route_token=route["data"]["route_token"]
        )["ok"] is True
        assert trial.call("verify_quicksave")["ok"] is True
    else:
        assert trial.call("quicksave")["ok"] is True
    trial.declare_success()
    return trial.finalize()


def test_batch_is_fully_preregistered_with_balanced_order_and_model_identity(tmp_path):
    batch = make_batch(tmp_path)
    manifest = json.loads((batch.batch_dir / "batch.json").read_text(encoding="utf-8"))

    assert manifest["evidence_status"] == "synthetic-prototype-only-not-a-RUN"
    assert manifest["agent_model"] == "test-model/example-1"
    assert manifest["source_revision"] == "test-revision"
    assert manifest["repeats_per_variant"] == 3
    assert manifest["variant_order_policy"] == "balanced-latin-square"
    assert Counter(spec.variant for spec in batch.trial_specs) == {"A": 3, "B": 3, "C": 3}
    assert [spec.variant for spec in batch.trial_specs] == list("ABCBCACAB")
    assert manifest["preregistration_digest"]
    assert "RUN-001" not in manifest["batch_id"]


def test_batch_uses_compact_deterministic_storage_aliases(tmp_path):
    batch = make_batch(tmp_path)

    assert batch.batch_dir.name == batch.batch_storage_id
    assert re.fullmatch(r"BATCH-[A-Za-z0-9_-]{22}", batch.batch_storage_id)
    for spec in batch.trial_specs:
        assert re.fullmatch(r"TRIAL-[A-Za-z0-9_-]{22}", spec.storage_id)
        assert batch.trial_dir(spec).name == spec.storage_id


def test_compact_storage_aliases_leave_room_for_legacy_windows_paths(tmp_path):
    batch = make_batch(tmp_path)
    spec = batch.trial_specs[0]
    representative_root = (
        r"C:\Users\operator\AppData\Local\Temp\pytest-of-operator\pytest-999"
        r"\test_driver_runs_one_synthetic0\external-prototype-output"
    )
    expectation_path = "\\".join(
        (
            representative_root,
            batch.batch_storage_id,
            "trials",
            spec.storage_id,
            "target",
            "expectations",
            f"{spec.transaction_id}.json",
        )
    )

    assert len(expectation_path) < 260


def test_batch_enforces_the_pre_registered_trial_order(tmp_path):
    batch = make_batch(tmp_path)

    with pytest.raises(HarnessError, match="schedule order"):
        batch.open_trial(batch.trial_specs[1].trial_id)

    first = batch.open_trial(batch.trial_specs[0].trial_id)
    with pytest.raises(HarnessError, match="prior scheduled trial"):
        batch.open_trial(batch.trial_specs[1].trial_id)
    first.finalize()
    second = batch.open_trial(batch.trial_specs[1].trial_id)
    second.finalize()


def test_batch_refuses_missing_model_identity_unbalanced_repeats_and_repo_output(tmp_path):
    with pytest.raises(HarnessError, match="agent_model"):
        PreregisteredBatch.create(
            tmp_path / "output",
            agent_model="",
            operator="pytest",
            source_revision="test-revision",
        )
    with pytest.raises(HarnessError, match="source_revision"):
        PreregisteredBatch.create(
            tmp_path / "output",
            agent_model="test-model/example-1",
            operator="pytest",
            source_revision="",
        )
    with pytest.raises(HarnessError, match="multiple of 3"):
        PreregisteredBatch.create(
            tmp_path / "output",
            agent_model="test-model/example-1",
            operator="pytest",
            source_revision="test-revision",
            repeats_per_variant=4,
        )

    repository_runs = Path(harness_module.__file__).resolve().parents[2] / "datasets" / "runs"
    with pytest.raises(HarnessError, match="outside the repository"):
        PreregisteredBatch.create(
            repository_runs,
            agent_model="test-model/example-1",
            operator="pytest",
            source_revision="test-revision",
        )


def test_all_variants_reach_the_same_independently_verified_synthetic_state(tmp_path):
    batch = make_batch(tmp_path)
    results = []
    tool_surface_sizes = {}

    for variant in ("A", "B", "C"):
        trial = batch.open_trial(first_spec_for(batch, variant).trial_id)
        tool_surface_sizes[variant] = len(trial.instruction["allowed_tools"])
        results.append(execute_minimum_success_path(trial))

    assert tool_surface_sizes == {"A": 6, "B": 3, "C": 1}
    for result in results:
        assert result["evidence_status"] == "synthetic-prototype-only-not-a-RUN"
        assert "run_id" not in result
        assert result["verifier_proof"]["verification_scope"] == "synthetic-controlled-target"
        assert result["verifier_proof"]["authoritative_success"] is True
        assert result["verifier_proof"]["final_state_correct"] is True
        assert result["verifier_proof"]["receipt_complete"] is True
        assert result["false_success"] is False


def test_wrong_tool_is_distinct_from_wrong_route_and_recovery_requires_verifier_proof(tmp_path):
    batch = make_batch(tmp_path)

    trial_a = batch.open_trial(first_spec_for(batch, "A").trial_id)
    assert trial_a.call("quicksave")["error_code"] == "wrong_tool"
    prepared = trial_a.call("read_prepared_transaction")
    assert trial_a.call(
        "commit_prepared_transaction", transaction_id=prepared["data"]["transaction_id"]
    )["ok"] is True
    trial_a.record_recovery_action("used the exposed variant-A transaction path")
    assert trial_a.record_recovery_complete()["authoritative_success"] is True
    result_a = trial_a.finalize()

    assert result_a["diagnostic_metrics"]["wrong_tool_calls"] == 1
    assert result_a["diagnostic_metrics"]["wrong_route_target_calls"] == 0
    assert result_a["diagnostic_metrics"]["recovery_steps"] == 1
    assert result_a["diagnostic_metrics"]["recovery_time_ms"] is not None

    trial_b = batch.open_trial(first_spec_for(batch, "B").trial_id)
    route = trial_b.call("read_quicksave_route")
    wrong_route = trial_b.call("execute_quicksave_route", route_token="route:wrong")
    assert wrong_route["error_code"] == "wrong_route_target"
    trial_b.record_recovery_action("used the returned compact route")
    assert trial_b.call(
        "execute_quicksave_route", route_token=route["data"]["route_token"]
    )["ok"] is True
    assert trial_b.record_recovery_complete()["authoritative_success"] is True
    result_b = trial_b.finalize()

    assert result_b["diagnostic_metrics"]["wrong_tool_calls"] == 0
    assert result_b["diagnostic_metrics"]["wrong_route_target_calls"] == 1
    assert result_b["diagnostic_metrics"]["recovery_steps"] == 1


def test_success_claim_without_commit_is_false_success_and_not_authoritative(tmp_path):
    batch = make_batch(tmp_path)
    trial = batch.open_trial(batch.trial_specs[0].trial_id)

    trial.declare_success()
    result = trial.finalize()

    assert result["agent_success_claimed"] is True
    assert result["false_success"] is True
    assert result["verifier_proof"]["authoritative_success"] is False
    assert result["verifier_proof"]["final_state_correct"] is False
