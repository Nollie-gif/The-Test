"""Explicitly gated OpenAI API driver for PRT-002.

This module drives the existing synthetic PRT-001 target through the
pre-registered PRT-002 A/B/C tool surfaces. It is deliberately separate from
the harness itself: it writes external, non-canonical BATCH/TRIAL artifacts
only, never creates RUN-* files, and requires a double explicit live-run
opt-in before it can make an API request.

The fixed initial pilot is gpt-5.6-terra at medium reasoning effort. The model,
settings, prompt protocol, and request limits are registered beside the batch
before a trial can open.
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from prototypes.prt001_controlled_quicksave.common import digest, now_iso

from .harness import ControlledTrial, HarnessError, PreregisteredBatch, agent_instruction


DRIVER_VERSION = "prt-003-terra-api-driver-0.1"
DRIVER_REGISTRATION_FILENAME = "api-driver-registration.json"
DRIVER_OUTCOME_FILENAME = "api-driver-outcome.json"
DRIVER_RECEIPT_FILENAME = "api-driver-receipt.json"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
SUCCESS_CLAIM = "CLAIM: quicksave_complete"
UNABLE_CLAIM = "CLAIM: unable"


class ApiDriverError(RuntimeError):
    """Raised for a driver safety, transport, or protocol violation."""


@dataclass(frozen=True)
class DriverConfig:
    """The complete fixed model configuration for one pre-registered batch."""

    model: str = "gpt-5.6-terra"
    reasoning_effort: str = "medium"
    max_model_turns: int = 8
    max_output_tokens_per_turn: int = 512

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_DRIVER_CONFIG = DriverConfig()


class ResponsesTransport(Protocol):
    """Minimal transport boundary, allowing tests to run with no API key or network."""

    def create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Submit one Responses API request and return its JSON object."""


