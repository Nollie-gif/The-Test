import json
import subprocess
from pathlib import Path
import sys

from jsonschema import validate

from runner import runner as runner_module


def test_runner_fixture_end_to_end(tmp_path):
    outdir = tmp_path / "out_run"
    # run runner in fixture mode and write into outdir
    argv = [
        "--exp",
        "EXP-TEST",
        "--variant",
        "A",
        "--fixture",
        "--outdir",
        str(outdir),
    ]
    runner_module.main(argv)

    # verify files created
    run_json_path = outdir / "run.json"
    receipt_path = outdir / "receipt.json"
    events_path = outdir / "events.jsonl"
    env_path = outdir / "environment.json"

    assert run_json_path.exists()
    assert receipt_path.exists()
    assert events_path.exists()
    assert env_path.exists()

    run_obj = json.loads(run_json_path.read_text(encoding="utf-8"))
    # basic schema validation
    schema_path = Path(__file__).resolve().parents[2] / "runner" / "schemas" / "run.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validate(instance=run_obj, schema=schema)

    # receipt determines success
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert "verified" in receipt

    # events are structured JSON lines
    lines = [l for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    for line in lines:
        obj = json.loads(line)
        assert "event_type" in obj
