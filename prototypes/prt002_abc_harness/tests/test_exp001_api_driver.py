import json
from pathlib import Path

import pytest

from prototypes.prt002_abc_harness.api_driver import ApiDriverError, DEFAULT_DRIVER_CONFIG
from prototypes.prt002_abc_harness.completion_cycle import FROZEN_MODEL_SETTINGS
from prototypes.prt002_abc_harness.exp001_api_driver import (
    EXP001_API_MODEL,
    EXP001_AUTOMATIC_RETRIES,
    EXP001_DRIVER_CONFIG,
    EXP001_EXECUTION_PROFILE,
    EXP001_MODEL_FALLBACK,
    EXP001_REQUEST_TIMEOUT_SECONDS,
    create_exp001_api_batch,
    load_exp001_api_batch,
    plan_exp001_next,
)


def make_batch(tmp_path: Path):
    return create_exp001_api_batch(
        tmp_path / "external-exp001-output",
        operator="pytest",
        source_revision="exp001-test-revision",
        driver_source_revision="exp001-driver-test-revision",
    )


def test_exp001_profile_matches_frozen_completion_cycle_settings():
    assert EXP001_API_MODEL == "gpt-5.6-sol"
    assert EXP001_DRIVER_CONFIG.reasoning_effort == "medium"
    assert EXP001_DRIVER_CONFIG.max_output_tokens_per_turn == 1000
    assert EXP001_REQUEST_TIMEOUT_SECONDS == 90
    assert EXP001_AUTOMATIC_RETRIES == 0
    assert EXP001_MODEL_FALLBACK is None
    assert FROZEN_MODEL_SETTINGS == {
        "model_family": "GPT-5.6 Sol",
        "reasoning_effort": "medium",
        "sampling_controls": "provider-defaults",
        "max_output_tokens": 1000,
        "timeout_seconds": 90,
        "automatic_retry": False,
        "model_fallback": False,
    }


def test_exp001_batch_freezes_30_trials_and_sol_request_without_network(tmp_path):
    batch = make_batch(tmp_path)

    assert len(batch.trial_specs) == 30
    assert batch.manifest["agent_model"] == "gpt-5.6-sol"
    assert batch.manifest["repeats_per_variant"] == 10
    assert batch.manifest["live_execution_authorized"] is False
    assert batch.manifest["canonical_run_export_authorized"] is False

    plan = plan_exp001_next(batch)
    assert plan["network_performed"] is False
    assert plan["model_config"] == EXP001_DRIVER_CONFIG.as_dict()
    assert plan["request"]["model"] == "gpt-5.6-sol"
    assert plan["request"]["reasoning"] == {"effort": "medium"}
    assert plan["request"]["max_output_tokens"] == 1000
    assert plan["request"]["store"] is False
    assert plan["request"]["parallel_tool_calls"] is False


def test_exp001_registration_records_request_policy_and_profile(tmp_path):
    batch = make_batch(tmp_path)
    registration = json.loads(
        (batch.batch_dir / "api-driver-registration.json").read_text(encoding="utf-8")
    )

    assert registration["execution_profile"] == EXP001_EXECUTION_PROFILE
    assert registration["model_config"] == EXP001_DRIVER_CONFIG.as_dict()
    assert registration["frozen_model_settings"] == FROZEN_MODEL_SETTINGS
    assert registration["request_policy"] == {
        "timeout_seconds": 90,
        "automatic_retries": 0,
        "model_fallback": None,
    }
    assert registration["live_run_guard"]["max_output_tokens_per_turn"] == 1000


def test_exp001_loader_rejects_historical_terra_batch(tmp_path):
    from prototypes.prt002_abc_harness.api_driver import create_api_batch

    historical = create_api_batch(
        tmp_path / "historical-terra-output",
        operator="pytest",
        source_revision="historical-test",
        driver_source_revision="historical-test",
    )

    with pytest.raises(ApiDriverError, match="frozen 30-trial research-cycle batch"):
        load_exp001_api_batch(historical.batch_dir)


def test_historical_default_driver_remains_terra_for_terminal_pilot_reproducibility():
    assert DEFAULT_DRIVER_CONFIG.model == "gpt-5.6-terra"
    assert DEFAULT_DRIVER_CONFIG.max_output_tokens_per_turn == 512
