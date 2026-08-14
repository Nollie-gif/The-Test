"""A small stateful target used to rehearse a real Quicksave proof boundary.

This is authoritative only for its own synthetic target. It is intentionally
not a Mission 10, GitHub, or Supabase integration.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Mapping

from .common import digest, now_iso, payload_digest, state_digest


TARGET_VERSION = "PRT-001"
VERIFICATION_SCOPE = "synthetic-controlled-target"


class ControlledTargetError(RuntimeError):
    """Base error for a controlled target operation."""


class StaleExpectationError(ControlledTargetError):
    """Raised when a prepared transaction no longer matches target state."""


class MissingExpectationError(ControlledTargetError):
    """Raised when a commit is attempted without a prepared expectation."""


class TargetBusyError(ControlledTargetError):
    """Raised when another commit already owns this controlled target."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlledTargetError(f"missing controlled-target artifact: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ControlledTargetError(f"invalid controlled-target JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise ControlledTargetError(f"controlled-target artifact must be an object: {path.name}")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, Any], *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not overwrite and path.exists():
        raise ControlledTargetError(f"controlled-target artifact already exists: {path.name}")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        # Keep temporary names short for deeply nested UUID-based trial paths on Windows.
        prefix=".tmp.",
        suffix=".tmp",
    ) as tmp:
        json.dump(value, tmp, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    try:
        if not overwrite and path.exists():
            raise ControlledTargetError(f"controlled-target artifact already exists: {path.name}")
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


class ControlledQuicksaveTarget:
    """Synthetic state store with an explicit prepare -> commit transaction.

    The test controller creates the expectation before an agent-facing action.
    The target will only commit that prepared expectation from the exact source
    generation/state it names.
    """

    def __init__(self, root: Path, *, target_id: str = "prt-001-quicksave-target"):
        self.root = Path(root)
        self.target_id = target_id

    @property
    def state_path(self) -> Path:
        return self.root / "authoritative-state.json"

    @property
    def expectations_dir(self) -> Path:
        return self.root / "expectations"

    @property
    def receipts_dir(self) -> Path:
        return self.root / "receipts"

    @property
    def lock_path(self) -> Path:
        return self.root / ".commit.lock"

    def expectation_path(self, transaction_id: str) -> Path:
        return self.expectations_dir / f"{self._validated_transaction_id(transaction_id)}.json"

    def receipt_path(self, transaction_id: str) -> Path:
        return self.receipts_dir / f"{self._validated_transaction_id(transaction_id)}.json"

    def initialize(self, initial_payload: Mapping[str, Any]) -> dict[str, Any]:
        """Create generation 0 once; callers cannot overwrite existing truth."""
        payload = dict(initial_payload)
        state = self._build_state(
            generation=0,
            payload=payload,
            last_transaction_id=None,
        )
        _write_json_atomic(self.state_path, state, overwrite=False)
        return state

    def read_authoritative_state(self) -> dict[str, Any]:
        return _read_json(self.state_path)

    def prepare(self, expected_payload: Mapping[str, Any], *, transaction_id: str | None = None) -> dict[str, Any]:
        """Persist a predeclared expected final state before any commit happens."""
        state = self.read_authoritative_state()
        self._require_valid_state(state)
        tx_id = self._validated_transaction_id(transaction_id or str(uuid.uuid4()))
        expectation = {
            "expectation_version": TARGET_VERSION,
            "verification_scope": VERIFICATION_SCOPE,
            "target_id": self.target_id,
            "transaction_id": tx_id,
            "source_generation": state["generation"],
            "source_state_digest": state["state_digest"],
            "expected_generation": state["generation"] + 1,
            "expected_payload": dict(expected_payload),
            "expected_payload_digest": payload_digest(expected_payload),
            "prepared_at": now_iso(),
        }
        _write_json_atomic(self.expectation_path(tx_id), expectation, overwrite=False)
        return expectation

    def commit_prepared(self, transaction_id: str) -> dict[str, Any]:
        """Atomically apply one prepared expectation if the source is still exact."""
        tx_id = self._validated_transaction_id(transaction_id)
        with self._exclusive_commit_lock():
            expectation_path = self.expectation_path(tx_id)
            if not expectation_path.is_file():
                raise MissingExpectationError(f"no prepared expectation for transaction {tx_id}")
            expectation = _read_json(expectation_path)
            self._require_valid_expectation(expectation, tx_id)

            state = self.read_authoritative_state()
            self._require_valid_state(state)
            if (
                state["generation"] != expectation["source_generation"]
                or state["state_digest"] != expectation["source_state_digest"]
            ):
                raise StaleExpectationError(
                    "prepared expectation does not match the current authoritative state"
                )

            new_state = self._build_state(
                generation=expectation["expected_generation"],
                payload=expectation["expected_payload"],
                last_transaction_id=tx_id,
            )
            _write_json_atomic(self.state_path, new_state, overwrite=True)

            receipt = {
                "receipt_version": TARGET_VERSION,
                "verification_scope": VERIFICATION_SCOPE,
                "target_id": self.target_id,
                "transaction_id": tx_id,
                "source_generation": expectation["source_generation"],
                "source_state_digest": expectation["source_state_digest"],
                "result_generation": new_state["generation"],
                "payload_digest": new_state["payload_digest"],
                "state_digest": new_state["state_digest"],
                "expectation_digest": digest(expectation),
                "status": "committed",
                "committed_at": new_state["committed_at"],
            }
            _write_json_atomic(self.receipt_path(tx_id), receipt, overwrite=False)
            return receipt

    def _build_state(
        self,
        *,
        generation: int,
        payload: Mapping[str, Any],
        last_transaction_id: str | None,
    ) -> dict[str, Any]:
        payload_copy = dict(payload)
        return {
            "state_version": TARGET_VERSION,
            "verification_scope": VERIFICATION_SCOPE,
            "target_id": self.target_id,
            "generation": generation,
            "payload": payload_copy,
            "payload_digest": payload_digest(payload_copy),
            "state_digest": state_digest(
                target_id=self.target_id,
                generation=generation,
                payload=payload_copy,
                last_transaction_id=last_transaction_id,
            ),
            "last_transaction_id": last_transaction_id,
            "committed_at": now_iso(),
        }

    def _require_valid_state(self, state: Mapping[str, Any]) -> None:
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
            raise ControlledTargetError("authoritative state is missing required fields")
        if state["target_id"] != self.target_id or state["verification_scope"] != VERIFICATION_SCOPE:
            raise ControlledTargetError("authoritative state belongs to a different target")
        if not isinstance(state["generation"], int) or state["generation"] < 0:
            raise ControlledTargetError("authoritative state has an invalid generation")
        if not isinstance(state["payload"], dict):
            raise ControlledTargetError("authoritative state has an invalid payload")
        if state["payload_digest"] != payload_digest(state["payload"]):
            raise ControlledTargetError("authoritative state payload digest does not match")
        expected_state_digest = state_digest(
            target_id=self.target_id,
            generation=state["generation"],
            payload=state["payload"],
            last_transaction_id=state["last_transaction_id"],
        )
        if state["state_digest"] != expected_state_digest:
            raise ControlledTargetError("authoritative state digest does not match")

    def _require_valid_expectation(self, expectation: Mapping[str, Any], transaction_id: str) -> None:
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
            raise ControlledTargetError("prepared expectation is missing required fields")
        if expectation["target_id"] != self.target_id or expectation["transaction_id"] != transaction_id:
            raise ControlledTargetError("prepared expectation belongs to a different transaction")
        if expectation["verification_scope"] != VERIFICATION_SCOPE:
            raise ControlledTargetError("prepared expectation has the wrong verification scope")
        if (
            not isinstance(expectation["source_generation"], int)
            or expectation["source_generation"] < 0
            or not isinstance(expectation["expected_generation"], int)
        ):
            raise ControlledTargetError("prepared expectation has invalid generations")
        if expectation["expected_generation"] != expectation["source_generation"] + 1:
            raise ControlledTargetError("prepared expectation has an invalid generation transition")
        if not isinstance(expectation["expected_payload"], dict):
            raise ControlledTargetError("prepared expectation has an invalid payload")
        if expectation["expected_payload_digest"] != payload_digest(expectation["expected_payload"]):
            raise ControlledTargetError("prepared expectation payload digest does not match")

    @staticmethod
    def _validated_transaction_id(transaction_id: str) -> str:
        try:
            return str(uuid.UUID(transaction_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ControlledTargetError("transaction_id must be a UUID") from exc

    @contextmanager
    def _exclusive_commit_lock(self):
        """Serialize commits and fail closed rather than permitting a lost update."""
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise TargetBusyError("controlled target is busy; retry only after the owner finishes") from exc
        try:
            os.write(lock_fd, str(os.getpid()).encode("ascii"))
            yield
        finally:
            try:
                os.close(lock_fd)
            finally:
                self.lock_path.unlink(missing_ok=True)
