commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/__main__.py b/runner/__main__.py
new file mode 100644
index 0000000..7d26fd0
--- /dev/null
+++ b/runner/__main__.py
@@ -0,0 +1,5 @@
+# Runner CLI entrypoint
+from .runner import main
+
+if __name__ == '__main__':
+    main()
