import json
from runner.verifier import Verifier
from pathlib import Path


def test_verifier_detects_no_error(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"event_type": "tool_call", "timestamp": "t1"}) + "\n")
    v = Verifier()
    receipt = v.verify(tmp_path)
    assert receipt["verified"] is True


def test_verifier_detects_error(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"event_type": "error", "stage": "execute", "timestamp": "t1"}) + "\n")
    v = Verifier()
    receipt = v.verify(tmp_path)
    assert receipt["verified"] is False
    assert receipt["failure_stage"] == "execute"
