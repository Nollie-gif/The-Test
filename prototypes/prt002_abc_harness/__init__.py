"""PRT-002 pre-registered A/B/C harness for the synthetic PRT-001 target."""

from .harness import (
    HarnessError,
    PreregisteredBatch,
    ControlledTrial,
    agent_instruction,
)

__all__ = [
    "ControlledTrial",
    "HarnessError",
    "PreregisteredBatch",
    "agent_instruction",
]
