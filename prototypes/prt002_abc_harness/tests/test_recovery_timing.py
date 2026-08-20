import json
from pathlib import Path

from prototypes.prt002_abc_harness import harness as harness_module
from prototypes.prt002_abc_harness.api_driver import (
    create_api_batch,
    run_next_trial,
)
from prototypes.prt002_abc_harness.harness import PreregisteredBatch


def make_batch(tmp_path: Path) -> PreregisteredBatch:
    return PreregisteredBatch.create(
        tmp_path / "prototype-output",
        agent_model="test-model/example-1",
        operator="pytest",
        source_revision="test-revision",
        repeats_per_variant=3,
    )


def read_events(trial):
    return [
        json.loads(line)
        for line in (trial.trial_dir / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]


def test_recovery_time_uses_monotonic_error_to_completion_boundaries(
    tmp_path,
    monkeypatch,
):
    ticks = iter(
        (
            1_000_000_000,
            1_100_000_000,
            9_000_000_000,
            1_400_000_000,
            2_000_000_000,
        )
    )
    monkeypatch.setattr(
        harness_module.time,
        "monotonic_ns",
        lambda: next(ticks),
    )

    batch = make_batch(tmp_path)
    trial = batch.open_trial(batch.trial_specs[0].trial_id)

    original_emit = trial.telemetry.emit

    def delayed_error_emit(event):
        if (
            event.get("event_type") == "tool_call"
            and event.get("result") == "error"
        ):
            harness_module.time.monotonic_ns()
        return original_emit(event)

    monkeypatch.setattr(
        trial.telemetry,
        "emit",
        delayed_error_emit,
    )

    wrong_tool = trial.call("quicksave")
    assert wrong_tool["error_code"] == "wrong_tool"

    prepared = trial.call("read_prepared_transaction")
    assert prepared["ok"] is True

    committed = trial.call(
        "commit_prepared_transaction",
        transaction_id=prepared["data"]["transaction_id"],
    )
    assert committed["ok"] is True

    trial.record_recovery_action(
        "used the exposed variant-A transaction path"
    )
    proof = trial.record_recovery_complete()
    assert proof["authoritative_success"] is True

    result = trial.finalize()

    assert result["diagnostic_metrics"]["recovery_time_ms"] == 300

    recovery_events = [
        event
        for event in read_events(trial)
        if event.get("event_type") == "recovery_complete"
    ]

    assert len(recovery_events) == 1
    assert recovery_events[0]["recovery_time_ms"] == 300


def test_error_without_completed_recovery_records_null(
    tmp_path,
    monkeypatch,
):
    ticks = iter(
        (
            2_000_000_000,
            2_100_000_000,
            2_500_000_000,
        )
    )
    monkeypatch.setattr(
        harness_module.time,
        "monotonic_ns",
        lambda: next(ticks),
    )

    batch = make_batch(tmp_path)
    trial = batch.open_trial(batch.trial_specs[0].trial_id)

    wrong_tool = trial.call("quicksave")
    assert wrong_tool["error_code"] == "wrong_tool"

    result = trial.finalize()

    assert result["diagnostic_metrics"]["recovery_time_ms"] is None


def test_no_error_records_zero_recovery_time(
    tmp_path,
    monkeypatch,
):
    ticks = iter(
        (
            3_000_000_000,
            3_500_000_000,
        )
    )
    monkeypatch.setattr(
        harness_module.time,
        "monotonic_ns",
        lambda: next(ticks),
    )

    batch = make_batch(tmp_path)
    trial = batch.open_trial(batch.trial_specs[0].trial_id)

    result = trial.finalize()

    assert result["diagnostic_metrics"]["recovery_time_ms"] == 0



class RecoveryTimeoutTransport:
    def create(self, payload):
        raise TimeoutError("synthetic timeout")


def test_terminal_transport_error_has_null_recovery_time(
    tmp_path,
    monkeypatch,
):
    ticks = iter((4_000_000_000, 4_200_000_000))
    monkeypatch.setattr(
        harness_module.time,
        "monotonic_ns",
        lambda: next(ticks),
    )

    batch = create_api_batch(
        tmp_path / "external-transport-error",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )

    outcome = run_next_trial(
        batch,
        RecoveryTimeoutTransport(),
    )

    assert outcome.trial_status == "INCOMPLETE"
    assert outcome.result["completion_time_ms"] == 200
    assert (
        outcome.result["diagnostic_metrics"]["recovery_time_ms"]
        is None
    )

    events_path = (
        batch.trial_dir(batch.trial_specs[0])
        / "events.jsonl"
    )
    events = [
        json.loads(line)
        for line in events_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    incomplete = [
        event
        for event in events
        if event.get("event_type")
        == "api_request_incomplete"
    ]

    assert len(incomplete) == 1
    assert (
        incomplete[0]["monotonic_elapsed_ns"]
        == 200_000_000
    )


class RecoveryInvalidJsonTransport:
    def create(self, payload):
        return {
            "id": "resp-invalid-json-recovery",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call-invalid-json-recovery",
                    "name": "read_prepared_transaction",
                    "arguments": "{",
                }
            ],
        }


def test_terminal_driver_error_has_null_recovery_time(
    tmp_path,
    monkeypatch,
):
    ticks = iter((5_000_000_000, 5_150_000_000))
    monkeypatch.setattr(
        harness_module.time,
        "monotonic_ns",
        lambda: next(ticks),
    )

    batch = create_api_batch(
        tmp_path / "external-driver-error",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )

    outcome = run_next_trial(
        batch,
        RecoveryInvalidJsonTransport(),
    )

    assert outcome.trial_status == "INCOMPLETE"
    assert outcome.result["completion_time_ms"] == 150
    assert (
        outcome.result["diagnostic_metrics"]["recovery_time_ms"]
        is None
    )

    events_path = (
        batch.trial_dir(batch.trial_specs[0])
        / "events.jsonl"
    )
    events = [
        json.loads(line)
        for line in events_path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    driver_errors = [
        event
        for event in events
        if event.get("event_type") == "driver_error"
    ]

    assert driver_errors
    assert all(
        event["monotonic_elapsed_ns"]
        == 150_000_000
        for event in driver_errors
    )
