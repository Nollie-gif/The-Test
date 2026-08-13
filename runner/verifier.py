"""Verifier interface and deterministic mock verifier.

The verifier inspects the run directory and writes a receipt.json-like object.
This mock verifier is deterministic and simple for fixture/testing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


class Verifier:
    def __init__(self, version: str = "mock-verifier-0.1"):
        self.version = version

    def verify(self, run_dir: Path) -> Dict[str, Any]:
        # Simple deterministic verification: if events.jsonl contains any error event, mark not verified
        events_path = run_dir / "events.jsonl"
        verified = True
        failure_stage = None
        verification_time = None
        if events_path.exists():
            with events_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip():
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if ev.get("event_type") == "error":
                        verified = False
                        failure_stage = ev.get("stage", "unknown")
                        break
        receipt = {
            "verified": verified,
            "verified_by": self.version,
            "verification_time": verification_time,
            "failure_stage": failure_stage,
            "details": ("mock verifier: no errors observed" if verified else "mock verifier: error observed"),
        }
        return receipt
