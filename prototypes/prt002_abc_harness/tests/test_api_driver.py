import json
import ssl
import urllib.error
from pathlib import Path

import pytest

from prototypes.prt002_abc_harness.api_driver import (
    DRIVER_OUTCOME_FILENAME,
    DRIVER_RECEIPT_FILENAME,
    DRIVER_REGISTRATION_FILENAME,
    SUCCESS_CLAIM,
    ApiDriverError,
    DriverConfig,
    DISPOSABLE_PILOT_CONFIG,
    HttpResponsesTransport,
    _transport_error_kind,
    _enforce_disposable_cost_envelope,
    create_disposable_pilot_batch,
    create_api_batch,
    inspect_interrupted_trials,
    load_api_batch,
    main,
    plan_next_trial,
    run_next_trial,
)


class ScriptedTransport:
    """A local fake Responses API that proves PRT-003 without network or credentials."""

    def __init__(self):
        self.payloads = []

    def create(self, payload):
        self.payloads.append(payload)
        turn = len(self.payloads)

        if turn == 1:
            return {
                "id": "resp-read-prepared",
                "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-read-prepared",
                        "name": "read_prepared_transaction",
                        "arguments": "{}",
                    }
                ],
            }

        if turn == 2:
            function_output = self.payloads[-1]["input"][-1]
            assert function_output["type"] == "function_call_output"
            prepared = json.loads(function_output["output"])
            transaction_id = prepared["data"]["transaction_id"]
            return {
                "id": "resp-commit",
                "usage": {"input_tokens": 12, "output_tokens": 5, "total_tokens": 17},
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-commit",
                        "name": "commit_prepared_transaction",
                        "arguments": json.dumps({"transaction_id": transaction_id}),
                    }
                ],
            }

        if turn == 3:
            return {
                "id": "resp-verify",
                "usage": {"input_tokens": 14, "output_tokens": 4, "total_tokens": 18},
                "output": [
                    {
                        "type": "function_call",
                        "call_id": "call-verify",
                        "name": "verify_final_state",
                        "arguments": "{}",
                    }
                ],
            }

        assert turn == 4
        return {
            "id": "resp-final",
            "usage": {"input_tokens": 15, "output_tokens": 2, "total_tokens": 17},
            "output_text": SUCCESS_CLAIM,
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": SUCCESS_CLAIM}],
                }
            ],
        }


class TimeoutTransport:
    """A local timeout after the driver has durably marked a request as started."""

    def __init__(self):
        self.payloads = []

    def create(self, payload):
        self.payloads.append(payload)
        raise TimeoutError("synthetic transport timeout")


class NetworkErrorTransport:
    """A local network error after the driver has marked a request as started."""

    def create(self, payload):
        raise urllib.error.URLError("synthetic network failure")


class CrashAfterStartedTransport:
    """Simulates process termination after the durable request-started journal event."""

    def __init__(self):
        self.payloads = []

    def create(self, payload):
        self.payloads.append(payload)
        raise KeyboardInterrupt("synthetic process termination")


class NeverCalledTransport:
    """Fails the test if restart handling ever attempts another API request."""

    def __init__(self):
        self.payloads = []

    def create(self, payload):
        self.payloads.append(payload)
        raise AssertionError("an interrupted trial must never be retried or resumed")


def make_batch(tmp_path: Path):
    return create_api_batch(
        tmp_path / "external-prototype-output",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )


def test_create_and_plan_are_external_noncanonical_and_never_make_a_network_call(tmp_path):
    batch = make_batch(tmp_path)

    assert (batch.batch_dir / "batch.json").is_file()
    assert (batch.batch_dir / DRIVER_REGISTRATION_FILENAME).is_file()
    assert not (batch.batch_dir / "trials").exists()

    plan = plan_next_trial(batch)

    assert plan["network_performed"] is False
    assert plan["evidence_status"] == "synthetic-prototype-only-not-a-RUN"
    assert plan["request"]["model"] == "gpt-5.6-terra"
    assert plan["request"]["reasoning"] == {"effort": "medium"}
    assert plan["request"]["parallel_tool_calls"] is False
    assert len(plan["request"]["tools"]) == 6
    assert "RUN-001" not in json.dumps(plan)


def test_disposable_pilot_is_one_variant_c_trial_with_frozen_cost_and_no_recap(tmp_path):
    batch = create_disposable_pilot_batch(
        tmp_path / "external-pilot", operator="pytest", source_revision="main-test", driver_source_revision="main-test"
    )
    assert len(batch.trial_specs) == 1
    assert batch.trial_specs[0].variant == "C"
    assert batch.manifest["batch_mode"] == "disposable-single-trial"
    plan = plan_next_trial(batch, config=DISPOSABLE_PILOT_CONFIG)
    assert plan["model_config"]["max_model_turns"] == 4
    assert plan["model_config"]["max_total_estimated_cost_usd"] == 0.10
    assert plan["model_config"]["input_usd_per_million"] == 2.0
    assert plan["model_config"]["output_usd_per_million"] == 12.0
    assert plan["request"]["store"] is False
    assert not ({"previous_response_id", "conversation", "background", "summary"} & set(plan["request"]))


