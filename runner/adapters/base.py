"""Adapter base contract and registry.

Adapters must implement AdapterBase with a run_task(exp_id) method and accept a telemetry object.
"""

from __future__ import annotations

from typing import Any
from .telemetry import Telemetry


class AdapterBase:
    def __init__(self, telemetry: Telemetry):
        self.telemetry = telemetry

    def run_task(self, exp_id: str):
        raise NotImplementedError("Adapter must implement run_task")


# Adapter loader
from importlib import import_module


def get_adapter(variant: str, telemetry: Telemetry) -> AdapterBase:
    mod_name = f"runner.adapters.variant_{variant.lower()}"
    mod = import_module(mod_name)
    return mod.Adapter(telemetry)
