"""Variant C: Deterministic composite action mock.

This adapter simulates a single high-level affordance quicksave().
"""

from __future__ import annotations

from datetime import datetime, timezone
from runner.adapters.base import AdapterBase


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class Adapter(AdapterBase):
    def __init__(self, telemetry):
        super().__init__(telemetry)

    def run_task(self, exp_id: str):
        # Single composite action
        self.telemetry.emit({
            "timestamp": now_iso(),
            "event_type": "tool_call",
            "source": "adapter",
            "tool": "quicksave",
            "args": {},
            "result": "ok",
        })
        # Agent may claim success
        self.telemetry.emit({
            "timestamp": now_iso(),
            "event_type": "agent_success_claim",
            "source": "agent",
            "claim": "quicksave_complete",
            "claim_type": "explicit",
        })
