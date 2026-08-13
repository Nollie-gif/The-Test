commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/adapters/variant_a.py b/runner/adapters/variant_a.py
new file mode 100644
index 0000000..2bc2111
--- /dev/null
+++ b/runner/adapters/variant_a.py
@@ -0,0 +1,48 @@
+"""Variant A: Low-level agent orchestration mock.
+
+This adapter simulates an agent performing multiple low-level persistence actions.
+It emits structured events for tool calls, errors, and success claims.
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
+        # Simulate a sequence of low-level operations that an agent would execute.
+        steps = [
+            {"tool": "resolve_project", "args": {"hint": "production"}},
+            {"tool": "read_runtime", "args": {}},
+            {"tool": "stage_changes", "args": {}},
+            {"tool": "git_sync", "args": {}},
+            {"tool": "validate", "args": {}},
+            {"tool": "publish", "args": {}},
+            {"tool": "confirm_mirror", "args": {}},
+        ]
+        for s in steps:
+            self.telemetry.emit({
+                "timestamp": now_iso(),
+                "event_type": "tool_call",
+                "source": "adapter",
+                "tool": s["tool"],
+                "args": s["args"],
+                "result": "ok",
+            })
+        # Agent declares success (non-authoritative)
+        self.telemetry.emit({
+            "timestamp": now_iso(),
+            "event_type": "agent_success_claim",
+            "source": "agent",
+            "claim": "quicksave_complete",
+            "claim_type": "explicit",
+        })
