commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/telemetry.py b/runner/telemetry.py
new file mode 100644
index 0000000..1bc2136
--- /dev/null
+++ b/runner/telemetry.py
@@ -0,0 +1,35 @@
+"""Simple telemetry emitter writing newline-delimited JSON events.
+
+Events are structured and are the primary evidence for derived metrics.
+"""
+
+from __future__ import annotations
+
+import json
+from pathlib import Path
+from threading import Lock
+from typing import Dict, Any
+
+
+class Telemetry:
+    def __init__(self, path: Path):
+        self.path = path
+        path.parent.mkdir(parents=True, exist_ok=True)
+        self.file = path.open("x", encoding="utf-8")
+        self._seq = 0
+        self._lock = Lock()
+
+    def emit(self, event: Dict[str, Any]):
+        """Write one event with a runner-owned, monotonically increasing sequence."""
+        with self._lock:
+            self._seq += 1
+            payload = dict(event)
+            payload["sequence"] = self._seq
+            self.file.write(json.dumps(payload, ensure_ascii=False) + "\n")
+            self.file.flush()
+
+    def close(self):
+        try:
+            self.file.close()
+        except Exception:
+            pass
