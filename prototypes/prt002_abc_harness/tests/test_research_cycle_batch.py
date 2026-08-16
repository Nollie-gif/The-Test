from collections import Counter

from prototypes.prt002_abc_harness.research_cycle_batch import (
    ORDER_POLICY,
    RESEARCH_CYCLE_MODE,
    create_research_cycle_batch,
)


def test_research_cycle_batch_uses_frozen_30_trial_plan(tmp_path):
    batch = create_research_cycle_batch(
        tmp_path,
        agent_model="frozen-test-model",
        operator="offline-test",
        source_revision="test-revision",
    )

    specs = batch.trial_specs
    manifest = batch.manifest

    assert len(specs) == 30
    assert Counter(spec.variant for spec in specs) == {"A": 10, "B": 10, "C": 10}
    assert manifest["batch_mode"] == RESEARCH_CYCLE_MODE
    assert manifest["variant_order_policy"] == ORDER_POLICY
    assert manifest["repeats_per_variant"] == 10
    assert manifest["completion_cycle"]["trial_count"] == 30
    assert manifest["completion_cycle"]["order_condition_count"] == 7
    assert len(manifest["order_metadata"]) == 30
    assert manifest["live_execution_authorized"] is False
    assert manifest["canonical_run_export_authorized"] is False


def test_research_cycle_batch_keeps_existing_trial_opening_path(tmp_path):
    batch = create_research_cycle_batch(
        tmp_path,
        agent_model="frozen-test-model",
        operator="offline-test",
        source_revision="test-revision",
    )

    first = batch.trial_specs[0]
    trial = batch.open_trial(first.trial_id)

    assert trial.spec.ordinal == 1
    assert trial.spec.variant == batch.manifest["order_metadata"][0]["variant"]
    assert batch.manifest["evidence_status"] == "synthetic-prototype-only-not-a-RUN"
