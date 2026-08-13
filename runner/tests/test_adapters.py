commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/tests/test_adapters.py b/runner/tests/test_adapters.py
new file mode 100644
index 0000000..ecd8832
--- /dev/null
+++ b/runner/tests/test_adapters.py
@@ -0,0 +1,22 @@
+import json
+from runner.telemetry import Telemetry
+from runner.adapters.base import get_adapter
+
+
+def test_adapters_emit_events(tmp_path):
+    events_path = tmp_path / "events.jsonl"
+    telemetry = Telemetry(events_path)
+
+    for variant in ["A", "B", "C"]:
+        adapter = get_adapter(variant, telemetry=telemetry)
+        # ensure run_task does not raise
+        adapter.run_task(exp_id="EXP-TEST")
+
+    telemetry.close()
+
+    data = events_path.read_text(encoding="utf-8").splitlines()
+    assert len(data) >= 3  # at least one event per adapter
+    # ensure each line is valid JSON
+    for line in data:
+        obj = json.loads(line)
+        assert "event_type" in obj
