commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/adapters/variant_c.py b/runner/adapters/variant_c.py
new file mode 100644
index 0000000..dc314de
--- /dev/null
+++ b/runner/adapters/variant_c.py
@@ -0,0 +1,37 @@
+"""Variant C: Deterministic composite action mock.
+
+This adapter simulates a single high-level affordance quicksave().
+"""
+
+from __future__ import annotations
+
+from datetime import datetime, timezone
+from runner.adapters.base import AdapterBase
+
+
+def now_iso():
+    return datetime.now(timezone.utc).isoformat()
+
+
+class Adapter(AdapterBase):
+    def __init__(self, telemetry):
+        super().__init__(telemetry)
+
+    def run_task(self, exp_id: str):
+        # Single composite action
+        self.telemetry.emit({
+            "timestamp": now_iso(),
+            "event_type": "tool_call",
+            "source": "adapter",
+            "tool": "quicksave",
+            "args": {},
+            "result": "ok",
+        })
+        # Agent may claim success
+        self.telemetry.emit({
+            "timestamp": now_iso(),
+            "event_type": "agent_success_claim",
+            "source": "agent",
+            "claim": "quicksave_complete",
+            "claim_type": "explicit",
+        })