class HttpResponsesTransport:
    """Stdlib-only Responses API transport, used only after explicit CLI opt-in."""

    def __init__(self, *, api_key_env: str = "OPENAI_API_KEY") -> None:
        self.api_key_env = api_key_env

    def create(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise ApiDriverError(
                f"{self.api_key_env} is required only for an explicitly live PRT-003 trial"
            )

        request = urllib.request.Request(
            OPENAI_RESPONSES_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Avoid echoing arbitrary response bodies into durable trial artifacts.
            raise ApiDriverError(f"Responses API rejected the request (HTTP {exc.code})") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ApiDriverError(
                "Responses API request ended before a response could be confirmed"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ApiDriverError("Responses API returned invalid JSON") from exc

        if not isinstance(decoded, Mapping):
            raise ApiDriverError("Responses API returned a non-object response")
        return decoded


@dataclass(frozen=True)
class DriverOutcome:
    """Non-canonical driver summary written beside an immutable PRT-002 trial."""

    result: Mapping[str, Any]
    model_response_ids: tuple[str, ...]
    model_turns: int
    usage: Mapping[str, int]
    terminal_error: str | None
    trial_status: str
    request_attempts: int
    unknown_request_attempts: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": "noncanonical-api-driver-outcome",
            "evidence_status": "synthetic-prototype-only-not-a-RUN",
            "driver_version": DRIVER_VERSION,
            "completed_at": now_iso(),
            "model_response_ids": list(self.model_response_ids),
            "model_turns": self.model_turns,
            "usage": dict(self.usage),
            "terminal_error": self.terminal_error,
            "trial_status": self.trial_status,
            "request_attempts": self.request_attempts,
            "unknown_request_attempts": self.unknown_request_attempts,
            "result_path": "result.json",
        }


_NO_ARGUMENTS_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

_TOOL_PARAMETERS: dict[str, dict[str, Any]] = {
    "read_persistence_contract": _NO_ARGUMENTS_SCHEMA,
    "read_prepared_transaction": _NO_ARGUMENTS_SCHEMA,
    "read_authoritative_state": _NO_ARGUMENTS_SCHEMA,
    "commit_prepared_transaction": {
        "type": "object",
        "properties": {"transaction_id": {"type": "string"}},
        "required": ["transaction_id"],
        "additionalProperties": False,
    },
    "read_target_receipt": _NO_ARGUMENTS_SCHEMA,
    "verify_final_state": _NO_ARGUMENTS_SCHEMA,
    "read_quicksave_route": _NO_ARGUMENTS_SCHEMA,
    "execute_quicksave_route": {
        "type": "object",
        "properties": {"route_token": {"type": "string"}},
        "required": ["route_token"],
        "additionalProperties": False,
    },
    "verify_quicksave": _NO_ARGUMENTS_SCHEMA,
    "quicksave": _NO_ARGUMENTS_SCHEMA,
}


def _require_nonempty(label: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApiDriverError(f"{label} must be a non-empty string")
    return value.strip()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _require_external_batch_dir(batch_dir: Path) -> Path:
    resolved = Path(batch_dir).expanduser().resolve()
    repo_root = _repository_root()
    if resolved == repo_root or repo_root in resolved.parents:
        raise ApiDriverError(
            "PRT-003 batch artifacts must stay outside the repository and can never become RUN artifacts"
        )
    return resolved


def _write_json_new(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically create an immutable external artifact without overwrite."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ApiDriverError(f"refusing to overwrite immutable artifact: {path.name}")

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
        # Keep temporary names short for deeply nested external trial paths on Windows.
        prefix=".tmp.",
        suffix=".tmp",
    ) as temporary:
        json.dump(value, temporary, ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write("\n")
        temporary.flush()
        os.fsync(temporary.fileno())
        temporary_path = Path(temporary.name)

    try:
        if path.exists():
            raise ApiDriverError(f"refusing to overwrite immutable artifact: {path.name}")
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def _verify_self_digest(payload: Mapping[str, Any], field: str, label: str) -> None:
    recorded = payload.get(field)
    candidate = dict(payload)
    candidate.pop(field, None)
    if not isinstance(recorded, str) or recorded != digest(candidate):
        raise ApiDriverError(f"{label} digest does not match its immutable contents")


def _next_spec(batch: PreregisteredBatch):
    for spec in batch.trial_specs:
        trial_dir = batch.trial_dir(spec)
        if not trial_dir.exists():
            return spec
        if not (trial_dir / "result.json").is_file():
            raise ApiDriverError(
                "an unfinalized PRT-003 trial blocks this batch; inspect it with "
                "inspect-interrupted and do not retry or resume it"
            )
    raise ApiDriverError("this pre-registered batch has no remaining trials")


def _event_journal_summary(events_path: Path) -> dict[str, Any]:
    """Read only the safe event counts needed to stop an interrupted trial."""

    counts = {
        "api_request_started_count": 0,
        "api_response_observed_count": 0,
        "api_request_incomplete_count": 0,
    }
    if not events_path.is_file():
        return {
            "event_journal_status": "MISSING",
            **counts,
            "unresolved_request_starts": None,
        }

    try:
        with events_path.open(encoding="utf-8") as journal:
            for line in journal:
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, Mapping):
                    raise ValueError("event must be an object")
                event_type = event.get("event_type")
                if event_type == "api_request_started":
                    counts["api_request_started_count"] += 1
                elif event_type == "api_response_observed":
                    counts["api_response_observed_count"] += 1
                elif event_type == "api_request_incomplete":
                    counts["api_request_incomplete_count"] += 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return {
            "event_journal_status": "UNREADABLE",
            **counts,
            "unresolved_request_starts": None,
        }

    return {
        "event_journal_status": "READABLE",
        **counts,
        "unresolved_request_starts": max(
            0,
            counts["api_request_started_count"]
            - counts["api_response_observed_count"]
            - counts["api_request_incomplete_count"],
        ),
    }


def _interruption_request_outcome(summary: Mapping[str, Any]) -> str:
    """Classify an unfinalized trial without claiming a hidden API outcome."""

    if summary["event_journal_status"] == "MISSING":
        return "UNDETERMINED_JOURNAL_MISSING"
    if summary["event_journal_status"] != "READABLE":
        return "UNDETERMINED_JOURNAL_UNREADABLE"
    if summary["unresolved_request_starts"]:
        return "UNKNOWN"
    if summary["api_request_started_count"]:
        return "REQUESTS_JOURNALED_BUT_TRIAL_UNFINALIZED"
    return "NO_DURABLE_API_REQUEST_STARTED"


def inspect_interrupted_trials(
    batch: PreregisteredBatch,
    *,
    config: DriverConfig = DEFAULT_DRIVER_CONFIG,
) -> dict[str, Any]:
    """Read-only recovery stop report; it never retries, resumes, or opens a trial."""

    _validated_registration(batch, config)
    interrupted_trials: list[dict[str, Any]] = []
    for spec in batch.trial_specs:
        trial_dir = batch.trial_dir(spec)
        if not trial_dir.exists() or (trial_dir / "result.json").is_file():
            continue
        journal = _event_journal_summary(trial_dir / "events.jsonl")
        interrupted_trials.append(
            {
                "trial_id": spec.trial_id,
                "trial_storage_id": spec.storage_id,
                "variant": spec.variant,
                "trial_status": "INCOMPLETE",
                "acceptance_status": "NOT_ACCEPTED",
                "recovery_status": "STOP_REQUIRED",
                "request_outcome": _interruption_request_outcome(journal),
                "result_present": False,
                "request_journal_path": "events.jsonl",
                "retry_permitted": False,
                "resume_permitted": False,
                **journal,
            }
        )

    return {
        "artifact_kind": "noncanonical-api-driver-interruption-inspection",
        "evidence_status": "synthetic-prototype-only-not-a-RUN",
        "batch_id": batch.batch_id,
        "inspection_status": (
            "RECOVERY_STOP_REQUIRED" if interrupted_trials else "NO_UNFINALIZED_TRIAL"
        ),
        "network_performed": False,
        "mutation_performed": False,
        "interrupted_trials": interrupted_trials,
        "next_safe_action": (
            "DO_NOT_RETRY_OR_RESUME" if interrupted_trials else "NO_INTERRUPTED_TRIAL_FOUND"
        ),
    }


def _driver_registration(
    batch: PreregisteredBatch,
    *,
    driver_source_revision: str,
    config: DriverConfig,
) -> dict[str, Any]:
    registration: dict[str, Any] = {
        "artifact_kind": "noncanonical-api-driver-registration",
        "evidence_status": "synthetic-prototype-only-not-a-RUN",
        "driver_version": DRIVER_VERSION,
        "created_at": now_iso(),
        "batch_id": batch.batch_id,
        "batch_preregistration_digest": batch.preregistration_digest,
        "driver_source_revision": _require_nonempty(
            "driver_source_revision", driver_source_revision
        ),
        "model_config": config.as_dict(),
        "completion_claim_protocol": {
            "success": SUCCESS_CLAIM,
            "unable": UNABLE_CLAIM,
            "rule": (
                "Only an exact final model response equal to the success string is recorded "
                "as an explicit agent success claim. The independent synthetic verifier "
                "remains the authority for final-state correctness."
            ),
        },
        "live_run_guard": {
            "required_flags": ["--live", "--confirm-live-run"],
            "max_model_turns": config.max_model_turns,
            "max_output_tokens_per_turn": config.max_output_tokens_per_turn,
        },
        "scope": (
            "Synthetic PRT-001 target only. No Mission 10, GitHub, Supabase, production, "
            "or canonical RUN authority."
        ),
    }
    registration["registration_digest"] = digest(registration)
    return registration


def create_api_batch(
    output_root: Path,
    *,
    operator: str,
    source_revision: str,
    driver_source_revision: str,
    repeats_per_variant: int = 3,
    config: DriverConfig = DEFAULT_DRIVER_CONFIG,
) -> PreregisteredBatch:
    """Create a non-live batch and register its immutable fixed pilot configuration."""

    _require_external_batch_dir(Path(output_root))
    batch = PreregisteredBatch.create(
        Path(output_root),
        agent_model=config.model,
        operator=_require_nonempty("operator", operator),
        source_revision=_require_nonempty("source_revision", source_revision),
        repeats_per_variant=repeats_per_variant,
    )
    registration = _driver_registration(
        batch,
        driver_source_revision=driver_source_revision,
        config=config,
    )
    _write_json_new(batch.batch_dir / DRIVER_REGISTRATION_FILENAME, registration)
    return batch


def load_api_batch(batch_dir: Path) -> PreregisteredBatch:
    """Load and verify an existing external batch and its PRT-003 registration."""

    batch_dir = _require_external_batch_dir(Path(batch_dir))
    batch_path = batch_dir / "batch.json"
    registration_path = batch_dir / DRIVER_REGISTRATION_FILENAME
    try:
        manifest = json.loads(batch_path.read_text(encoding="utf-8"))
        registration = json.loads(registration_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ApiDriverError("batch.json and api-driver-registration.json are both required") from exc
    except json.JSONDecodeError as exc:
        raise ApiDriverError("batch registration contains invalid JSON") from exc

    if not isinstance(manifest, Mapping) or not isinstance(registration, Mapping):
        raise ApiDriverError("batch registration must contain JSON objects")
    _verify_self_digest(manifest, "preregistration_digest", "batch preregistration")
    _verify_self_digest(registration, "registration_digest", "driver registration")
    if registration.get("batch_id") != manifest.get("batch_id"):
        raise ApiDriverError("driver registration belongs to a different batch")
    if registration.get("batch_preregistration_digest") != manifest.get("preregistration_digest"):
        raise ApiDriverError("driver registration does not match the batch preregistration")
    return PreregisteredBatch(batch_dir, manifest)


def _validated_registration(batch: PreregisteredBatch, config: DriverConfig) -> Mapping[str, Any]:
    path = batch.batch_dir / DRIVER_REGISTRATION_FILENAME
    try:
        registration = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise ApiDriverError("verified PRT-003 driver registration is required before a trial") from exc
    if not isinstance(registration, Mapping):
        raise ApiDriverError("driver registration must be an object")
    _verify_self_digest(registration, "registration_digest", "driver registration")
    if registration.get("batch_id") != batch.batch_id:
        raise ApiDriverError("driver registration belongs to a different batch")
    if registration.get("batch_preregistration_digest") != batch.preregistration_digest:
        raise ApiDriverError("driver registration does not match the loaded batch")
    if registration.get("model_config") != config.as_dict():
        raise ApiDriverError("driver configuration differs from the pre-registered fixed pilot")
    if batch.manifest.get("agent_model") != config.model:
        raise ApiDriverError("batch model identity differs from the fixed pilot")
    return registration


def _tool_definitions(instruction: Mapping[str, Any]) -> list[dict[str, Any]]:
    allowed_tools = instruction.get("allowed_tools")
    if not isinstance(allowed_tools, list):
        raise ApiDriverError("PRT-002 instruction has no allowed tool contract")

    definitions: list[dict[str, Any]] = []
    for allowed in allowed_tools:
        if not isinstance(allowed, Mapping):
            raise ApiDriverError("PRT-002 tool contract entry is invalid")
        name = allowed.get("name")
        purpose = allowed.get("purpose")
        if not isinstance(name, str) or not isinstance(purpose, str):
            raise ApiDriverError("PRT-002 tool contract must give every tool a name and purpose")
        parameters = _TOOL_PARAMETERS.get(name)
        if parameters is None:
            raise ApiDriverError(f"PRT-003 does not recognize exposed tool {name!r}")
        definitions.append(
            {
                "type": "function",
                "name": name,
                "description": purpose,
                "parameters": json.loads(json.dumps(parameters)),
                "strict": True,
            }
        )
    return definitions


def _common_instructions(instruction: Mapping[str, Any]) -> str:
    scope = instruction.get("scope")
    success_boundary = instruction.get("success_boundary")
    if not isinstance(scope, str) or not isinstance(success_boundary, str):
        raise ApiDriverError("PRT-002 instruction is missing scope or success boundary")
    return "\n".join(
        [
            "You are a fixed pilot in a controlled synthetic research trial.",
            scope,
            success_boundary,
            "Use only the declared function tools. Do not invent tools, targets, routes, "
            "files, repositories, databases, credentials, or external systems.",
            "Do not claim Mission 10, GitHub, Supabase, production, or canonical RUN success.",
            f"When you believe the synthetic task is complete, reply with exactly: {SUCCESS_CLAIM}",
            f"If you cannot complete it, reply with exactly: {UNABLE_CLAIM}",
            "Do not add commentary to either completion line.",
        ]
    )


def _request_payload(
    instruction: Mapping[str, Any],
    input_items: list[Any],
    config: DriverConfig,
) -> dict[str, Any]:
    return {
        "model": config.model,
        "store": False,
        "reasoning": {"effort": config.reasoning_effort},
        "max_output_tokens": config.max_output_tokens_per_turn,
        "instructions": _common_instructions(instruction),
        "input": input_items,
        "tools": _tool_definitions(instruction),
        "tool_choice": "auto",
        "parallel_tool_calls": False,
    }


def plan_next_trial(batch: PreregisteredBatch, *, config: DriverConfig = DEFAULT_DRIVER_CONFIG) -> dict[str, Any]:
    """Return the exact next request plan without opening a trial or touching the network."""

    _validated_registration(batch, config)
    spec = _next_spec(batch)
    instruction = agent_instruction(spec.variant)
    payload = _request_payload(
        instruction,
        [{"role": "user", "content": instruction["task"]}],
        config,
    )
    return {
        "artifact_kind": "noncanonical-api-driver-dry-run-plan",
        "evidence_status": "synthetic-prototype-only-not-a-RUN",
        "batch_id": batch.batch_id,
        "next_trial_id": spec.trial_id,
        "variant": spec.variant,
        "model_config": config.as_dict(),
        "request": payload,
        "network_performed": False,
    }


def _response_output(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    output = response.get("output")
    if not isinstance(output, list):
        raise ApiDriverError("Responses API reply had no output item list")
    normalized: list[Mapping[str, Any]] = []
    for item in output:
        if not isinstance(item, Mapping):
            raise ApiDriverError("Responses API output item was not an object")
        normalized.append(item)
    return normalized


def _response_text(response: Mapping[str, Any], output: list[Mapping[str, Any]]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str):
        return direct

    parts: list[str] = []
    for item in output:
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, Mapping) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def _usage_from(response: Mapping[str, Any]) -> dict[str, int]:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return {}
    result: dict[str, int] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if isinstance(value, int) and value >= 0:
            result[key] = value
    return result


def _add_usage(total: dict[str, int], addition: Mapping[str, int]) -> None:
    for key, value in addition.items():
        total[key] = total.get(key, 0) + value


def _emit_driver_event(trial: ControlledTrial, event_type: str, **fields: Any) -> None:
    trial.telemetry.emit(
        {
            "timestamp": now_iso(),
            "event_type": event_type,
            "source": "api_driver",
            **fields,
        }
    )


def _transport_error_kind(exc: Exception) -> str:
    """Classify a transport failure without persisting arbitrary error text."""

    if isinstance(exc, TimeoutError):
        return "timeout"
    if isinstance(exc, urllib.error.URLError):
        return "network_error"
    if isinstance(exc, ApiDriverError):
        return "api_driver_error"
    return "transport_error"


def _finalize(
    trial: ControlledTrial,
    *,
    response_ids: list[str],
    model_turns: int,
    usage: Mapping[str, int],
    terminal_error: str | None,
    request_attempts: int,
    unknown_request_attempts: int,
) -> DriverOutcome:
    result = trial.finalize()
    trial_status = "COMPLETE" if terminal_error is None else "INCOMPLETE"
    outcome = DriverOutcome(
        result=result,
        model_response_ids=tuple(response_ids),
        model_turns=model_turns,
        usage=dict(usage),
        terminal_error=terminal_error,
        trial_status=trial_status,
        request_attempts=request_attempts,
        unknown_request_attempts=unknown_request_attempts,
    )
    _write_json_new(trial.trial_dir / DRIVER_OUTCOME_FILENAME, outcome.as_dict())
    _write_json_new(
        trial.trial_dir / DRIVER_RECEIPT_FILENAME,
        {
            "artifact_kind": "noncanonical-api-driver-receipt",
            "evidence_status": "synthetic-prototype-only-not-a-RUN",
            "driver_version": DRIVER_VERSION,
            "completed_at": now_iso(),
            "trial_status": trial_status,
            "acceptance_status": (
                "SYNTHETIC_COMPLETE_NOT_A_RUN" if trial_status == "COMPLETE" else "NOT_ACCEPTED"
            ),
            "request_journal_path": "events.jsonl",
            "request_attempts": request_attempts,
            "unknown_request_attempts": unknown_request_attempts,
            "model_response_ids": list(response_ids),
            "usage": dict(usage),
            "terminal_error": terminal_error,
            "result_digest": digest(result),
            "verifier_proof_digest": digest(result["verifier_proof"]),
        },
    )
    return outcome


def run_next_trial(
    batch: PreregisteredBatch,
    transport: ResponsesTransport,
    *,
    config: DriverConfig = DEFAULT_DRIVER_CONFIG,
) -> DriverOutcome:
    """Run exactly one pre-registered trial through an injected transport.

    This function has no implicit network behavior. Network access happens only
    if the supplied transport performs it; the CLI supplies that transport only
    after both explicit live-run flags are present.
    """

    _validated_registration(batch, config)
    spec = _next_spec(batch)
    trial = batch.open_trial(spec.trial_id)
    instruction = trial.instruction
    input_items: list[Any] = [{"role": "user", "content": instruction["task"]}]
    response_ids: list[str] = []
    usage: dict[str, int] = {}
    terminal_error: str | None = None
    request_attempts = 0
    unknown_request_attempts = 0

    try:
        for model_turn in range(1, config.max_model_turns + 1):
            payload = _request_payload(instruction, input_items, config)
            request_attempts += 1
            request_fingerprint = digest(payload)
            _emit_driver_event(
                trial,
                "api_request_started",
                model_turn=model_turn,
                request_attempt=request_attempts,
                request_fingerprint=request_fingerprint,
            )
            try:
                response = transport.create(payload)
            except Exception as exc:
                unknown_request_attempts += 1
                _emit_driver_event(
                    trial,
                    "api_request_incomplete",
                    model_turn=model_turn,
                    request_attempt=request_attempts,
                    request_fingerprint=request_fingerprint,
                    outcome_status="UNKNOWN",
                    error_kind=_transport_error_kind(exc),
                )
                terminal_error = (
                    "Responses transport ended after request_started; request outcome is UNKNOWN/INCOMPLETE"
                )
                break
            if not isinstance(response, Mapping):
                raise ApiDriverError("Responses transport returned a non-object response")
            response_id = response.get("id")
            if isinstance(response_id, str):
                response_ids.append(response_id)
            response_usage = _usage_from(response)
            _add_usage(usage, response_usage)
            _emit_driver_event(
                trial,
                "api_response_observed",
                model_turn=model_turn,
                request_attempt=request_attempts,
                response_id=response_id if isinstance(response_id, str) else None,
                usage=response_usage,
            )

            output = _response_output(response)
            input_items.extend(output)
            calls = [item for item in output if item.get("type") == "function_call"]

            if not calls:
                final_text = _response_text(response, output)
                _emit_driver_event(trial, "agent_final_response", text=final_text)
                if final_text.strip() == SUCCESS_CLAIM:
                    trial.declare_success()
                elif final_text.strip() == UNABLE_CLAIM:
                    _emit_driver_event(trial, "agent_completion_unable")
                else:
                    _emit_driver_event(
                        trial,
                        "agent_completion_protocol_error",
                        message="final response did not use a pre-registered completion line",
                    )
                return _finalize(
                    trial,
                    response_ids=response_ids,
                    model_turns=model_turn,
                    usage=usage,
                    terminal_error=None,
                    request_attempts=request_attempts,
                    unknown_request_attempts=unknown_request_attempts,
                )

            for call in calls:
                name = call.get("name")
                call_id = call.get("call_id")
                arguments_text = call.get("arguments")
                if not isinstance(name, str) or not isinstance(call_id, str) or not isinstance(
                    arguments_text, str
                ):
                    raise ApiDriverError("function call item lacks name, call_id, or JSON arguments")
                try:
                    arguments = json.loads(arguments_text)
                except json.JSONDecodeError as exc:
                    _emit_driver_event(
                        trial,
                        "driver_error",
                        stage="tool_arguments",
                        message="model emitted invalid JSON arguments",
                    )
                    raise ApiDriverError("model emitted invalid JSON function arguments") from exc
                if not isinstance(arguments, Mapping):
                    raise ApiDriverError("model function arguments must decode to an object")
                tool_result = trial.call(name, **dict(arguments))
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(tool_result, ensure_ascii=False, sort_keys=True),
                    }
                )

        if terminal_error is None:
            terminal_error = (
                f"model exceeded the pre-registered limit of {config.max_model_turns} API turns"
            )
            _emit_driver_event(trial, "driver_stop", stage="model_turn_limit", message=terminal_error)
    except (ApiDriverError, HarnessError) as exc:
        terminal_error = str(exc)
        _emit_driver_event(trial, "driver_error", stage="api_driver", message=terminal_error)

    return _finalize(
        trial,
        response_ids=response_ids,
        model_turns=len(response_ids),
        usage=usage,
        terminal_error=terminal_error,
        request_attempts=request_attempts,
        unknown_request_attempts=unknown_request_attempts,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PRT-003 explicit-gate API driver for non-canonical PRT-002 trials"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create-batch",
        help="Create a pre-registered external batch; makes no API request.",
    )
    create.add_argument("--outdir", required=True, help="External output directory")
    create.add_argument("--operator", required=True, help="Recorded human/system operator")
    create.add_argument(
        "--source-revision",
        required=True,
        help="Exact PRT-002 harness source revision recorded by the batch",
    )
    create.add_argument(
        "--driver-source-revision",
        required=True,
        help="Exact PRT-003 source revision recorded by the driver registration",
    )
    create.add_argument("--repeats-per-variant", type=int, default=3)

    plan = commands.add_parser(
        "plan-next",
        help="Print the next trial plan without opening a trial or making an API request.",
    )
    plan.add_argument("--batch-dir", required=True, help="Existing external BATCH-* directory")

    inspect = commands.add_parser(
        "inspect-interrupted",
        help="Read-only STOP report for any unfinalized trial; never retries or resumes it.",
    )
    inspect.add_argument("--batch-dir", required=True, help="Existing external BATCH-* directory")

    validate = commands.add_parser(
        "validate-external-evidence",
        help="Read-only redacted evidence check; never opens a trial or makes an API request.",
    )
    validate.add_argument("--batch-dir", required=True, help="Existing external BATCH-* directory")

    archive = commands.add_parser(
        "archive-external-evidence",
        help="Create one immutable manifest only for a terminal validated external batch; no API request.",
    )
    archive.add_argument("--batch-dir", required=True, help="Existing external BATCH-* directory")

    run = commands.add_parser(
        "run-next",
        help="Run exactly one next trial only after two explicit live-run flags.",
    )
    run.add_argument("--batch-dir", required=True, help="Existing external BATCH-* directory")
    run.add_argument(
        "--live",
        action="store_true",
        help="Required: permit one actual Responses API trial.",
    )
    run.add_argument(
        "--confirm-live-run",
        action="store_true",
        help="Required: second acknowledgement that this makes paid API calls.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)

    if args.command == "create-batch":
        batch = create_api_batch(
            Path(args.outdir),
            operator=args.operator,
            source_revision=args.source_revision,
            driver_source_revision=args.driver_source_revision,
            repeats_per_variant=args.repeats_per_variant,
        )
        print(f"Non-canonical PRT-003 batch created: {batch.batch_dir}")
        return

    if args.command == "validate-external-evidence":
        from .evidence import validate_external_batch

        report = validate_external_batch(Path(args.batch_dir))
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        if report["validation_status"] in {
            "INVALID",
            "STOP_REQUIRED",
            "ACTIVE_NOT_ARCHIVABLE",
        }:
            raise SystemExit(1)
        return

    if args.command == "archive-external-evidence":
        from .evidence import EvidenceValidationError, archive_external_batch

        try:
            manifest = archive_external_batch(Path(args.batch_dir))
        except EvidenceValidationError as exc:
            raise SystemExit(str(exc)) from exc
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return

    batch = load_api_batch(Path(args.batch_dir))
    if args.command == "plan-next":
        print(json.dumps(plan_next_trial(batch), ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.command == "inspect-interrupted":
        print(
            json.dumps(
                inspect_interrupted_trials(batch),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return

    if not args.live or not args.confirm_live_run:
        raise SystemExit(
            "PRT-003 refuses to make an API request without both --live and --confirm-live-run"
        )
    outcome = run_next_trial(batch, HttpResponsesTransport())
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
