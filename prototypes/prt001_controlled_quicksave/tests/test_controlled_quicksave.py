import json

import pytest

from prototypes.prt001_controlled_quicksave import (
    ControlledQuicksaveTarget,
    IndependentQuicksaveVerifier,
    StaleExpectationError,
    TargetBusyError,
)


def make_target(tmp_path):
    target = ControlledQuicksaveTarget(tmp_path / "target")
    target.initialize({"published_generation": 0, "checkpoint": "baseline"})
    return target


def test_independent_verifier_proves_predeclared_final_state(tmp_path):
    target = make_target(tmp_path)
    expectation = target.prepare(
        {"published_generation": 1, "checkpoint": "expected-save"},
        transaction_id="00000000-0000-4000-8000-000000000001",
    )
    target.commit_prepared(expectation["transaction_id"])

    proof = IndependentQuicksaveVerifier(target.root).verify(expectation["transaction_id"])

    assert proof["verification_scope"] == "synthetic-controlled-target"
    assert proof["authoritative_for_scope"] is True
    assert proof["authoritative_success"] is True
    assert proof["final_state_correct"] is True
    assert proof["receipt_complete"] is True
    assert proof["failure_reasons"] == []


def test_success_claim_without_committed_state_is_not_authoritative_success(tmp_path):
    target = make_target(tmp_path)
    expectation = target.prepare(
        {"published_generation": 1, "checkpoint": "expected-save"},
        transaction_id="00000000-0000-4000-8000-000000000002",
    )
    # This represents an agent saying “done”; no target commit has happened.
    (target.root / "agent-success-claim.json").write_text(
        json.dumps({"claim": "quicksave_complete"}), encoding="utf-8"
    )

    proof = IndependentQuicksaveVerifier(target.root).verify(expectation["transaction_id"])

    assert proof["authoritative_success"] is False
    assert proof["final_state_correct"] is False
    assert "receipts artifact is missing" in proof["failure_reasons"]


def test_verifier_rejects_tampered_state_even_when_receipt_claims_commit(tmp_path):
    target = make_target(tmp_path)
    expectation = target.prepare(
        {"published_generation": 1, "checkpoint": "expected-save"},
        transaction_id="00000000-0000-4000-8000-000000000003",
    )
    target.commit_prepared(expectation["transaction_id"])

    state = target.read_authoritative_state()
    state["payload"] = {"published_generation": 999, "checkpoint": "tampered"}
    target.state_path.write_text(json.dumps(state), encoding="utf-8")

    proof = IndependentQuicksaveVerifier(target.root).verify(expectation["transaction_id"])

    assert proof["authoritative_success"] is False
    assert proof["final_state_correct"] is False
    assert "authoritative state payload does not match expectation" in proof["failure_reasons"]
    assert "authoritative state digest does not match its contents" in proof["failure_reasons"]


def test_target_rejects_a_stale_prepared_transaction(tmp_path):
    target = make_target(tmp_path)
    first = target.prepare(
        {"published_generation": 1, "checkpoint": "first"},
        transaction_id="00000000-0000-4000-8000-000000000004",
    )
    stale = target.prepare(
        {"published_generation": 1, "checkpoint": "stale"},
        transaction_id="00000000-0000-4000-8000-000000000005",
    )

    target.commit_prepared(first["transaction_id"])
    with pytest.raises(StaleExpectationError):
        target.commit_prepared(stale["transaction_id"])

    state = target.read_authoritative_state()
    assert state["generation"] == 1
    assert state["payload"]["checkpoint"] == "first"


def test_verifier_marks_an_incomplete_receipt_as_not_authoritative_success(tmp_path):
    target = make_target(tmp_path)
    expectation = target.prepare(
        {"published_generation": 1, "checkpoint": "expected-save"},
        transaction_id="00000000-0000-4000-8000-000000000006",
    )
    target.commit_prepared(expectation["transaction_id"])

    receipt_path = target.receipt_path(expectation["transaction_id"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    del receipt["state_digest"]
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    proof = IndependentQuicksaveVerifier(target.root).verify(expectation["transaction_id"])

    assert proof["final_state_correct"] is True
    assert proof["receipt_complete"] is False
    assert proof["authoritative_success"] is False
    assert "target receipt is incomplete" in proof["failure_reasons"]


def test_verifier_rejects_an_invalid_transaction_id_without_reading_paths(tmp_path):
    target = make_target(tmp_path)

    proof = IndependentQuicksaveVerifier(target.root).verify("../../not-a-transaction")

    assert proof["authoritative_success"] is False
    assert proof["failure_reasons"] == ["transaction_id must be a UUID"]


def test_target_fails_closed_when_another_commit_owns_the_target(tmp_path):
    target = make_target(tmp_path)
    expectation = target.prepare(
        {"published_generation": 1, "checkpoint": "expected-save"},
        transaction_id="00000000-0000-4000-8000-000000000008",
    )
    target.lock_path.write_text("another-writer", encoding="ascii")

    with pytest.raises(TargetBusyError):
        target.commit_prepared(expectation["transaction_id"])

    assert target.read_authoritative_state()["generation"] == 0
