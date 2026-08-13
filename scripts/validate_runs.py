#!/usr/bin/env python3
"""Validate non-evidentiary runner fixtures only.

Only FIXTURE-* and TEST-RUN-* directories are considered. Canonical RUN-*
research artifacts remain the responsibility of validate_research_repo.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("jsonschema is required. Install with: pip install -r requirements-dev.txt", file=sys.stderr)
    sys.exit(2)


FIXTURE_PREFIXES = ("FIXTURE-", "TEST-RUN-")
RECEIPT_FIELDS = {
    "fixture_verified",
    "verifier",
    "verified_at",
    "authoritative",
    "failure_stage",
    "details",
}


def fixture_sidecar_path(run_dir: Path, raw_path: object) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path:
        return None
    candidate = Path(raw_path)
    if candidate.is_absolute() or candidate.name != raw_path:
        return None
    return run_dir / candidate


def validate_events(path: Path) -> list[str]:
    errors: list[str] = []
    previous_sequence = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"events.jsonl line {line_number}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(event, dict):
            errors.append(f"events.jsonl line {line_number}: event must be an object")
            continue
        if not isinstance(event.get("event_type"), str) or not event["event_type"]:
            errors.append(f"events.jsonl line {line_number}: missing event_type")
        sequence = event.get("sequence")
        if not isinstance(sequence, int) or sequence <= previous_sequence:
            errors.append(f"events.jsonl line {line_number}: sequence must be strictly increasing")
        else:
            previous_sequence = sequence
    return errors


def validate_sidecars(run_dir: Path, run_obj: dict[str, object]) -> list[str]:
    errors: list[str] = []
    paths: dict[str, Path] = {}
    for field in ("environment_manifest_path", "events_path", "receipt_path"):
        path = fixture_sidecar_path(run_dir, run_obj.get(field))
        if path is None or not path.is_file():
            errors.append(f"{field}: missing or unsafe fixture sidecar")
        else:
            paths[field] = path

    for field in ("environment_manifest_path", "receipt_path"):
        path = paths.get(field)
        if path is None:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}: invalid JSON ({exc.msg})")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}: must contain an object")
            continue
        if field == "receipt_path":
            missing = RECEIPT_FIELDS - set(value)
            if missing:
                errors.append(f"receipt.json: missing fields {sorted(missing)}")
            elif value.get("authoritative") is not False:
                errors.append("receipt.json: fixture receipt must be non-authoritative")
            elif value.get("fixture_verified") != run_obj.get("fixture_verified"):
                errors.append("receipt.json: fixture_verified does not match run.json")

    events_path = paths.get("events_path")
    if events_path is not None:
        errors.extend(validate_events(events_path))
    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    runs_root = repo_root / "datasets" / "runs"
    schema_path = repo_root / "runner" / "schemas" / "fixture.schema.json"

    if not schema_path.exists():
        print(f"Fixture schema not found at {schema_path}")
        return 1
    if not runs_root.exists():
        print(f"No runs directory at {runs_root}; nothing to validate.")
        return 0

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        schema,
        format_checker=jsonschema.FormatChecker(),
    )
    failures = 0
    validated = 0
    skipped = 0

    for experiment_dir in sorted(runs_root.iterdir()):
        if not experiment_dir.is_dir():
            continue
        for run_dir in sorted(experiment_dir.iterdir()):
            if not run_dir.is_dir():
                continue
            run_json_path = run_dir / "run.json"
            if not run_json_path.exists():
                print(f"Skipping {run_dir}: no run.json")
                skipped += 1
                continue
            try:
                run_obj = json.loads(run_json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                print(f"Validation failed for {run_dir}: invalid run.json ({exc.msg})")
                failures += 1
                continue
            if not isinstance(run_obj, dict):
                print(f"Validation failed for {run_dir}: run.json must contain an object")
                failures += 1
                continue

            run_id = str(run_obj.get("run_id") or run_dir.name)
            if not run_id.startswith(FIXTURE_PREFIXES):
                print(f"Skipping {run_dir}: run_id {run_id} not a fixture/test-run")
                skipped += 1
                continue

            errors = [error.message for error in sorted(validator.iter_errors(run_obj), key=str)]
            if run_dir.name != run_id:
                errors.append("fixture directory name must match run_id")
            errors.extend(validate_sidecars(run_dir, run_obj))
            if errors:
                print(f"Validation failed for {run_dir}:")
                for error in errors:
                    print(f" - {error}")
                failures += 1
            else:
                print(f"Validated: {run_dir}")
                validated += 1

    print(f"Summary: validated={validated}, skipped={skipped}, failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
