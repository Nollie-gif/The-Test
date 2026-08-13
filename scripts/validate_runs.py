#!/usr/bin/env python3
"""Validate run fixtures under datasets/runs against runner/schemas/run.schema.json.

Only validates runs with run_id or directory names that start with FIXTURE- or TEST-RUN-.
Exits with status 0 on success, non-zero on validation failures or missing dependencies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("jsonschema is required. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


def main():
    repo_root = Path(__file__).resolve().parents[1]
    runs_root = repo_root / "datasets" / "runs"
    schema_path = repo_root / "runner" / "schemas" / "run.schema.json"

    if not schema_path.exists():
        print(f"Schema not found at {schema_path}")
        sys.exit(1)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    failures = 0
    validated = 0
    skipped = 0

    if not runs_root.exists():
        print(f"No runs directory at {runs_root}; nothing to validate.")
        sys.exit(0)

    for exp_dir in runs_root.iterdir():
        if not exp_dir.is_dir():
            continue
        for run_dir in exp_dir.iterdir():
            if not run_dir.is_dir():
                continue
            run_json_path = run_dir / "run.json"
            if not run_json_path.exists():
                print(f"Skipping {run_dir}: no run.json")
                skipped += 1
                continue
            try:
                run_obj = json.loads(run_json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"Failed to read {run_json_path}: {exc}")
                failures += 1
                continue

            run_id = run_obj.get("run_id") or run_dir.name
            if not (str(run_id).startswith("FIXTURE-") or str(run_id).startswith("TEST-RUN-")):
                print(f"Skipping {run_dir}: run_id {run_id} not a fixture/test-run")
                skipped += 1
                continue

            try:
                jsonschema.validate(instance=run_obj, schema=schema)
                print(f"Validated: {run_dir}")
                validated += 1
            except jsonschema.ValidationError as ve:
                print(f"Validation failed for {run_dir}: {ve.message}")
                failures += 1

    print(f"Summary: validated={validated}, skipped={skipped}, failures={failures}")
    if failures:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
