from collections import Counter, defaultdict

import pytest

from prototypes.prt002_abc_harness.completion_cycle import (
    BASELINE_ORDERS,
    FIXED_ORDERS,
    FROZEN_MODEL_SETTINGS,
    FROZEN_TASK,
    PlannedTrial,
    build_completion_cycle,
    completion_cycle_manifest,
    validate_completion_cycle,
)


def test_completion_cycle_freezes_30_trials_and_10_runs_per_variant():
    trials = build_completion_cycle()

    assert len(trials) == 30
    assert Counter(trial.variant for trial in trials) == {"A": 10, "B": 10, "C": 10}
    assert FROZEN_TASK == "DM note: quicksave"
    assert FROZEN_MODEL_SETTINGS["max_output_tokens"] == 1000
    assert FROZEN_MODEL_SETTINGS["timeout_seconds"] == 90
    assert FROZEN_MODEL_SETTINGS["automatic_retry"] is False


def test_completion_cycle_contains_four_baselines_and_all_six_fixed_orders():
    trials = build_completion_cycle()
    grouped = defaultdict(list)
    for trial in trials:
        grouped[trial.triplet_index].append(trial)

    orders = []
    labels = []
    for index in sorted(grouped):
        group = sorted(grouped[index], key=lambda trial: trial.position_in_triplet)
        orders.append(tuple(trial.variant for trial in group))
        labels.append(group[0].order_condition)

    assert len(grouped) == 10
    assert sum(label.startswith("balanced-baseline-") for label in labels) == 4
    assert [order for order, label in zip(orders, labels) if label.startswith("balanced-baseline-")] == list(BASELINE_ORDERS)
    assert Counter(order for order, label in zip(orders, labels) if label.startswith("fixed-")) == Counter(FIXED_ORDERS)


def test_completion_cycle_is_balanced_as_closely_as_possible_by_position():
    trials = build_completion_cycle()

    for variant in ("A", "B", "C"):
        counts = Counter(
            trial.position_in_triplet for trial in trials if trial.variant == variant
        )
        assert sum(counts.values()) == 10
        assert max(counts.values()) - min(counts.values()) <= 1


def test_manifest_is_noncanonical_and_cannot_authorize_execution():
    manifest = completion_cycle_manifest()

    assert manifest["artifact_kind"] == "noncanonical-exp-001-completion-cycle-plan"
    assert manifest["order_condition_count"] == 7
    assert manifest["triplet_count"] == 10
    assert manifest["trial_count"] == 30
    assert manifest["runs_per_variant"] == 10
    assert manifest["live_execution_authorized"] is False
    assert manifest["canonical_run_export_authorized"] is False
    assert len(manifest["trials"]) == 30


def test_validator_rejects_a_damaged_cycle():
    trials = list(build_completion_cycle())
    trials[-1] = PlannedTrial(
        ordinal=trials[-1].ordinal,
        triplet_index=trials[-1].triplet_index,
        position_in_triplet=trials[-1].position_in_triplet,
        variant="A",
        order_condition=trials[-1].order_condition,
        order=trials[-1].order,
    )

    with pytest.raises(ValueError):
        validate_completion_cycle(trials)
