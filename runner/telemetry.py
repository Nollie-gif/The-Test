"""Simple telemetry emitter writing newline-delimited JSON events.

Events are structured and are the primary evidence for derived metrics.
"""

from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Dict, Any


class Telemetry:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("x", encoding="utf-8")
        self._seq = 0
        self._lock = Lock()

    def emit(self, event: Dict[str, Any]):
        """Write one event with a runner-owned, monotonically increasing sequence."""
        with self._lock:
            self._seq += 1
            payload = dict(event)
            payload["sequence"] = self._seq
            self.file.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.file.flush()

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass
