commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/utils.py b/runner/utils.py
new file mode 100644
index 0000000..37d91b2
--- /dev/null
+++ b/runner/utils.py
@@ -0,0 +1,23 @@
+"""Utility helpers for runner: run id allocation and atomic write helpers.
+
+FIXTURE and TEST ids only in this implementation.
+"""
+
+from __future__ import annotations
+
+import json
+from pathlib import Path
+from datetime import datetime, timezone
+
+
+def allocate_fixture_run_id(exp_id: str) -> str:
+    """Return a fixture-only id with enough precision to avoid normal collisions."""
+    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
+    return f"FIXTURE-{ts}"
+
+
+def write_json_atomic(path: Path, obj):
+    tmp = path.with_suffix(path.suffix + ".tmp")
+    with tmp.open("w", encoding="utf-8") as fh:
+        json.dump(obj, fh, indent=2, ensure_ascii=False)
+    tmp.replace(path)
