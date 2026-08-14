import json
from pathlib import Path

import pytest

from prototypes.prt002_abc_harness.api_driver import (
    DRIVER_OUTCOME_FILENAME,
    DRIVER_REGISTRATION_FILENAME,
    SUCCESS_CLAIM,
    ApiDriverError,
    DriverConfig,
    create_api_batch,
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


def test_driver_runs_one_synthetic_trial_with_fake_transport_and_records_verifier_truth(tmp_path):
    batch = make_batch(tmp_path)
    transport = ScriptedTransport()

    outcome = run_next_trial(batch, transport)

    assert len(transport.payloads) == 4
    assert outcome.terminal_error is None
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
    assert not any(path.name.startswith("RUN-") for path in batch.batch_dir.rglob("*"))


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
