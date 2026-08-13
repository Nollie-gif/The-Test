import json
from runner.verifier import FixtureVerifier
from pathlib import Path


def test_verifier_detects_no_error(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"event_type": "tool_call", "timestamp": "t1"}) + "\n")
    v = FixtureVerifier()
    receipt = v.verify(tmp_path)
    assert receipt["fixture_verified"] is True
    assert receipt["authoritative"] is False


def test_verifier_detects_error(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(json.dumps({"event_type": "error", "stage": "execute", "timestamp": "t1"}) + "\n")
    v = FixtureVerifier()
    receipt = v.verify(tmp_path)
    assert receipt["fixture_verified"] is False
    assert receipt["failure_stage"] == "execute"


def test_verifier_detects_error_coded_tool_call(tmp_path):
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps(
            {
                "event_type": "tool_call",
                "error_code": "permission_denied",
                "timestamp": "t1",
            }
        )
        + "\n"
    )
    receipt = FixtureVerifier().verify(tmp_path)
    assert receipt["fixture_verified"] is False
    assert receipt["failure_stage"] == "tool_call"
