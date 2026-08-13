"""Variant A: Low-level agent orchestration mock.

This adapter simulates an agent performing multiple low-level persistence actions.
It emits structured events for tool calls, errors, and success claims.
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
        # Simulate a sequence of low-level operations that an agent would execute.
        steps = [
            {"tool": "resolve_project", "args": {"hint": "production"}},
            {"tool": "read_runtime", "args": {}},
            {"tool": "stage_changes", "args": {}},
            {"tool": "git_sync", "args": {}},
            {"tool": "validate", "args": {}},
            {"tool": "publish", "args": {}},
            {"tool": "confirm_mirror", "args": {}},
        ]
        for s in steps:
            self.telemetry.emit({
                "timestamp": now_iso(),
                "event_type": "tool_call",
                "source": "adapter",
                "tool": s["tool"],
                "args": s["args"],
                "result": "ok",
            })
        # Agent declares success (non-authoritative)
        self.telemetry.emit({
            "timestamp": now_iso(),
            "event_type": "agent_success_claim",
            "source": "agent",
            "claim": "quicksave_complete",
            "claim_type": "explicit",
        })
