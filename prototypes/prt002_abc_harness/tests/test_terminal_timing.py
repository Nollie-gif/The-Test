from pathlib import Path

from prototypes.prt002_abc_harness import api_driver as api_driver_module
from prototypes.prt002_abc_harness import harness as harness_module
from prototypes.prt002_abc_harness.api_driver import (
    DriverConfig,
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


def test_agent_facing_verifier_check_is_non_terminal(tmp_path):
    batch = make_batch(tmp_path)
    trial = batch.open_trial(batch.trial_specs[0].trial_id)

    prepared = trial.call("read_prepared_transaction")
    assert prepared["ok"] is True
    assert trial.call(
        "commit_prepared_transaction",
        transaction_id=prepared["data"]["transaction_id"],
    )["ok"] is True

    assert trial.call("verify_final_state")["ok"] is True
    assert trial._terminal_at_ns is None

    result = trial.finalize()

    assert trial._terminal_at_ns is not None
    assert result["verifier_proof"]["authoritative_success"] is True


def test_completion_time_stops_at_terminal_verifier_before_cleanup(tmp_path, monkeypatch):
    ticks = iter((1_000_000_000, 1_250_000_000, 9_000_000_000))
    monkeypatch.setattr(harness_module.time, "monotonic_ns", lambda: next(ticks))

    original_compute = harness_module.compute_derived_metrics

    def delayed_metrics(path):
        harness_module.time.monotonic_ns()
        return original_compute(path)

    monkeypatch.setattr(harness_module, "compute_derived_metrics", delayed_metrics)

    batch = make_batch(tmp_path)
    trial = batch.open_trial(batch.trial_specs[0].trial_id)

    prepared = trial.call("read_prepared_transaction")
    assert trial.call(
        "commit_prepared_transaction",
        transaction_id=prepared["data"]["transaction_id"],
    )["ok"] is True

    result = trial.finalize()

    assert result["completion_time_ms"] == 250


class TimeoutTransport:
    def create(self, payload):
        raise TimeoutError("synthetic timeout")


def test_transport_abort_boundary_survives_later_finalize(tmp_path, monkeypatch):
    ticks = iter((2_000_000_000, 2_100_000_000, 9_000_000_000))
    monkeypatch.setattr(harness_module.time, "monotonic_ns", lambda: next(ticks))

    batch = create_api_batch(
        tmp_path / "external-prototype-output",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )

    outcome = run_next_trial(batch, TimeoutTransport())

    assert outcome.trial_status == "INCOMPLETE"
    assert outcome.transport_error_kind == "timeout"
    assert outcome.result["completion_time_ms"] == 100



class InvalidJsonArgumentsTransport:
    def create(self, payload):
        return {
            "id": "resp-invalid-json",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call-invalid-json",
                    "name": "read_prepared_transaction",
                    "arguments": "{",
                }
            ],
        }


def test_driver_error_freezes_before_terminal_error_telemetry(tmp_path, monkeypatch):
    ticks = iter((3_000_000_000, 3_100_000_000, 9_000_000_000))
    monkeypatch.setattr(harness_module.time, "monotonic_ns", lambda: next(ticks))

    original_emit = api_driver_module._emit_driver_event

    def delayed_emit(trial, event_type, **fields):
        if event_type == "driver_error" and fields.get("stage") == "tool_arguments":
            harness_module.time.monotonic_ns()
        return original_emit(trial, event_type, **fields)

    monkeypatch.setattr(api_driver_module, "_emit_driver_event", delayed_emit)

    batch = create_api_batch(
        tmp_path / "external-invalid-json",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )

    outcome = run_next_trial(batch, InvalidJsonArgumentsTransport())

    assert outcome.trial_status == "INCOMPLETE"
    assert outcome.result["completion_time_ms"] == 100


class ContinueUntilLimitTransport:
    def __init__(self):
        self.calls = 0

    def create(self, payload):
        self.calls += 1
        return {
            "id": f"resp-limit-{self.calls}",
            "output": [
                {
                    "type": "function_call",
                    "call_id": f"call-limit-{self.calls}",
                    "name": "read_prepared_transaction",
                    "arguments": "{}",
                }
            ],
        }


def test_model_turn_limit_freezes_before_stop_telemetry(tmp_path, monkeypatch):
    ticks = iter((4_000_000_000, 4_200_000_000, 9_000_000_000))
    monkeypatch.setattr(harness_module.time, "monotonic_ns", lambda: next(ticks))

    original_emit = api_driver_module._emit_driver_event

    def delayed_emit(trial, event_type, **fields):
        if event_type == "driver_stop":
            harness_module.time.monotonic_ns()
        return original_emit(trial, event_type, **fields)

    monkeypatch.setattr(api_driver_module, "_emit_driver_event", delayed_emit)

    config = DriverConfig(max_model_turns=1)
    batch = create_api_batch(
        tmp_path / "external-turn-limit",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
        config=config,
    )

    outcome = run_next_trial(
        batch,
        ContinueUntilLimitTransport(),
        config=config,
    )

    assert outcome.trial_status == "INCOMPLETE"
    assert outcome.result["completion_time_ms"] == 200
