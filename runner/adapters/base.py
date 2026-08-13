commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/adapters/base.py b/runner/adapters/base.py
new file mode 100644
index 0000000..ace798e
--- /dev/null
+++ b/runner/adapters/base.py
@@ -0,0 +1,26 @@
+"""Adapter base contract and registry.
+
+Adapters must implement AdapterBase with a run_task(exp_id) method and accept a telemetry object.
+"""
+
+from __future__ import annotations
+
+from ..telemetry import Telemetry
+
+
+class AdapterBase:
+    def __init__(self, telemetry: Telemetry):
+        self.telemetry = telemetry
+
+    def run_task(self, exp_id: str):
+        raise NotImplementedError("Adapter must implement run_task")
+
+
+# Adapter loader
+from importlib import import_module
+
+
+def get_adapter(variant: str, telemetry: Telemetry) -> AdapterBase:
+    mod_name = f"runner.adapters.variant_{variant.lower()}"
+    mod = import_module(mod_name)
+    return mod.Adapter(telemetry)
