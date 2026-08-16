"""Frozen API execution profile for the EXP-001 30-trial research cycle.

This module deliberately leaves the terminal Terra pilot configuration in
``api_driver.py`` unchanged for historical reproducibility.  EXP-001 uses this
separate profile so an old pilot command cannot silently run the new research
cycle with the wrong model.

No function in this module authorizes RUN-001.  Batch creation, registration,
planning, and inspection are offline.  A live request still requires the
existing immutable approval proof plus both explicit CLI live flags.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from prototypes.prt001_controlled_quicksave.common import digest

from .api_driver import (
    DRIVER_REGISTRATION_FILENAME,
    ApiDriverError,
    DriverConfig,
    HttpResponsesTransport,
    _driver_registration,
    _validated_registration,
    _write_json_new,
    inspect_interrupted_trials,
    load_api_batch,
    plan_next_trial,
    run_next_trial,
)
from .completion_cycle import FROZEN_MODEL_SETTINGS
from .research_cycle_batch import RESEARCH_CYCLE_MODE, create_research_cycle_batch


EXP001_EXECUTION_PROFILE = "exp-001f-sol-medium-v1"
EXP001_API_MODEL = "gpt-5.6-sol"
EXP001_REQUEST_TIMEOUT_SECONDS = 90
EXP001_AUTOMATIC_RETRIES = 0
EXP001_MODEL_FALLBACK: str | None = None

EXP001_DRIVER_CONFIG = DriverConfig(
    model=EXP001_API_MODEL,
    reasoning_effort="medium",
    max_model_turns=8,
    max_output_tokens_per_turn=1000,
)


def _require_frozen_baseline() -> None:
    """Fail closed if code and the already-frozen experiment metadata diverge."""

    expected: Mapping[str, Any] = FROZEN_MODEL_SETTINGS
    checks = {
        "model_family": "GPT-5.6 Sol",
        "reasoning_effort": EXP001_DRIVER_CONFIG.reasoning_effort,
        "sampling_controls": "provider-defaults",
        "max_output_tokens": EXP001_DRIVER_CONFIG.max_output_tokens_per_turn,
        "timeout_seconds": EXP001_REQUEST_TIMEOUT_SECONDS,
        "automatic_retry": bool(EXP001_AUTOMATIC_RETRIES),
        "model_fallback": EXP001_MODEL_FALLBACK is not None,
    }
    if dict(expected) != checks:
        raise ApiDriverError(
            "EXP-001 API profile differs from the frozen completion-cycle model settings"
        )


def _exp001_registration(
    batch,
    *,
    driver_source_revision: str,
) -> dict[str, Any]:
    """Build the immutable registration for the frozen EXP-001 profile."""

    _require_frozen_baseline()
    registration = _driver_registration(
        batch,
        driver_source_revision=driver_source_revision,
        config=EXP001_DRIVER_CONFIG,
    )
    registration.pop("registration_digest", None)
    registration["execution_profile"] = EXP001_EXECUTION_PROFILE
    registration["frozen_model_settings"] = dict(FROZEN_MODEL_SETTINGS)
    registration["request_policy"] = {
        "timeout_seconds": EXP001_REQUEST_TIMEOUT_SECONDS,
        "automatic_retries": EXP001_AUTOMATIC_RETRIES,
        "model_fallback": EXP001_MODEL_FALLBACK,
    }
    registration["historical_driver_note"] = (
        "Underlying PRT-003 transport/version is retained for pilot reproducibility; "
        "this execution profile is the frozen EXP-001 Sol baseline."
    )
    registration["registration_digest"] = digest(registration)
    return registration


def create_exp001_api_batch(
    output_root: Path,
    *,
    operator: str,
    source_revision: str,
    driver_source_revision: str,
):
    """Create and register the frozen 30-trial EXP-001 batch without a network call."""

    _require_frozen_baseline()
    batch = create_research_cycle_batch(
        Path(output_root),
        agent_model=EXP001_API_MODEL,
        operator=operator,
        source_revision=source_revision,
    )
    _write_json_new(
        batch.batch_dir / DRIVER_REGISTRATION_FILENAME,
        _exp001_registration(batch, driver_source_revision=driver_source_revision),
    )
    return batch


def load_exp001_api_batch(batch_dir: Path):
    """Load a batch only if it is the registered frozen EXP-001 research cycle."""

    _require_frozen_baseline()
    batch = load_api_batch(Path(batch_dir))
    if batch.manifest.get("batch_mode") != RESEARCH_CYCLE_MODE:
        raise ApiDriverError("EXP-001 driver requires the frozen 30-trial research-cycle batch")
    registration = _validated_registration(batch, EXP001_DRIVER_CONFIG)
    if registration.get("execution_profile") != EXP001_EXECUTION_PROFILE:
        raise ApiDriverError("batch is not registered for the frozen EXP-001 execution profile")
    if registration.get("frozen_model_settings") != dict(FROZEN_MODEL_SETTINGS):
        raise ApiDriverError("batch registration differs from frozen EXP-001 model settings")
    expected_policy = {
        "timeout_seconds": EXP001_REQUEST_TIMEOUT_SECONDS,
        "automatic_retries": EXP001_AUTOMATIC_RETRIES,
        "model_fallback": EXP001_MODEL_FALLBACK,
    }
    if registration.get("request_policy") != expected_policy:
        raise ApiDriverError("batch registration differs from frozen EXP-001 request policy")
    return batch


def plan_exp001_next(batch) -> dict[str, Any]:
    """Return the exact next Sol request plan; no trial is opened and no network is used."""

    _require_frozen_baseline()
    return plan_next_trial(batch, config=EXP001_DRIVER_CONFIG)


def inspect_exp001_interrupted(batch) -> dict[str, Any]:
    """Return the existing read-only STOP report under the frozen Sol profile."""

    _require_frozen_baseline()
    return inspect_interrupted_trials(batch, config=EXP001_DRIVER_CONFIG)


def run_exp001_next(batch, transport):
    """Execute exactly one pre-registered trial through an explicitly supplied transport."""

    _require_frozen_baseline()
    return run_next_trial(batch, transport, config=EXP001_DRIVER_CONFIG)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Frozen EXP-001 GPT-5.6 Sol API profile; RUN-001 remains separately locked"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create-batch",
        help="Create the frozen external 30-trial batch; no API request.",
    )
    create.add_argument("--outdir", required=True)
    create.add_argument("--operator", required=True)
    create.add_argument("--source-revision", required=True)
    create.add_argument("--driver-source-revision", required=True)

    plan = commands.add_parser(
        "plan-next",
        help="Print the next frozen request plan; no API request.",
    )
    plan.add_argument("--batch-dir", required=True)

    inspect = commands.add_parser(
        "inspect-interrupted",
        help="Read-only STOP report; never retries or resumes.",
    )
    inspect.add_argument("--batch-dir", required=True)

    run = commands.add_parser(
        "run-next",
        help="Run exactly one trial only after the existing approval proof and two live flags.",
    )
    run.add_argument("--batch-dir", required=True)
    run.add_argument("--live", action="store_true")
    run.add_argument("--confirm-live-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    if args.command == "create-batch":
        batch = create_exp001_api_batch(
            Path(args.outdir),
            operator=args.operator,
            source_revision=args.source_revision,
            driver_source_revision=args.driver_source_revision,
        )
        print(f"Frozen non-canonical EXP-001 batch created: {batch.batch_dir}")
        return

    batch = load_exp001_api_batch(Path(args.batch_dir))

    if args.command == "plan-next":
        print(json.dumps(plan_exp001_next(batch), ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "inspect-interrupted":
        print(
            json.dumps(
                inspect_exp001_interrupted(batch),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return

    if not args.live or not args.confirm_live_run:
        raise SystemExit(
            "EXP-001 driver refuses to make an API request without both --live and --confirm-live-run"
        )

    from .evidence import EvidenceValidationError, require_valid_pilot_approval_proof

    try:
        require_valid_pilot_approval_proof(Path(args.batch_dir))
    except EvidenceValidationError as exc:
        raise SystemExit(str(exc)) from exc

    transport = HttpResponsesTransport()
    transport.preflight()
    outcome = run_exp001_next(batch, transport)
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
