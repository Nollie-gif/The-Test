import json
from pathlib import Path

import pytest

from prototypes.prt001_controlled_quicksave.common import digest
from prototypes.prt002_abc_harness.api_driver import create_api_batch, main, run_next_trial
from prototypes.prt002_abc_harness.evidence import (
    EVIDENCE_MANIFEST_FILENAME,
    EvidenceValidationError,
    archive_external_batch,
    validate_external_batch,
)


class TimeoutTransport:
    """Local transport that leaves a terminal UNKNOWN/INCOMPLETE receipt."""

    def create(self, _payload):
        raise TimeoutError("synthetic transport timeout")


class CrashAfterStartedTransport:
    """Local process-stop simulation after the durable request-started event."""

    def create(self, _payload):
        raise KeyboardInterrupt("synthetic process termination")


def make_batch(tmp_path: Path):
    return create_api_batch(
        tmp_path / "external-prototype-output",
        operator="pytest",
        source_revision="prt002-test-revision",
        driver_source_revision="prt003-test-revision",
    )


def terminal_timeout_batch(tmp_path: Path):
    batch = make_batch(tmp_path)
    for _ in batch.trial_specs:
        outcome = run_next_trial(batch, TimeoutTransport())
        assert outcome.trial_status == "INCOMPLETE"
    return batch


def test_terminal_external_batch_can_be_archived_without_network_or_a_run(tmp_path, capsys):
    batch = terminal_timeout_batch(tmp_path)

    report = validate_external_batch(batch.batch_dir)

    assert report["validation_status"] == "ARCHIVE_READY"
    assert report["archive_permitted"] is True
    assert report["network_performed"] is False
    assert report["mutation_performed"] is False
    assert {trial["evidence_state"] for trial in report["trials"]} == {"INCOMPLETE"}

    main(["validate-external-evidence", "--batch-dir", str(batch.batch_dir)])
    cli_report = json.loads(capsys.readouterr().out)
    assert cli_report["validation_status"] == "ARCHIVE_READY"

    manifest = archive_external_batch(batch.batch_dir)

    assert manifest["archive_status"] == "TERMINAL_NONCANONICAL_BATCH"
    assert (batch.batch_dir / EVIDENCE_MANIFEST_FILENAME).is_file()
    assert len(manifest["artifacts"]) == 2 + len(batch.trial_specs) * 5

    archived = validate_external_batch(batch.batch_dir)
    assert archived["validation_status"] == "ARCHIVED_VALID"
    assert archived["archive_permitted"] is False
    assert archived["network_performed"] is False
    assert archived["mutation_performed"] is False

    with pytest.raises(EvidenceValidationError, match="not archive-ready"):
        archive_external_batch(batch.batch_dir)


def test_active_external_batch_cannot_be_archived(tmp_path, capsys):
    batch = make_batch(tmp_path)

    report = validate_external_batch(batch.batch_dir)

    assert report["validation_status"] == "ACTIVE_NOT_ARCHIVABLE"
    assert report["next_safe_action"] == "COMPLETE_OR_EXPLICITLY_STOP_EVERY_PREREGISTERED_TRIAL"
    assert not (batch.batch_dir / EVIDENCE_MANIFEST_FILENAME).exists()
    with pytest.raises(EvidenceValidationError, match="not archive-ready"):
        archive_external_batch(batch.batch_dir)

    with pytest.raises(SystemExit, match="1"):
        main(["validate-external-evidence", "--batch-dir", str(batch.batch_dir)])
    cli_report = json.loads(capsys.readouterr().out)
    assert cli_report["validation_status"] == "ACTIVE_NOT_ARCHIVABLE"


def test_interrupted_external_batch_is_stop_required_and_never_archived(tmp_path, monkeypatch):
    batch = make_batch(tmp_path)
    opened_trials = []
    original_open_trial = batch.open_trial

    def capture_open_trial(trial_id):
        trial = original_open_trial(trial_id)
        opened_trials.append(trial)
        return trial

    monkeypatch.setattr(batch, "open_trial", capture_open_trial)
    with pytest.raises(KeyboardInterrupt, match="synthetic process termination"):
        run_next_trial(batch, CrashAfterStartedTransport())
    opened_trials[0].telemetry.close()

    report = validate_external_batch(batch.batch_dir)

    assert report["validation_status"] == "STOP_REQUIRED"
    assert report["next_safe_action"] == "DO_NOT_RETRY_OR_RESUME"
    interrupted = next(trial for trial in report["trials"] if "evidence_state" in trial)
    assert interrupted["evidence_state"] == "INTERRUPTED_STOP_REQUIRED"
    assert interrupted["request_outcome"] == "UNKNOWN"
    assert not (batch.batch_dir / EVIDENCE_MANIFEST_FILENAME).exists()
    with pytest.raises(EvidenceValidationError, match="not archive-ready"):
        archive_external_batch(batch.batch_dir)


def test_manifest_detects_terminal_artifact_tampering(tmp_path):
    batch = terminal_timeout_batch(tmp_path)
    archive_external_batch(batch.batch_dir)
    first_trial = batch.trial_dir(batch.trial_specs[0])
    receipt_path = first_trial / "api-driver-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["terminal_error"] = "tampered after archive"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    report = validate_external_batch(batch.batch_dir)

    assert report["validation_status"] == "INVALID"
    assert any("artifact digest does not match" in error for error in report["errors"])


def test_validator_rejects_raw_request_like_fields_even_before_archival(tmp_path):
    batch = terminal_timeout_batch(tmp_path)
    first_trial = batch.trial_dir(batch.trial_specs[0])
    events_path = first_trial / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
    events[0]["payload"] = "test-only forbidden request field"
    events_path.write_text(
        "\n".join(json.dumps(event, sort_keys=True) for event in events) + "\n",
        encoding="utf-8",
    )

    report = validate_external_batch(batch.batch_dir)

    assert report["validation_status"] == "INVALID"
    assert any("forbidden raw evidence field 'payload'" in error for error in report["errors"])


def test_validator_rejects_forbidden_fields_in_preregistered_batch_metadata(tmp_path):
    batch = make_batch(tmp_path)
    batch_path = batch.batch_dir / "batch.json"
    registration_path = batch.batch_dir / "api-driver-registration.json"
    batch_manifest = json.loads(batch_path.read_text(encoding="utf-8"))
    registration = json.loads(registration_path.read_text(encoding="utf-8"))

    batch_manifest["payload"] = "test-only forbidden batch field"
    batch_without_digest = dict(batch_manifest)
    batch_without_digest.pop("preregistration_digest")
    batch_manifest["preregistration_digest"] = digest(batch_without_digest)
    registration["batch_preregistration_digest"] = batch_manifest["preregistration_digest"]
    registration_without_digest = dict(registration)
    registration_without_digest.pop("registration_digest")
    registration["registration_digest"] = digest(registration_without_digest)
    batch_path.write_text(json.dumps(batch_manifest), encoding="utf-8")
    registration_path.write_text(json.dumps(registration), encoding="utf-8")

    report = validate_external_batch(batch.batch_dir)

    assert report["validation_status"] == "INVALID"
    assert any("batch.json: forbidden raw evidence field 'payload'" in error for error in report["errors"])
