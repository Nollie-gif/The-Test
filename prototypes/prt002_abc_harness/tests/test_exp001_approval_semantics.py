from prototypes.prt002_abc_harness.api_driver import create_api_batch
from prototypes.prt002_abc_harness.evidence import (
    create_pilot_approval_proof,
    validate_external_batch,
)
from prototypes.prt002_abc_harness.exp001_api_driver import create_exp001_api_batch


def test_exp001_approval_scope_is_research_cycle_not_disposable_pilot(tmp_path):
    batch = create_exp001_api_batch(
        tmp_path / "exp001-output",
        operator="pytest",
        source_revision="exp001-test-revision",
        driver_source_revision="exp001-driver-test-revision",
    )

    proof = create_pilot_approval_proof(
        batch.batch_dir,
        approval_reference="EXP001-DECISION-001",
    )

    assert proof["pilot_scope"]["scope_kind"] == "pre-registered-exp-001-research-cycle"
    assert proof["pilot_scope"]["request_limits"]["max_api_trials"] == 30
    assert proof["pilot_scope"]["prohibitions"]["canonical_run_authorized"] is False
    assert proof["approval_status"] == "SCOPE_FROZEN_NOT_A_LIVE_AUTHORIZATION"

    report = validate_external_batch(batch.batch_dir)
    assert report["validation_status"] == "ACTIVE_NOT_ARCHIVABLE"
    assert report["pilot_approval_proof_status"] == "VALID"


def test_legacy_disposable_pilot_scope_label_is_preserved(tmp_path):
    batch = create_api_batch(
        tmp_path / "legacy-output",
        operator="pytest",
        source_revision="legacy-test-revision",
        driver_source_revision="legacy-driver-test-revision",
    )

    proof = create_pilot_approval_proof(
        batch.batch_dir,
        approval_reference="LEGACY-DECISION-001",
    )

    assert proof["pilot_scope"]["scope_kind"] == "pre-registered-disposable-synthetic-pilot"
