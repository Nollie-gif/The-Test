"""Shared deterministic representation helpers for PRT-001.

The target and verifier deliberately own their decision logic separately. They
share only canonical JSON encoding and SHA-256 helpers so both can name the
same expected state precisely.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def payload_digest(payload: Mapping[str, Any]) -> str:
    return digest(dict(payload))


def state_digest(
    *,
    target_id: str,
    generation: int,
    payload: Mapping[str, Any],
    last_transaction_id: str | None,
) -> str:
    return digest(
        {
            "target_id": target_id,
            "generation": generation,
            "payload": dict(payload),
            "last_transaction_id": last_transaction_id,
        }
    )
