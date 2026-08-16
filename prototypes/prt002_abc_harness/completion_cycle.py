"""Offline planner for the frozen EXP-001 30-trial completion cycle.

This module does not call a model, open a live trial, write canonical RUN data,
or make network requests. It exists only to turn the approved EXP-001 design
into one reproducible pre-registration plan that a later execution harness may
consume after a separate human gate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable

VARIANTS = ("A", "B", "C")

# All six fixed permutations are required exactly once in the completion cycle.
FIXED_ORDERS: tuple[tuple[str, str, str], ...] = (
    ("A", "B", "C"),
    ("A", "C", "B"),
    ("B", "A", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
    ("C", "B", "A"),
)

# Four triplets cannot be perfectly position-balanced across three variants.
# This deterministic set is balanced as closely as mathematically possible:
# each variant appears once in each position, plus one extra appearance in a
# different position. Exact order is frozen here before data collection.
BASELINE_ORDERS: tuple[tuple[str, str, str], ...] = (
    ("A", "B", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
    ("A", "C", "B"),
)

FROZEN_MODEL_SETTINGS = {
    "model_family": "GPT-5.6 Sol",
    "reasoning_effort": "medium",
    "sampling_controls": "provider-defaults",
    "max_output_tokens": 1000,
    "timeout_seconds": 90,
    "automatic_retry": False,
    "model_fallback": False,
}

FROZEN_TASK = "DM note: quicksave"


@dataclass(frozen=True)
class PlannedTrial:
    ordinal: int
    triplet_index: int
    position_in_triplet: int
    variant: str
    order_condition: str
    order: tuple[str, str, str]

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["order"] = list(self.order)
        return value


def _triplets() -> list[tuple[str, tuple[str, str, str]]]:
    planned: list[tuple[str, tuple[str, str, str]]] = []
    for index, order in enumerate(BASELINE_ORDERS, start=1):
        planned.append((f"balanced-baseline-{index}", order))
    for order in FIXED_ORDERS:
        label = "fixed-" + "-".join(order).lower()
        planned.append((label, order))
    return planned


def build_completion_cycle() -> tuple[PlannedTrial, ...]:
    """Return the frozen 10-triplet / 30-trial EXP-001 plan."""

    trials: list[PlannedTrial] = []
    ordinal = 0
    for triplet_index, (condition, order) in enumerate(_triplets(), start=1):
        for position, variant in enumerate(order, start=1):
            ordinal += 1
            trials.append(
                PlannedTrial(
                    ordinal=ordinal,
                    triplet_index=triplet_index,
                    position_in_triplet=position,
                    variant=variant,
                    order_condition=condition,
                    order=order,
                )
            )
    validate_completion_cycle(trials)
    return tuple(trials)


def validate_completion_cycle(trials: Iterable[PlannedTrial]) -> None:
    trials = tuple(trials)
    if len(trials) != 30:
        raise ValueError("EXP-001 completion cycle must contain exactly 30 trials")

    counts = Counter(trial.variant for trial in trials)
    if counts != Counter({"A": 10, "B": 10, "C": 10}):
        raise ValueError("EXP-001 completion cycle must contain 10 runs per variant")

    triplets: dict[int, list[PlannedTrial]] = defaultdict(list)
    for trial in trials:
        triplets[trial.triplet_index].append(trial)
    if len(triplets) != 10:
        raise ValueError("EXP-001 completion cycle must contain exactly 10 triplets")

    observed_fixed: list[tuple[str, str, str]] = []
    baseline_count = 0
    for triplet_index in sorted(triplets):
        group = sorted(triplets[triplet_index], key=lambda item: item.position_in_triplet)
        if len(group) != 3:
            raise ValueError("every completion-cycle triplet must contain exactly three trials")
        order = tuple(item.variant for item in group)
        if set(order) != set(VARIANTS):
            raise ValueError("every triplet must contain A, B and C exactly once")
        if group[0].order_condition.startswith("balanced-baseline-"):
            baseline_count += 1
        elif group[0].order_condition.startswith("fixed-"):
            observed_fixed.append(order)
        else:
            raise ValueError("unknown EXP-001 order condition")

    if baseline_count != 4:
        raise ValueError("EXP-001 completion cycle must contain four baseline triplets")
    if Counter(observed_fixed) != Counter(FIXED_ORDERS):
        raise ValueError("EXP-001 completion cycle must contain every fixed permutation exactly once")

    # Ten appearances per variant cannot divide equally across three positions.
    # Require the smallest possible imbalance: position counts may differ by at
    # most one for each variant.
    position_counts: dict[str, Counter[int]] = {variant: Counter() for variant in VARIANTS}
    for trial in trials:
        position_counts[trial.variant][trial.position_in_triplet] += 1
    for variant in VARIANTS:
        values = [position_counts[variant][position] for position in (1, 2, 3)]
        if max(values) - min(values) > 1:
            raise ValueError(f"position allocation for variant {variant} is more imbalanced than necessary")


def completion_cycle_manifest() -> dict[str, object]:
    """Return a serializable, non-canonical preregistration payload."""

    trials = build_completion_cycle()
    return {
        "artifact_kind": "noncanonical-exp-001-completion-cycle-plan",
        "experiment_id": "EXP-001",
        "task": FROZEN_TASK,
        "model_settings": dict(FROZEN_MODEL_SETTINGS),
        "environment_variants": list(VARIANTS),
        "order_condition_count": 7,
        "triplet_count": 10,
        "trial_count": 30,
        "runs_per_variant": 10,
        "baseline_triplets": 4,
        "fixed_permutation_triplets": 6,
        "trials": [trial.as_dict() for trial in trials],
        "live_execution_authorized": False,
        "canonical_run_export_authorized": False,
    }
