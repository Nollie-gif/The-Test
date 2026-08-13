commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/verifier.py b/runner/verifier.py
new file mode 100644
index 0000000..bbcb4cc
--- /dev/null
+++ b/runner/verifier.py
@@ -0,0 +1,49 @@
+"""Deterministic fixture verifier.
+
+This verifier only checks the fixture event stream. It cannot prove an
+authoritative final state and must never be used as evidence-run authority.
+"""
+
+from __future__ import annotations
+
+import json
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Dict, Any
+
+
+class FixtureVerifier:
+    def __init__(self, version: str = "fixture-mock-verifier-0.2"):
+        self.version = version
+
+    def verify(self, run_dir: Path) -> Dict[str, Any]:
+        # Simple deterministic verification: if events.jsonl contains any error event, mark not verified
+        events_path = run_dir / "events.jsonl"
+        verified = True
+        failure_stage = None
+        if events_path.exists():
+            with events_path.open("r", encoding="utf-8") as fh:
+                for line in fh:
+                    if not line.strip():
+                        continue
+                    try:
+                        ev = json.loads(line)
+                    except Exception:
+                        continue
+                    if ev.get("event_type") == "error" or ev.get("error_code"):
+                        verified = False
+                        failure_stage = ev.get("stage") or ev.get("event_type", "unknown")
+                        break
+        receipt = {
+            "fixture_verified": verified,
+            "verifier": self.version,
+            "verified_at": datetime.now(timezone.utc).isoformat(),
+            "authoritative": False,
+            "failure_stage": failure_stage,
+            "details": (
+                "fixture verifier: no error condition observed"
+                if verified
+                else "fixture verifier: error condition observed"
+            ),
+        }
+        return receipt
