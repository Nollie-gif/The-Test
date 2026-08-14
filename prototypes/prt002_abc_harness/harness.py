"""Non-canonical, pre-registered A/B/C harness for EXP-001.

This module gives each EXP-001 variant a different agent-facing tool surface
over the *same* fresh PRT-001 synthetic target and predeclared final state.
It is deliberately not a model runner and it never writes ``RUN-*`` files.

The harness can create a batch only after recording a model identity, operator,
repeat policy, task, target configuration, variant order, and prompt revision.
Any resulting artifact is a non-canonical synthetic prototype artifact; it is
not experimental evidence until a later, separately approved promotion path
maps it into the canonical RUN contract.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from prototypes.prt001_controlled_quicksave.common import digest, now_iso
from prototypes.prt001_controlled_quicksave.target import (
    ControlledQuicksaveTarget,
    ControlledTargetError,
)
from prototypes.prt001_controlled_quicksave.verifier import IndependentQuicksaveVerifier
from runner.runner import compute_derived_metrics
from runner.telemetry import Telemetry


HARNESS_VERSION = "prt-002-abc-harness-0.1"
EXPERIMENT_ID = "EXP-001"
VERIFICATION_SCOPE = "synthetic-controlled-target"
TASK_REQUEST = "DM note: quicksave"
PROMPT_REVISION = "exp-001-prt-002-v1"
VARIANTS = ("A", "B", "C")
DEFAULT_REPEATS_PER_VARIANT = 3
INITIAL_PAYLOAD = {"published_generation": 0, "checkpoint": "baseline"}
EXPECTED_PAYLOAD = {"published_generation": 1, "checkpoint": "quicksave-complete"}

_LATIN_ORDERS = (
    ("A", "B", "C"),
    ("B", "C", "A"),
    ("C", "A", "B"),
)

_TOOL_CONTRACTS: dict[str, tuple[dict[str, str], ...]] = {
    "A": (
        {"name": "read_persistence_contract", "purpose": "Read the visible low-level save contract."},
        {"name": "read_prepared_transaction", "purpose": "Read the prepared transaction identifier."},
        {"name": "read_authoritative_state", "purpose": "Read the current target state."},
        {"name": "commit_prepared_transaction", "purpose": "Commit one prepared transaction."},
        {"name": "read_target_receipt", "purpose": "Read the target receipt after a commit."},
        {"name": "verify_final_state", "purpose": "Ask for an independent final-state check."},
    ),
    "B": (
        {"name": "read_quicksave_route", "purpose": "Read the compact Quicksave route."},
        {"name": "execute_quicksave_route", "purpose": "Execute the routed Quicksave operation."},
        {"name": "verify_quicksave", "purpose": "Ask for an independent final-state check."},
    ),
    "C": (
        {"name": "quicksave", "purpose": "Execute the deterministic composite Quicksave action."},
    ),
}


class HarnessError(RuntimeError):
    """Raised for invalid PRT-002 planning or interaction operations."""


def _require_nonempty(label: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HarnessError(f"{label} must be recorded before a batch can be created")
    return value.strip()


def _require_variant(variant: str) -> str:
    if variant not in VARIANTS:
        raise HarnessError(f"variant must be one of {', '.join(VARIANTS)}")
    return variant


def _compact_storage_id(artifact_id: str, *, prefix: str) -> str:
    """Derive a short, filesystem-safe alias without weakening the recorded ID."""

    if not artifact_id.startswith(prefix):
        raise HarnessError(f"artifact ID must begin with {prefix!r}")
    try:
        identifier = uuid.UUID(artifact_id[len(prefix) :])
    except (ValueError, TypeError, AttributeError) as exc:
        raise HarnessError("artifact ID must contain a UUID") from exc
    token = urlsafe_b64encode(identifier.bytes).decode("ascii").rstrip("=")
    return f"{prefix}{token}"


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _require_external_output_root(output_root: Path) -> Path:
    """Prevent prototype artifacts from landing in the versioned research repo."""
    resolved = Path(output_root).expanduser().resolve()
    repo_root = _repository_root()
    if resolved == repo_root or repo_root in resolved.parents:
        raise HarnessError(
            "PRT-002 output must live outside the repository; it must never create RUN-like artifacts in source control"
        )
    return resolved


def _write_json_new(path: Path, value: Mapping[str, Any]) -> None:
    """Write one immutable harness artifact without overwriting an existing one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise HarnessError(f"harness artifact already exists: {path.name}")
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        # Keep temporary names short for deeply nested external trial paths on Windows.
        prefix=".tmp.",
        suffix=".tmp",
    ) as temp:
        json.dump(value, temp, ensure_ascii=False, indent=2, sort_keys=True)
        temp.write("\n")
        temp.flush()
        os.fsync(temp.fileno())
        temporary_path = Path(temp.name)
    try:
        if path.exists():
            raise HarnessError(f"harness artifact already exists: {path.name}")
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _balanced_schedule(repeats_per_variant: int) -> list[str]:
    if not isinstance(repeats_per_variant, int) or repeats_per_variant < DEFAULT_REPEATS_PER_VARIANT:
        raise HarnessError(
            f"repeats_per_variant must be an integer of at least {DEFAULT_REPEATS_PER_VARIANT}"
        )
    if repeats_per_variant % len(VARIANTS) != 0:
        raise HarnessError(
            "repeats_per_variant must be a multiple of 3 so every variant occupies every order position equally"
        )
    schedule: list[str] = []
    for cycle in range(repeats_per_variant):
        schedule.extend(_LATIN_ORDERS[cycle % len(_LATIN_ORDERS)])
    return schedule


