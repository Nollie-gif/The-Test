"""Runner orchestrator (fixture-oriented).

Responsibilities:
- allocate fixture run id
- create run directory
- capture environment manifest
- open telemetry (events.jsonl)
- select adapter and run task
- invoke verifier -> receipt.json
- compute derived metrics from events.jsonl
- write run.json

This runner is intentionally minimal and deterministic for fixture/testing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from runner.utils import allocate_fixture_run_id, write_json_atomic
from runner.env_freeze import capture_environment_manifest
from runner.telemetry import Telemetry
from runner.verifier import Verifier
from runner.adapters.base import get_adapter

RUN_SCHEMA_VERSION = "1.0"
RUNNER_VERSION = "0.1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_derived_metrics(events_path: Path) -> Dict[str, Any]:
    totals = {
        "total_tool_calls": 0,
        "wrong_tool_calls": 0,
        "permission_errors": 0,
        "human_interventions": 0,
        "recovery_steps": 0,
        "agent_success_claims": 0,
    }
    first_error_ts = None
    recovery_after_first_error = 0

    if not events_path.exists():
        return totals

    with events_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            ev = json.loads(line)
            et = ev.get("event_type")
            if et == "tool_call":
                totals["total_tool_calls"] += 1
                if ev.get("result") == "wrong_target":
                    totals["wrong_tool_calls"] += 1
                if ev.get("error_code") == "permission_denied":
                    totals["permission_errors"] += 1
            elif et == "human_intervention":
                totals["human_interventions"] += 1
            elif et == "recovery_action":
                totals["recovery_steps"] += 1
                if first_error_ts:
                    recovery_after_first_error += 1
            elif et == "agent_success_claim":
                totals["agent_success_claims"] += 1
            elif et == "error":
                if first_error_ts is None:
                    first_error_ts = ev.get("timestamp")

    totals["recovery_steps_after_first_error"] = recovery_after_first_error
    return totals


def create_run_dir(base: Path, exp: str, run_id: str) -> Path:
    run_dir = base / exp / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description="The-Test experimental runner (fixture mode)")
    parser.add_argument("--exp", required=True, help="Experiment id (e.g., EXP-001)")
    parser.add_argument("--variant", required=True, choices=["A", "B", "C"], help="Variant id")
    parser.add_argument("--operator", default="fixture-operator", help="Operator name")
    parser.add_argument("--outdir", default=None, help="Output directory (optional)")
    parser.add_argument("--fixture", action="store_true", help="Create a fixture run id (FIXTURE-*)")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    base_runs = repo_root / "datasets" / "runs"

    if args.fixture:
        run_id = allocate_fixture_run_id(args.exp)
    else:
        # For safety in this implementation, fallback to fixture id if not explicitly requested
        run_id = allocate_fixture_run_id(args.exp)

    if args.outdir:
        run_dir = Path(args.outdir)
        run_dir.mkdir(parents=True, exist_ok=True)
    else:
        run_dir = create_run_dir(base_runs, args.exp, run_id)

    # initial run metadata
    run_json: Dict[str, Any] = {
        "run_id": run_id,
        "exp_id": args.exp,
        "variant": args.variant,
        "exp_commit": None,
        "runner_version": RUNNER_VERSION,
        "schema_version": RUN_SCHEMA_VERSION,
        "operator": args.operator,
        "start_time": now_iso(),
        "end_time": None,
        "status": "running",
        "environment_manifest_path": "environment.json",
        "events_path": "events.jsonl",
        "receipt_path": "receipt.json",
        "artifacts": [],
        "derived_metrics": {},
        "notes": "",
        "success": None,
        "failure_stage": None,
    }

    # environment manifest
    env = capture_environment_manifest()
    write_json_atomic(run_dir / "environment.json", env)

    telemetry = Telemetry(run_dir / "events.jsonl")

    # load adapter
    adapter = get_adapter(args.variant, telemetry=telemetry)

    # run the adapter workflow
    try:
        adapter.run_task(exp_id=args.exp)
    except Exception as exc:
        telemetry.emit({
            "timestamp": now_iso(),
            "event_type": "error",
            "source": "adapter",
            "message": str(exc),
        })

    # verifier
    verifier = Verifier()
    receipt = verifier.verify(run_dir)
    write_json_atomic(run_dir / "receipt.json", receipt)

    telemetry.close()

    derived = compute_derived_metrics(run_dir / "events.jsonl")
    run_json["derived_metrics"] = derived
    run_json["end_time"] = now_iso()
    run_json["status"] = "completed"
    run_json["success"] = bool(receipt.get("verified"))
    run_json["failure_stage"] = receipt.get("failure_stage")

    write_json_atomic(run_dir / "run.json", run_json)

    print(f"Fixture run created at: {run_dir}")


if __name__ == "__main__":
    main()
