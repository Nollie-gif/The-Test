"""Create the frozen EXP-001 research batch using the existing PRT-002 harness.

Additive integration layer: no live API calls, no RUN export, no change to the
legacy disposable pilot path. The returned object is the existing
``PreregisteredBatch`` so trial opening, verifier behavior, telemetry, and
immutability continue to use the already-tested harness implementation.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from prototypes.prt001_controlled_quicksave.common import digest, now_iso
from prototypes.prt002_abc_harness.completion_cycle import (
    FROZEN_MODEL_SETTINGS,
    build_completion_cycle,
    completion_cycle_manifest,
)
from prototypes.prt002_abc_harness.harness import (
    EXPERIMENT_ID,
    EXPECTED_PAYLOAD,
    HARNESS_VERSION,
    INITIAL_PAYLOAD,
    PROMPT_REVISION,
    TASK_REQUEST,
    VARIANTS,
    VERIFICATION_SCOPE,
    PreregisteredBatch,
    TrialSpec,
    _compact_storage_id,
    _require_external_output_root,
    _require_nonempty,
    _write_json_new,
    agent_instruction,
)

RESEARCH_CYCLE_MODE = "exp-001-frozen-30-trial-cycle"
ORDER_POLICY = "4-balanced-baseline-plus-6-fixed-permutations"


def create_research_cycle_batch(
    output_root: Path,
    *,
    agent_model: str,
    operator: str,
    source_revision: str,
) -> PreregisteredBatch:
    """Pre-register the complete frozen 30-trial EXP-001 cycle.

    This creates only synthetic, non-canonical batch metadata. It never opens a
    trial, calls a model, touches an API key, or authorizes RUN-001.
    """

    output_root = _require_external_output_root(Path(output_root))
    agent_model = _require_nonempty("agent_model", agent_model)
    operator = _require_nonempty("operator", operator)
    source_revision = _require_nonempty("source_revision", source_revision)

    planned = build_completion_cycle()
    cycle = completion_cycle_manifest()

    batch_id = f"BATCH-{uuid.uuid4()}"
    batch_storage_id = _compact_storage_id(batch_id, prefix="BATCH-")
    batch_dir = output_root / batch_storage_id
    batch_dir.mkdir(parents=True, exist_ok=False)

    specs: list[TrialSpec] = []
    order_metadata: list[dict[str, object]] = []
    for planned_trial in planned:
        trial_id = f"TRIAL-{uuid.uuid4()}"
        specs.append(
            TrialSpec(
                trial_id=trial_id,
                storage_id=_compact_storage_id(trial_id, prefix="TRIAL-"),
                ordinal=planned_trial.ordinal,
                variant=planned_trial.variant,
                transaction_id=str(uuid.uuid4()),
            )
        )
        order_metadata.append(
            {
                "ordinal": planned_trial.ordinal,
                "triplet_index": planned_trial.triplet_index,
                "position_in_triplet": planned_trial.position_in_triplet,
                "variant": planned_trial.variant,
                "order_condition": planned_trial.order_condition,
                "order": list(planned_trial.order),
            }
        )

    instructions = {variant: agent_instruction(variant) for variant in VARIANTS}
    manifest: dict[str, object] = {
        "artifact_kind": "noncanonical-preregistered-abc-batch",
        "harness_version": HARNESS_VERSION,
        "evidence_status": "synthetic-prototype-only-not-a-RUN",
        "batch_id": batch_id,
        "batch_storage_id": batch_storage_id,
        "created_at": now_iso(),
        "experiment_id": EXPERIMENT_ID,
        "verification_scope": VERIFICATION_SCOPE,
        "task_request": TASK_REQUEST,
        "agent_model": agent_model,
        "operator": operator,
        "source_revision": source_revision,
        "prompt_revision": PROMPT_REVISION,
        "batch_mode": RESEARCH_CYCLE_MODE,
        "variant_order_policy": ORDER_POLICY,
        "repeats_per_variant": 10,
        "variants": list(VARIANTS),
        "initial_payload": dict(INITIAL_PAYLOAD),
        "expected_payload": dict(EXPECTED_PAYLOAD),
        "frozen_model_settings": dict(FROZEN_MODEL_SETTINGS),
        "completion_cycle": cycle,
        "order_metadata": order_metadata,
        "agent_instruction_digests": {
            variant: digest(instruction) for variant, instruction in instructions.items()
        },
        "trial_specs": [spec.as_dict() for spec in specs],
        "live_execution_authorized": False,
        "canonical_run_export_authorized": False,
    }
    manifest["preregistration_digest"] = digest(manifest)
    _write_json_new(batch_dir / "batch.json", manifest)
    return PreregisteredBatch(batch_dir, manifest)
