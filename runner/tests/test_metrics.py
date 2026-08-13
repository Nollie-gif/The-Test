commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/tests/test_metrics.py b/runner/tests/test_metrics.py
new file mode 100644
index 0000000..d2d4645
--- /dev/null
+++ b/runner/tests/test_metrics.py
@@ -0,0 +1,27 @@
+import json
+
+from runner.runner import compute_derived_metrics
+
+
+def test_fixture_metrics_keep_wrong_tool_and_wrong_target_separate(tmp_path):
+    events = [
+        {"timestamp": "2026-08-13T00:00:00Z", "event_type": "tool_call", "operation": "read", "resource_id": "runtime"},
+        {"timestamp": "2026-08-13T00:00:01Z", "event_type": "tool_call", "operation": "read", "resource_id": "runtime"},
+        {"timestamp": "2026-08-13T00:00:02Z", "event_type": "tool_call", "classification": "wrong_tool"},
+        {"timestamp": "2026-08-13T00:00:03Z", "event_type": "tool_call", "classification": "wrong_route_target", "error_code": "permission_denied"},
+        {"timestamp": "2026-08-13T00:00:04Z", "event_type": "error"},
+        {"timestamp": "2026-08-13T00:00:05Z", "event_type": "recovery_action"},
+        {"timestamp": "2026-08-13T00:00:06Z", "event_type": "recovery_complete"},
+    ]
+    path = tmp_path / "events.jsonl"
+    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
+
+    metrics = compute_derived_metrics(path)
+
+    assert metrics["tool_calls"] == 4
+    assert metrics["wrong_tool_calls"] == 1
+    assert metrics["wrong_route_target_calls"] == 1
+    assert metrics["repeated_reads"] == 1
+    assert metrics["permission_routing_errors"] == 1
+    assert metrics["recovery_steps"] == 1
+    assert metrics["recovery_time_ms"] == 3000