def agent_instruction(variant: str) -> dict[str, Any]:
    """Return the fixed agent-facing instruction for one pre-registered variant."""
    variant = _require_variant(variant)
    return {
        "prompt_revision": PROMPT_REVISION,
        "task": TASK_REQUEST,
        "scope": "Synthetic PRT-001 target only. Do not claim Mission 10, GitHub, Supabase, or canonical RUN success.",
        "success_boundary": (
            "A textual completion claim is non-authoritative. The independent verifier decides whether the "
            "predeclared final state is correct for this synthetic target."
        ),
        "variant": variant,
        "allowed_tools": [dict(tool) for tool in _TOOL_CONTRACTS[variant]],
    }


@dataclass(frozen=True)
class TrialSpec:
    """One position in an immutable, pre-registered batch schedule."""

    trial_id: str
    storage_id: str
    ordinal: int
    variant: str
    transaction_id: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "storage_id": self.storage_id,
            "ordinal": self.ordinal,
            "variant": self.variant,
            "transaction_id": self.transaction_id,
        }


class PreregisteredBatch:
    """Create a complete EXP-001 synthetic A/B/C batch before any trial opens."""

    def __init__(self, batch_dir: Path, manifest: Mapping[str, Any]):
        self.batch_dir = Path(batch_dir)
        self.manifest = dict(manifest)

    @classmethod
    def create(
        cls,
        output_root: Path,
        *,
        agent_model: str,
        operator: str,
        source_revision: str,
        repeats_per_variant: int = DEFAULT_REPEATS_PER_VARIANT,
    ) -> "PreregisteredBatch":
        """Persist a full balanced-order batch before any agent action can occur."""
        output_root = _require_external_output_root(Path(output_root))
        agent_model = _require_nonempty("agent_model", agent_model)
        operator = _require_nonempty("operator", operator)
        source_revision = _require_nonempty("source_revision", source_revision)
        schedule = _balanced_schedule(repeats_per_variant)

        batch_id = f"BATCH-{uuid.uuid4()}"
        batch_storage_id = _compact_storage_id(batch_id, prefix="BATCH-")
        batch_dir = output_root / batch_storage_id
        try:
            batch_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise HarnessError(f"batch directory already exists: {batch_dir.name}") from exc

        specs: list[TrialSpec] = []
        for ordinal, variant in enumerate(schedule, start=1):
            trial_id = f"TRIAL-{uuid.uuid4()}"
            specs.append(
                TrialSpec(
                    trial_id=trial_id,
                    storage_id=_compact_storage_id(trial_id, prefix="TRIAL-"),
                    ordinal=ordinal,
                    variant=variant,
                    transaction_id=str(uuid.uuid4()),
                )
            )
        instructions = {variant: agent_instruction(variant) for variant in VARIANTS}
        manifest: dict[str, Any] = {
            "artifact_kind": "noncanonical-preregistered-abc-batch",
            "harness_version": HARNESS_VERSION,
            "evidence_status": "synthetic-prototype-only-not-a-RUN",
            "batch_id": batch_id,
            "batch_storage_id": batch_storage_id,
            "created_at": now_iso(),
            "experiment_id": EXPERIMENT_ID,
            "verification_scope": VERIFICATION_SCOPE,
            "task_request": TASK_REQUEST,
            "agent_model": agent_model,
            "operator": operator,
            "source_revision": source_revision,
            "prompt_revision": PROMPT_REVISION,
            "variant_order_policy": "balanced-latin-square",
            "repeats_per_variant": repeats_per_variant,
            "variants": list(VARIANTS),
            "initial_payload": dict(INITIAL_PAYLOAD),
            "expected_payload": dict(EXPECTED_PAYLOAD),
            "agent_instruction_digests": {
                variant: digest(instruction) for variant, instruction in instructions.items()
            },
            "trial_specs": [spec.as_dict() for spec in specs],
        }
        manifest["preregistration_digest"] = digest(manifest)
        _write_json_new(batch_dir / "batch.json", manifest)
        return cls(batch_dir, manifest)

    @property
    def batch_id(self) -> str:
        return str(self.manifest["batch_id"])

    @property
    def batch_storage_id(self) -> str:
        recorded = self.manifest.get("batch_storage_id")
        expected = _compact_storage_id(self.batch_id, prefix="BATCH-")
        if recorded != expected:
            raise HarnessError("batch storage alias does not match the recorded batch ID")
        return expected

    @property
    def preregistration_digest(self) -> str:
        return str(self.manifest["preregistration_digest"])

    @property
    def trial_specs(self) -> tuple[TrialSpec, ...]:
        specs: list[TrialSpec] = []
        for spec in self.manifest["trial_specs"]:
            trial_id = str(spec["trial_id"])
            storage_id = str(spec["storage_id"])
            expected_storage_id = _compact_storage_id(trial_id, prefix="TRIAL-")
            if storage_id != expected_storage_id:
                raise HarnessError("trial storage alias does not match the recorded trial ID")
            specs.append(
                TrialSpec(
                    trial_id=trial_id,
                    storage_id=storage_id,
                    ordinal=int(spec["ordinal"]),
                    variant=str(spec["variant"]),
                    transaction_id=str(spec["transaction_id"]),
                )
            )
        return tuple(specs)

    def trial_dir(self, spec: TrialSpec) -> Path:
        """Return the compact on-disk location for one recorded trial."""

        expected_storage_id = _compact_storage_id(spec.trial_id, prefix="TRIAL-")
        if spec.storage_id != expected_storage_id:
            raise HarnessError("trial storage alias does not match the recorded trial ID")
        return self.batch_dir / "trials" / spec.storage_id

    def open_trial(self, trial_id: str) -> "ControlledTrial":
        """Create one fresh PRT-001 target using only a pre-registered trial spec."""
        spec = next((item for item in self.trial_specs if item.trial_id == trial_id), None)
        if spec is None:
            raise HarnessError("trial_id is not present in this pre-registered batch")

        expected = self._next_schedulable_spec()
        if expected is None:
            raise HarnessError("the prior scheduled trial must be finalized before another trial opens")
        if spec.trial_id != expected.trial_id:
            raise HarnessError("trials must open in the pre-registered schedule order")

        trial_dir = self.trial_dir(spec)
        if trial_dir.exists():
            raise HarnessError("a pre-registered trial may be opened only once")
        trial_dir.mkdir(parents=True)
        target = ControlledQuicksaveTarget(trial_dir / "target")
        target.initialize(INITIAL_PAYLOAD)
        expectation = target.prepare(EXPECTED_PAYLOAD, transaction_id=spec.transaction_id)
        trial_manifest = {
            "artifact_kind": "noncanonical-preregistered-abc-trial",
            "evidence_status": "synthetic-prototype-only-not-a-RUN",
            "batch_id": self.batch_id,
            "batch_preregistration_digest": self.preregistration_digest,
            "trial_spec": spec.as_dict(),
            "trial_spec_digest": digest(spec.as_dict()),
            "experiment_id": EXPERIMENT_ID,
            "verification_scope": VERIFICATION_SCOPE,
            "task_request": TASK_REQUEST,
            "agent_model": self.manifest["agent_model"],
            "operator": self.manifest["operator"],
            "source_revision": self.manifest["source_revision"],
            "prompt_revision": PROMPT_REVISION,
            "agent_instruction_digest": self.manifest["agent_instruction_digests"][spec.variant],
            "opened_at": now_iso(),
            "expected_state_reference": {
                "transaction_id": expectation["transaction_id"],
                "expected_generation": expectation["expected_generation"],
                "expected_payload_digest": expectation["expected_payload_digest"],
            },
        }
        _write_json_new(trial_dir / "trial.json", trial_manifest)
        telemetry = Telemetry(trial_dir / "events.jsonl")
        telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "trial_started",
                "source": "harness",
                "variant": spec.variant,
                "trial_id": spec.trial_id,
            }
        )
        return ControlledTrial(
            batch=self,
            spec=spec,
            trial_dir=trial_dir,
            target=target,
            expectation=expectation,
            telemetry=telemetry,
        )

    def _next_schedulable_spec(self) -> TrialSpec | None:
        """Keep execution order faithful to the immutable pre-registration."""
        specs = self.trial_specs
        for spec in specs:
            trial_dir = self.trial_dir(spec)
            if not trial_dir.exists():
                return spec
            if not (trial_dir / "result.json").is_file():
                return None
        return None


