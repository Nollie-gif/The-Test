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
        # ensure parent dir exists
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a", encoding="utf-8")
        self._seq = 0
        self._lock = Lock()

    def next_sequence(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq

    def emit(self, event: Dict[str, Any]):
        if "sequence" not in event:
            event["sequence"] = self.next_sequence()
        self.file.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.file.flush()

    def close(self):
        try:
            self.file.close()
        except Exception:
            pass
