from runner.telemetry import Telemetry
import json


def test_telemetry_order(tmp_path):
    p = tmp_path / "events.jsonl"
    t = Telemetry(p)
    t.emit({"timestamp": "t1", "event_type": "tool_call", "tool": "a"})
    t.emit({"timestamp": "t2", "event_type": "tool_call", "tool": "b"})
    t.close()

    data = p.read_text(encoding="utf-8").splitlines()
    assert len(data) == 2
    e1 = json.loads(data[0])
    e2 = json.loads(data[1])
    assert e1["event_type"] == "tool_call"
    assert e2["event_type"] == "tool_call"
    assert e1["sequence"] == 1
    assert e2["sequence"] == 2
    assert "seq" not in e1