class ControlledTrial:
    """One agent-facing interaction over a fresh, pre-registered PRT-001 target."""

    def __init__(
        self,
        *,
        batch: PreregisteredBatch,
        spec: TrialSpec,
        trial_dir: Path,
        target: ControlledQuicksaveTarget,
        expectation: Mapping[str, Any],
        telemetry: Telemetry,
    ):
        self.batch = batch
        self.spec = spec
        self.trial_dir = Path(trial_dir)
        self.target = target
        self.expectation = dict(expectation)
        self.telemetry = telemetry
        self.verifier = IndependentQuicksaveVerifier(target.root)
        self._started_at_ns = time.monotonic_ns()
        self._finalized = False
        self._error_seen = False
        self._last_error_stage: str | None = None
        self._last_proof: dict[str, Any] | None = None

    @property
    def transaction_id(self) -> str:
        return str(self.expectation["transaction_id"])

    @property
    def route_token(self) -> str:
        """An opaque B-only route token derived from its fixed pre-registration."""
        return f"route:{digest({'batch': self.batch.batch_id, 'trial': self.spec.trial_id})[:24]}"

    @property
    def instruction(self) -> dict[str, Any]:
        return agent_instruction(self.spec.variant)

    def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        """Execute one visible agent tool call and record its classification."""
        if self._finalized:
            raise HarnessError("cannot call a tool after a trial is finalized")
        if not isinstance(tool, str):
            return self._tool_error(
                tool=str(tool),
                operation="unknown",
                stage="agent_interface",
                error_code="wrong_tool",
                classification="wrong_tool",
                message="tool name must be a string",
            )
        handlers = self._handlers()
        handler = handlers.get(tool)
        if handler is None:
            return self._tool_error(
                tool=tool,
                operation="unknown",
                stage="agent_interface",
                error_code="wrong_tool",
                classification="wrong_tool",
                message=f"{tool} is not exposed in variant {self.spec.variant}",
            )
        target_id = arguments.get("target_id")
        if target_id is not None and target_id != self.target.target_id:
            return self._wrong_route(tool, "target_id does not match the controlled target")
        return handler(arguments)

    def declare_success(self, claim: str = "quicksave_complete") -> None:
        """Record a non-authoritative agent completion claim."""
        if self._finalized:
            raise HarnessError("cannot declare success after a trial is finalized")
        self.telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "agent_success_claim",
                "source": "agent",
                "claim": claim,
                "claim_type": "explicit",
            }
        )

    def record_human_intervention(self, reason: str) -> None:
        if self._finalized:
            raise HarnessError("cannot record an intervention after a trial is finalized")
        self.telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "human_intervention",
                "source": "observer",
                "reason": str(reason),
            }
        )

    def record_recovery_action(self, description: str) -> None:
        if self._finalized:
            raise HarnessError("cannot record recovery after a trial is finalized")
        self.telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "recovery_action",
                "source": "agent",
                "description": str(description),
            }
        )

    def record_recovery_complete(self) -> dict[str, Any]:
        """Record recovery only after an independent terminal verifier verdict."""
        if self._finalized:
            raise HarnessError("cannot record recovery after a trial is finalized")
        if not self._error_seen:
            raise HarnessError("recovery_complete requires a recorded error first")
        proof = self._verify()
        self._emit_verifier_verdict(proof)
        if not proof["authoritative_success"]:
            return proof
        self.telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "recovery_complete",
                "source": "harness",
            }
        )
        return proof

    def finalize(self) -> dict[str, Any]:
        """Close telemetry and write a non-canonical result with independent proof."""
        if self._finalized:
            raise HarnessError("a trial may be finalized only once")
        proof = self._verify()
        self._emit_verifier_verdict(proof)
        self.telemetry.close()
        diagnostics = compute_derived_metrics(self.trial_dir / "events.jsonl")
        false_success = bool(diagnostics["agent_success_claims"] and not proof["authoritative_success"])
        completion_time_ms = max(0, round((time.monotonic_ns() - self._started_at_ns) / 1_000_000))
        result = {
            "artifact_kind": "noncanonical-synthetic-abc-trial-result",
            "harness_version": HARNESS_VERSION,
            "evidence_status": "synthetic-prototype-only-not-a-RUN",
            "batch_id": self.batch.batch_id,
            "batch_preregistration_digest": self.batch.preregistration_digest,
            "trial_id": self.spec.trial_id,
            "trial_spec_digest": digest(self.spec.as_dict()),
            "experiment_id": EXPERIMENT_ID,
            "variant": self.spec.variant,
            "agent_model": self.batch.manifest["agent_model"],
            "operator": self.batch.manifest["operator"],
            "source_revision": self.batch.manifest["source_revision"],
            "prompt_revision": PROMPT_REVISION,
            "verification_scope": proof["verification_scope"],
            "completed_at": now_iso(),
            "completion_time_ms": completion_time_ms,
            "agent_success_claimed": bool(diagnostics["agent_success_claims"]),
            "false_success": false_success,
            "failure_stage": None
            if proof["authoritative_success"]
            else (self._last_error_stage or "verification"),
            "diagnostic_metrics": diagnostics,
            "verifier_proof": proof,
        }
        _write_json_new(self.trial_dir / "result.json", result)
        self._finalized = True
        return result

    def _handlers(self) -> dict[str, Any]:
        if self.spec.variant == "A":
            return {
                "read_persistence_contract": self._a_read_contract,
                "read_prepared_transaction": self._a_read_prepared_transaction,
                "read_authoritative_state": self._a_read_state,
                "commit_prepared_transaction": self._a_commit,
                "read_target_receipt": self._a_read_receipt,
                "verify_final_state": self._a_verify,
            }
        if self.spec.variant == "B":
            return {
                "read_quicksave_route": self._b_read_route,
                "execute_quicksave_route": self._b_execute_route,
                "verify_quicksave": self._b_verify,
            }
        return {"quicksave": self._c_quicksave}

    def _a_read_contract(self, _: Mapping[str, Any]) -> dict[str, Any]:
        return self._tool_ok(
            tool="read_persistence_contract",
            operation="read",
            resource_id="prt002:variant-a:persistence-contract",
            data={"required_terminal_proof": "independent verifier verdict"},
        )

    def _a_read_prepared_transaction(self, _: Mapping[str, Any]) -> dict[str, Any]:
        return self._tool_ok(
            tool="read_prepared_transaction",
            operation="read",
            resource_id="prt002:prepared-transaction",
            data={"transaction_id": self.transaction_id},
        )

    def _a_read_state(self, _: Mapping[str, Any]) -> dict[str, Any]:
        return self._tool_ok(
            tool="read_authoritative_state",
            operation="read",
            resource_id="prt002:authoritative-state",
            data={"state": self.target.read_authoritative_state()},
        )

    def _a_commit(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        requested = arguments.get("transaction_id")
        if requested != self.transaction_id:
            return self._wrong_route("commit_prepared_transaction", "transaction_id does not match the pre-registered transaction")
        return self._commit(
            tool="commit_prepared_transaction",
            resource_id="prt002:prepared-transaction",
            transaction_id=self.transaction_id,
        )

    def _a_read_receipt(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        requested = arguments.get("transaction_id", self.transaction_id)
        if requested != self.transaction_id:
            return self._wrong_route("read_target_receipt", "transaction_id does not match the pre-registered transaction")
        try:
            receipt = json.loads(self.target.receipt_path(self.transaction_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._tool_error(
                tool="read_target_receipt",
                operation="read",
                stage="receipt",
                error_code="receipt_missing",
                message="no receipt exists before a successful target commit",
            )
        return self._tool_ok(
            tool="read_target_receipt",
            operation="read",
            resource_id="prt002:target-receipt",
            data={"receipt": receipt},
        )

    def _a_verify(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        requested = arguments.get("transaction_id", self.transaction_id)
        if requested != self.transaction_id:
            return self._wrong_route("verify_final_state", "transaction_id does not match the pre-registered transaction")
        return self._verify_tool("verify_final_state")

    def _b_read_route(self, _: Mapping[str, Any]) -> dict[str, Any]:
        return self._tool_ok(
            tool="read_quicksave_route",
            operation="read",
            resource_id="prt002:compact-quicksave-route",
            data={"route_token": self.route_token},
        )

    def _b_execute_route(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        if arguments.get("route_token") != self.route_token:
            return self._wrong_route("execute_quicksave_route", "route_token does not match the compact route")
        return self._commit(
            tool="execute_quicksave_route",
            resource_id="prt002:compact-quicksave-route",
            transaction_id=self.transaction_id,
        )

    def _b_verify(self, _: Mapping[str, Any]) -> dict[str, Any]:
        return self._verify_tool("verify_quicksave")

    def _c_quicksave(self, _: Mapping[str, Any]) -> dict[str, Any]:
        commit = self._commit(
            tool="quicksave",
            resource_id="prt002:deterministic-composite-quicksave",
            transaction_id=self.transaction_id,
        )
        if not commit["ok"]:
            return commit
        proof = self._verify()
        if not proof["authoritative_success"]:
            return self._tool_error(
                tool="quicksave",
                operation="write",
                stage="verification",
                error_code="verification_failed",
                message="composite quicksave did not produce an authoritative synthetic proof",
                data={"proof": proof},
            )
        return commit | {"data": {"receipt": commit["data"]["receipt"], "proof": proof}}

    def _commit(self, *, tool: str, resource_id: str, transaction_id: str) -> dict[str, Any]:
        try:
            receipt = self.target.commit_prepared(transaction_id)
        except ControlledTargetError as exc:
            return self._tool_error(
                tool=tool,
                operation="write",
                stage="target_commit",
                error_code="target_rejected",
                message=str(exc),
            )
        return self._tool_ok(
            tool=tool,
            operation="write",
            resource_id=resource_id,
            data={"receipt": receipt},
        )

    def _verify_tool(self, tool: str) -> dict[str, Any]:
        proof = self._verify()
        if not proof["authoritative_success"]:
            return self._tool_error(
                tool=tool,
                operation="verify",
                stage="verification",
                error_code="verification_failed",
                message="independent verifier rejected the final state",
                data={"proof": proof},
            )
        return self._tool_ok(
            tool=tool,
            operation="verify",
            resource_id="prt002:independent-verifier",
            data={"proof": proof},
        )

    def _verify(self) -> dict[str, Any]:
        proof = self.verifier.verify(self.transaction_id)
        self._last_proof = proof
        return proof

    def _emit_verifier_verdict(self, proof: Mapping[str, Any]) -> None:
        self.telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "verifier_verdict",
                "source": "independent_verifier",
                "authoritative_success": bool(proof["authoritative_success"]),
                "final_state_correct": bool(proof["final_state_correct"]),
                "receipt_complete": bool(proof["receipt_complete"]),
            }
        )

    def _tool_ok(
        self,
        *,
        tool: str,
        operation: str,
        resource_id: str,
        data: Mapping[str, Any],
    ) -> dict[str, Any]:
        self.telemetry.emit(
            {
                "timestamp": now_iso(),
                "event_type": "tool_call",
                "source": "agent",
                "tool": tool,
                "operation": operation,
                "resource_id": resource_id,
                "result": "ok",
            }
        )
        return {"ok": True, "tool": tool, "data": dict(data)}

    def _wrong_route(self, tool: str, message: str) -> dict[str, Any]:
        return self._tool_error(
            tool=tool,
            operation="route",
            stage="agent_interface",
            error_code="wrong_route_target",
            classification="wrong_route_target",
            message=message,
        )

    def _tool_error(
        self,
        *,
        tool: str,
        operation: str,
        stage: str,
        error_code: str,
        message: str,
        classification: str | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "timestamp": now_iso(),
            "event_type": "tool_call",
            "source": "agent",
            "tool": tool,
            "operation": operation,
            "result": "error",
            "error_code": error_code,
            "stage": stage,
            "message": message,
        }
        if classification is not None:
            event["classification"] = classification
        self.telemetry.emit(event)
        self._error_seen = True
        self._last_error_stage = stage
        result: dict[str, Any] = {"ok": False, "tool": tool, "error_code": error_code, "message": message}
        if data is not None:
            result["data"] = dict(data)
        return result
