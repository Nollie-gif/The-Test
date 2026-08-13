"""Independent read-back verifier for PRT-001.

It does not trust agent telemetry or a success claim. It reads the persistent
expectation, target receipt, and authoritative state separately, then compares
the final state to the expectation that existed before the commit.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Mapping

from .common import digest, now_iso, payload_digest, state_digest
from .target import TARGET_VERSION, VERIFICATION_SCOPE


class IndependentQuicksaveVerifier:
    """Verify a committed PRT-001 transaction against persistent invariants."""

    version = "prt-001-independent-verifier-0.1"

    def __init__(self, root: Path, *, target_id: str = "prt-001-quicksave-target"):
        self.root = Path(root)
        self.target_id = target_id

    def verify(self, transaction_id: str) -> dict[str, Any]:
        try:
            tx_id = str(uuid.UUID(transaction_id))
        except (ValueError, TypeError, AttributeError):
            return self._invalid_transaction_result(str(transaction_id))
        failures: list[str] = []
        expectation = self._load("expectations", tx_id, failures)
        state = self._load_state(failures)
        receipt = self._load("receipts", tx_id, failures)

        expected_payload_digest: str | None = None
        expected_generation: int | None = None
        expectation_valid = False
        if expectation is not None:
            expectation_valid, expected_payload_digest, expected_generation = self._check_expectation(
                expectation,
                tx_id,
                failures,
            )

        final_state_correct = self._check_final_state(
            state,
            tx_id,
            expectation_valid,
            expected_payload_digest,
            expected_generation,
            failures,
        )
        receipt_complete = self._check_receipt(
            receipt,
            expectation,
            state,
            tx_id,
            failures,
        )
        authoritative_success = final_state_correct and receipt_complete

        return {
            "verification_version": TARGET_VERSION,
            "verification_scope": VERIFICATION_SCOPE,
            "authoritative_for_scope": True,
            "authoritative_success": authoritative_success,
            "final_state_correct": final_state_correct,
            "receipt_complete": receipt_complete,
            "verifier": self.version,
            "verified_at": now_iso(),
            "target_id": self.target_id,
            "transaction_id": tx_id,
            "expected_generation": expected_generation,
            "observed_generation": state.get("generation") if state else None,
            "expected_payload_digest": expected_payload_digest,
            "observed_state_digest": state.get("state_digest") if state else None,
            "failure_reasons": failures,
        }

    def _invalid_transaction_result(self, transaction_id: str) -> dict[str, Any]:
        return {
            "verification_version": TARGET_VERSION,
            "verification_scope": VERIFICATION_SCOPE,
            "authoritative_for_scope": True,
            "authoritative_success": False,
            "final_state_correct": False,
            "receipt_complete": False,
            "verifier": self.version,
            "verified_at": now_iso(),
            "target_id": self.target_id,
            "transaction_id": transaction_id,
            "expected_generation": None,
            "observed_generation": None,
            "expected_payload_digest": None,
            "observed_state_digest": None,
            "failure_reasons": ["transaction_id must be a UUID"],
        }

    def _load(self, directory: str, transaction_id: str, failures: list[str]) -> dict[str, Any] | None:
        path = self.root / directory / f"{transaction_id}.json"
        return self._read_object(path, f"{directory} artifact", failures)

    def _load_state(self, failures: list[str]) -> dict[str, Any] | None:
        return self._read_object(self.root / "authoritative-state.json", "authoritative state", failures)

    @staticmethod
    def _read_object(path: Path, label: str, failures: list[str]) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            failures.append(f"{label} is missing")
            return None
        except json.JSONDecodeError:
            failures.append(f"{label} is invalid JSON")
            return None
        if not isinstance(value, dict):
            failures.append(f"{label} is not an object")
            return None
        return value

    def _check_expectation(
        self,
        expectation: Mapping[str, Any],
        transaction_id: str,
        failures: list[str],
    ) -> tuple[bool, str | None, int | None]:
        required = {
            "expectation_version",
            "verification_scope",
            "target_id",
            "transaction_id",
            "source_generation",
            "source_state_digest",
            "expected_generation",
            "expected_payload",
            "expected_payload_digest",
            "prepared_at",
        }
        if not required <= set(expectation):
            failures.append("expectation is incomplete")
            return False, None, None
        valid = True
        if expectation["expectation_version"] != TARGET_VERSION:
            failures.append("expectation has an unknown version")
            valid = False
        if expectation["verification_scope"] != VERIFICATION_SCOPE:
            failures.append("expectation has the wrong verification scope")
            valid = False
        if expectation["target_id"] != self.target_id:
            failures.append("expectation targets a different target")
            valid = False
        if expectation["transaction_id"] != transaction_id:
            failures.append("expectation transaction_id does not match")
            valid = False
        if not isinstance(expectation["source_generation"], int) or not isinstance(
            expectation["expected_generation"], int
        ):
            failures.append("expectation generations are invalid")
            valid = False
        elif expectation["expected_generation"] != expectation["source_generation"] + 1:
            failures.append("expectation generation transition is invalid")
            valid = False
        if not isinstance(expectation["expected_payload"], dict):
            failures.append("expectation payload is invalid")
            return False, None, None
        expected_payload_digest = payload_digest(expectation["expected_payload"])
        if expectation["expected_payload_digest"] != expected_payload_digest:
            failures.append("expectation payload digest does not match its payload")
            valid = False
        return valid, expected_payload_digest, expectation["expected_generation"]

    def _check_final_state(
        self,
        state: Mapping[str, Any] | None,
        transaction_id: str,
        expectation_valid: bool,
        expected_payload_digest: str | None,
        expected_generation: int | None,
        failures: list[str],
    ) -> bool:
        if (
            not expectation_valid
            or state is None
            or expected_payload_digest is None
            or expected_generation is None
        ):
            return False
        required = {
            "state_version",
            "verification_scope",
            "target_id",
            "generation",
            "payload",
            "payload_digest",
            "state_digest",
            "last_transaction_id",
            "committed_at",
        }
        if not required <= set(state):
            failures.append("authoritative state is incomplete")
            return False
        valid = True
        if state["state_version"] != TARGET_VERSION:
            failures.append("authoritative state has an unknown version")
            valid = False
        if state["verification_scope"] != VERIFICATION_SCOPE:
            failures.append("authoritative state has the wrong verification scope")
            valid = False
        if state["target_id"] != self.target_id:
            failures.append("authoritative state belongs to a different target")
            valid = False
        if state["generation"] != expected_generation:
            failures.append("authoritative state generation does not match expectation")
            valid = False
        if state["last_transaction_id"] != transaction_id:
            failures.append("authoritative state transaction_id does not match expectation")
            valid = False
        if not isinstance(state["payload"], dict):
            failures.append("authoritative state payload is invalid")
            return False
        observed_payload_digest = payload_digest(state["payload"])
        if state["payload_digest"] != observed_payload_digest:
            failures.append("authoritative state payload digest does not match its payload")
            valid = False
        if observed_payload_digest != expected_payload_digest:
            failures.append("authoritative state payload does not match expectation")
            valid = False
        expected_state_digest = state_digest(
            target_id=state["target_id"],
            generation=state["generation"],
            payload=state["payload"],
            last_transaction_id=state["last_transaction_id"],
        )
        if state["state_digest"] != expected_state_digest:
            failures.append("authoritative state digest does not match its contents")
            valid = False
        return valid

    def _check_receipt(
        self,
        receipt: Mapping[str, Any] | None,
        expectation: Mapping[str, Any] | None,
        state: Mapping[str, Any] | None,
        transaction_id: str,
        failures: list[str],
    ) -> bool:
        if receipt is None:
            return False
        required = {
            "receipt_version",
            "verification_scope",
            "target_id",
            "transaction_id",
            "source_generation",
            "source_state_digest",
            "result_generation",
            "payload_digest",
            "state_digest",
            "expectation_digest",
            "status",
            "committed_at",
        }
        if not required <= set(receipt):
            failures.append("target receipt is incomplete")
            return False
        complete = True
        if receipt["receipt_version"] != TARGET_VERSION:
            failures.append("target receipt has an unknown version")
            complete = False
        if receipt["verification_scope"] != VERIFICATION_SCOPE:
            failures.append("target receipt has the wrong verification scope")
            complete = False
        if receipt["target_id"] != self.target_id:
            failures.append("target receipt belongs to a different target")
            complete = False
        if receipt["transaction_id"] != transaction_id:
            failures.append("target receipt transaction_id does not match")
            complete = False
        if receipt["status"] != "committed":
            failures.append("target receipt does not record a committed transaction")
            complete = False
        if expectation is not None:
            if receipt["source_generation"] != expectation.get("source_generation"):
                failures.append("target receipt source generation does not match expectation")
                complete = False
            if receipt["source_state_digest"] != expectation.get("source_state_digest"):
                failures.append("target receipt source state does not match expectation")
                complete = False
            if receipt["result_generation"] != expectation.get("expected_generation"):
                failures.append("target receipt result generation does not match expectation")
                complete = False
            if receipt["payload_digest"] != expectation.get("expected_payload_digest"):
                failures.append("target receipt payload digest does not match expectation")
                complete = False
            if receipt["expectation_digest"] != digest(expectation):
                failures.append("target receipt expectation reference does not match expectation")
                complete = False
        if state is not None and receipt["state_digest"] != state.get("state_digest"):
            failures.append("target receipt state digest does not match authoritative state")
            complete = False
        return complete
