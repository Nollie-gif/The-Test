"""Fixture-only runner for controlled pre-flight testing.

This module deliberately creates FIXTURE-* artifacts only. It does not create
or validate canonical RUN-* research evidence.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from runner.adapters.base import get_adapter
from runner.env_freeze import capture_environment_manifest
from runner.telemetry import Telemetry
from runner.utils import allocate_fixture_run_id, write_json_atomic
from runner.verifier import FixtureVerifier

FIXTURE_SCHEMA_VERSION = "1.0"
RUNNER_VERSION = "0.1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_event_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_derived_metrics(events_path: Path) -> Dict[str, Any]:
    """Compute fixture diagnostics from explicitly classified telemetry only.

    These values are not canonical research metrics until a future, opt-in
    export has a real authoritative verifier behind it.
    """
    totals: Dict[str, Any] = {
        "tool_calls": 0,
        "wrong_tool_calls": 0,
        "wrong_route_target_calls": 0,
        "repeated_reads": 0,
        "permission_routing_errors": 0,
        "human_interventions": 0,
        "recovery_steps": 0,
        "agent_success_claims": 0,
    }
    error_seen = False
    first_error_at: datetime | None = None
    recovery_complete_at: datetime | None = None
    read_counts: Dict[str, int] = {}

    if not events_path.exists():
        totals["recovery_time_ms"] = 0
        return totals

    with events_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            event = json.loads(line)
            event_type = event.get("event_type")

            if event_type == "tool_call":
                totals["tool_calls"] += 1
                if event.get("classification") == "wrong_tool":
                    totals["wrong_tool_calls"] += 1
                elif event.get("classification") == "wrong_route_target":
                    totals["wrong_route_target_calls"] += 1
                if event.get("error_code") == "permission_denied":
                    totals["permission_routing_errors"] += 1
                if event.get("operation") == "read":
                    resource_id = event.get("resource_id")
                    if isinstance(resource_id, str) and resource_id:
                        prior_reads = read_counts.get(resource_id, 0)
                        if prior_reads:
                            totals["repeated_reads"] += 1
                        read_counts[resource_id] = prior_reads + 1
                if event.get("error_code"):
                    error_seen = True
                    if first_error_at is None:
                        first_error_at = parse_event_timestamp(event.get("timestamp"))
            elif event_type == "human_intervention":
                totals["human_interventions"] += 1
            elif event_type == "recovery_action":
                if error_seen:
                    totals["recovery_steps"] += 1
            elif event_type == "recovery_complete":
                if error_seen and recovery_complete_at is None:
                    recovery_complete_at = parse_event_timestamp(event.get("timestamp"))
            elif event_type == "agent_success_claim":
                if event.get("claim_type") == "explicit":
                    totals["agent_success_claims"] += 1
            elif event_type == "error":
                error_seen = True
                if first_error_at is None:
                    first_error_at = parse_event_timestamp(event.get("timestamp"))

    if not error_seen:
        totals["recovery_time_ms"] = 0
    elif first_error_at is None or recovery_complete_at is None:
        totals["recovery_time_ms"] = None
    else:
        totals["recovery_time_ms"] = max(
            0,
            round((recovery_complete_at - first_error_at).total_seconds() * 1000),
        )
    return totals


def fixture_receipt_complete(receipt: Dict[str, Any]) -> bool:
    required = {
        "fixture_verified",
        "verifier",
        "verified_at",
        "authoritative",
        "failure_stage",
        "details",
    }
    return required <= set(receipt) and receipt.get("authoritative") is False


def create_run_dir(base: Path, experiment_id: str, run_id: str) -> Path:
    run_dir = base / experiment_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="The-Test fixture runner")
    parser.add_argument("--exp", required=True, help="Experiment id (for example, EXP-001)")
    parser.add_argument("--variant", required=True, choices=["A", "B", "C"], help="Variant id")
    parser.add_argument("--operator", default="fixture-operator", help="Operator name")
    parser.add_argument("--outdir", default=None, help="Output directory (optional)")
    parser.add_argument("--fixture", action="store_true", help="Required: create a FIXTURE-* artifact")
    args = parser.parse_args(argv)

    if not args.fixture:
        parser.error("This runner is fixture-only. Pass --fixture; canonical RUN artifacts are blocked.")

    repo_root = Path(__file__).resolve().parent.parent
    base_runs = repo_root / "datasets" / "runs"
    run_id = allocate_fixture_run_id(args.exp)

    if args.outdir:
        run_dir = Path(args.outdir)
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = create_run_dir(base_runs, args.exp, run_id)

    run_json: Dict[str, Any] = {
        "run_id": run_id,
        "exp_id": args.exp,
        "variant": args.variant,
        "exp_commit": None,
        "runner_version": RUNNER_VERSION,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "operator": args.operator,
        "start_time": now_iso(),
        "end_time": None,
        "status": "running",
        "environment_manifest_path": "environment.json",
        "events_path": "events.jsonl",
        "receipt_path": "receipt.json",
        "artifacts": [],
        "derived_metrics": {},
        "notes": "Non-evidentiary fixture artifact.",
        "fixture_verified": None,
        "failure_stage": None,
    }

    write_json_atomic(run_dir / "environment.json", capture_environment_manifest())
    telemetry = Telemetry(run_dir / "events.jsonl")

    try:
        adapter = get_adapter(args.variant, telemetry=telemetry)
        adapter.run_task(exp_id=args.exp)
    except Exception as exc:
        telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "error",
                "source": "adapter",
                "stage": "adapter",
                "message": str(exc),
            }
        )

    receipt = FixtureVerifier().verify(run_dir)
    write_json_atomic(run_dir / "receipt.json", receipt)
    telemetry.close()

    derived = compute_derived_metrics(run_dir / "events.jsonl")
    derived["false_success"] = bool(
        derived["agent_success_claims"] and not receipt["fixture_verified"]
    )
    derived["final_state_correct"] = None
    derived["receipt_complete"] = fixture_receipt_complete(receipt)

    run_json["derived_metrics"] = derived
    run_json["end_time"] = now_iso()
    run_json["status"] = "completed"
    run_json["fixture_verified"] = bool(receipt["fixture_verified"])
    run_json["failure_stage"] = receipt["failure_stage"]
    write_json_atomic(run_dir / "run.json", run_json)

    print(f"Fixture run created at: {run_dir}")


if __name__ == "__main__":
    main()
