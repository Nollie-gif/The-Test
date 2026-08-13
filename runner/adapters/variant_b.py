commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/adapters/variant_b.py b/runner/adapters/variant_b.py
new file mode 100644
index 0000000..74bbbf5
--- /dev/null
+++ b/runner/adapters/variant_b.py
@@ -0,0 +1,47 @@
+"""Variant B: Compact routed orchestration mock.
+
+This adapter simulates the agent receiving a compact routing contract and performing a few operations.
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
+        # Compact route then a smaller sequence of calls
+        self.telemetry.emit({
+            "timestamp": now_iso(),
+            "event_type": "tool_call",
+            "source": "adapter",
+            "tool": "resolve_route",
+            "args": {"route": "quicksave_contract"},
+            "result": "ok",
+        })
+        # Two subsequent actions
+        for tool in ["execute_preflight", "execute_publish"]:
+            self.telemetry.emit({
+                "timestamp": now_iso(),
+                "event_type": "tool_call",
+                "source": "adapter",
+                "tool": tool,
+                "args": {},
+                "result": "ok",
+            })
+        # Agent claims success
+        self.telemetry.emit({
+            "timestamp": now_iso(),
+            "event_type": "agent_success_claim",
+            "source": "agent",
+            "claim": "quicksave_complete",
+            "claim_type": "explicit",
+        })