def test_disposable_pilot_rejects_a_payload_that_could_exceed_its_frozen_budget(tmp_path):
    too_small = DriverConfig(
        max_model_turns=4,
        max_output_tokens_per_turn=512,
        max_request_bytes=1,
        max_total_estimated_cost_usd=0.10,
        input_usd_per_million=2.0,
        output_usd_per_million=12.0,
    )
    with pytest.raises(ApiDriverError, match="input-byte ceiling"):
        _enforce_disposable_cost_envelope({"model": "gpt-5.6-terra"}, too_small, attempt=1)


def test_driver_runs_one_synthetic_trial_with_fake_transport_and_records_verifier_truth(tmp_path):
    batch = make_batch(tmp_path)
    transport = ScriptedTransport()

    outcome = run_next_trial(batch, transport)

    assert len(transport.payloads) == 4
    assert all(payload["store"] is False for payload in transport.payloads)
    assert outcome.terminal_error is None
    assert outcome.transport_error_kind is None
    assert outcome.model_response_ids == (
        "resp-read-prepared",
        "resp-commit",
        "resp-verify",
        "resp-final",
    )
    assert outcome.result["agent_success_claimed"] is True
    assert outcome.result["false_success"] is False
    assert outcome.result["verifier_proof"]["authoritative_success"] is True
    assert outcome.result["verifier_proof"]["final_state_correct"] is True
    assert outcome.result["verifier_proof"]["receipt_complete"] is True

    trial_dir = batch.trial_dir(batch.trial_specs[0])
    assert (trial_dir / "result.json").is_file()
    assert (trial_dir / DRIVER_OUTCOME_FILENAME).is_file()
    assert (trial_dir / DRIVER_RECEIPT_FILENAME).is_file()
    assert not any(path.name.startswith("RUN-") for path in batch.batch_dir.rglob("*"))

    events = [json.loads(line) for line in (trial_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    started = [event for event in events if event["event_type"] == "api_request_started"]
    observed = [event for event in events if event["event_type"] == "api_response_observed"]
    receipt = json.loads((trial_dir / DRIVER_RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert len(started) == len(observed) == 4
    assert started[0]["sequence"] < observed[0]["sequence"]
    assert "request_fingerprint" in started[0]
    assert "instructions" not in started[0]
    assert receipt["trial_status"] == "COMPLETE"
    assert receipt["acceptance_status"] == "SYNTHETIC_COMPLETE_NOT_A_RUN"


def test_driver_records_unknown_request_outcome_and_rejects_the_trial_after_timeout(tmp_path):
    batch = make_batch(tmp_path)
    transport = TimeoutTransport()

    outcome = run_next_trial(batch, transport)

    assert len(transport.payloads) == 1
    assert outcome.trial_status == "INCOMPLETE"
    assert outcome.request_attempts == 1
    assert outcome.unknown_request_attempts == 1
    assert outcome.terminal_error == (
        "Responses transport ended after request_started; request outcome is UNKNOWN/INCOMPLETE"
    )
    assert outcome.transport_error_kind == "timeout"
    assert outcome.result["verifier_proof"]["authoritative_success"] is False

    trial_dir = batch.trial_dir(batch.trial_specs[0])
    events = [json.loads(line) for line in (trial_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    started = [event for event in events if event["event_type"] == "api_request_started"]
    incomplete = [event for event in events if event["event_type"] == "api_request_incomplete"]
    receipt = json.loads((trial_dir / DRIVER_RECEIPT_FILENAME).read_text(encoding="utf-8"))
    outcome_artifact = json.loads((trial_dir / DRIVER_OUTCOME_FILENAME).read_text(encoding="utf-8"))
    assert len(started) == len(incomplete) == 1
    assert started[0]["sequence"] < incomplete[0]["sequence"]
    assert incomplete[0]["outcome_status"] == "UNKNOWN"
    assert incomplete[0]["error_kind"] == "timeout"
    assert "synthetic transport timeout" not in json.dumps(incomplete)
    assert outcome_artifact["transport_error_kind"] == "timeout"
    assert "synthetic transport timeout" not in json.dumps(outcome_artifact)
    assert receipt["trial_status"] == "INCOMPLETE"
    assert receipt["acceptance_status"] == "NOT_ACCEPTED"
    assert receipt["unknown_request_attempts"] == 1
    assert receipt["transport_error_kind"] == "timeout"
    assert "synthetic transport timeout" not in json.dumps(receipt)


@pytest.mark.parametrize(
    ("exc", "expected_kind"),
    [
        (TimeoutError("synthetic timeout"), "timeout"),
        (urllib.error.URLError("synthetic network failure"), "network_error"),
        (ApiDriverError("synthetic API-driver failure"), "api_driver_error"),
        (RuntimeError("synthetic transport failure"), "transport_error"),
    ],
)
def test_transport_error_kind_uses_only_allowlisted_categories(exc, expected_kind):
    assert _transport_error_kind(exc) == expected_kind


def test_http_transport_tls_preflight_blocks_unusable_sslkeylogfile_without_network(
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SSLKEYLOGFILE", "protected-virtual-file")

    def refuse_tls_context():
        raise PermissionError("synthetic protected file")

    monkeypatch.setattr(ssl, "create_default_context", refuse_tls_context)

    with pytest.raises(ApiDriverError, match="SSLKEYLOGFILE is unusable"):
        HttpResponsesTransport().preflight()


def test_http_transport_tls_preflight_never_persists_or_echoes_the_os_error(
    monkeypatch,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("SSLKEYLOGFILE", "protected-virtual-file")

    def refuse_tls_context():
        raise PermissionError("synthetic protected file")

    monkeypatch.setattr(ssl, "create_default_context", refuse_tls_context)

    with pytest.raises(ApiDriverError) as error:
        HttpResponsesTransport().preflight()
    assert "synthetic protected file" not in str(error.value)


def test_driver_persists_network_error_kind_without_raw_error_text(tmp_path):
    batch = make_batch(tmp_path)

    outcome = run_next_trial(batch, NetworkErrorTransport())

    trial_dir = batch.trial_dir(batch.trial_specs[0])
    outcome_artifact = json.loads((trial_dir / DRIVER_OUTCOME_FILENAME).read_text(encoding="utf-8"))
    receipt = json.loads((trial_dir / DRIVER_RECEIPT_FILENAME).read_text(encoding="utf-8"))
    assert outcome.transport_error_kind == "network_error"
    assert outcome_artifact["transport_error_kind"] == "network_error"
    assert receipt["transport_error_kind"] == "network_error"
    assert "synthetic network failure" not in json.dumps(outcome_artifact)
    assert "synthetic network failure" not in json.dumps(receipt)


def test_restart_after_durable_request_started_stops_without_retry_or_resume(tmp_path, monkeypatch, capsys):
    batch = make_batch(tmp_path)
    crash_transport = CrashAfterStartedTransport()
    opened_trials = []
    original_open_trial = batch.open_trial

    def capture_open_trial(trial_id):
        trial = original_open_trial(trial_id)
        opened_trials.append(trial)
        return trial

    monkeypatch.setattr(batch, "open_trial", capture_open_trial)
    with pytest.raises(KeyboardInterrupt, match="synthetic process termination"):
        run_next_trial(batch, crash_transport)
    opened_trials[0].telemetry.close()  # Mimics file-handle cleanup after process termination.

    trial_dir = batch.trial_dir(batch.trial_specs[0])
    assert len(crash_transport.payloads) == 1
    assert (trial_dir / "result.json").exists() is False
    assert (trial_dir / DRIVER_OUTCOME_FILENAME).exists() is False
    assert (trial_dir / DRIVER_RECEIPT_FILENAME).exists() is False

    fresh_batch = load_api_batch(batch.batch_dir)
    report = inspect_interrupted_trials(fresh_batch)
    assert report["inspection_status"] == "RECOVERY_STOP_REQUIRED"
    assert report["network_performed"] is False
    assert report["mutation_performed"] is False
    assert report["next_safe_action"] == "DO_NOT_RETRY_OR_RESUME"
    assert len(report["interrupted_trials"]) == 1
    interrupted = report["interrupted_trials"][0]
    assert interrupted["request_outcome"] == "UNKNOWN"
    assert interrupted["api_request_started_count"] == 1
    assert interrupted["unresolved_request_starts"] == 1
    assert interrupted["retry_permitted"] is False
    assert interrupted["resume_permitted"] is False

    main(["inspect-interrupted", "--batch-dir", str(fresh_batch.batch_dir)])
    cli_report = json.loads(capsys.readouterr().out)
    assert cli_report["inspection_status"] == "RECOVERY_STOP_REQUIRED"

    blocked_transport = NeverCalledTransport()
    with pytest.raises(ApiDriverError, match="do not retry or resume"):
        plan_next_trial(fresh_batch)
    with pytest.raises(ApiDriverError, match="do not retry or resume"):
        run_next_trial(fresh_batch, blocked_transport)
    assert blocked_transport.payloads == []
    assert len(list((fresh_batch.batch_dir / "trials").iterdir())) == 1


def test_driver_refuses_config_drift_and_tampered_registration_before_opening_a_trial(tmp_path):
    batch = make_batch(tmp_path)

    with pytest.raises(ApiDriverError, match="differs from the pre-registered fixed pilot"):
        plan_next_trial(batch, config=DriverConfig(reasoning_effort="low"))

    registration_path = batch.batch_dir / DRIVER_REGISTRATION_FILENAME
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    registration["model_config"]["reasoning_effort"] = "low"
    registration_path.write_text(json.dumps(registration), encoding="utf-8")

    with pytest.raises(ApiDriverError, match="digest"):
        load_api_batch(batch.batch_dir)
    assert not (batch.batch_dir / "trials").exists()


def test_cli_refuses_any_live_request_without_both_explicit_flags(tmp_path):
    batch = make_batch(tmp_path)

    with pytest.raises(SystemExit, match="--live and --confirm-live-run"):
        main(["run-next", "--batch-dir", str(batch.batch_dir)])
