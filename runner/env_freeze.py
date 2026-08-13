commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/env_freeze.py b/runner/env_freeze.py
new file mode 100644
index 0000000..bcc7875
--- /dev/null
+++ b/runner/env_freeze.py
@@ -0,0 +1,21 @@
+"""Capture a minimal environment manifest for reproducibility.
+
+Do not include secrets. Keep output small and deterministic where possible.
+"""
+
+from __future__ import annotations
+
+import platform
+import sys
+from typing import Dict, Any
+
+
+def capture_environment_manifest() -> Dict[str, Any]:
+    manifest = {
+        "python_version": sys.version.split()[0],
+        "platform": platform.platform(),
+        "executable": sys.executable,
+        "cwd": None,
+        "packages": {},
+    }
+    return manifest
