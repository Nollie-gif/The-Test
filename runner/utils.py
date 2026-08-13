"""Utility helpers for runner: run id allocation and atomic write helpers.

FIXTURE and TEST ids only in this implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime


def allocate_fixture_run_id(exp_id: str) -> str:
    # produce a deterministic fixture id based on timestamp
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"FIXTURE-{ts}"


def write_json_atomic(path: Path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)
