commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/experiments/EXP-001-QUICKSAVE/README.md b/experiments/EXP-001-QUICKSAVE/README.md
index 5c8aec6..37af2a6 100644
--- a/experiments/EXP-001-QUICKSAVE/README.md
+++ b/experiments/EXP-001-QUICKSAVE/README.md
@@ -66,6 +66,36 @@ The agent sees success/failure and structured evidence, not the internal persist
 - context volume / routing burden when observable;
 - final receipt completeness.
 
+## Metric semantics v1
+
+These definitions govern future canonical EXP-001 exports. Fixture diagnostics may
+exercise them, but are not controlled evidence.
+
+- **wrong tool call:** a call explicitly classified as `wrong_tool`: the chosen
+  operation is outside the permitted tool contract for that variant.
+- **wrong route/target call:** a call explicitly classified as
+  `wrong_route_target`: the operation may be appropriate, but its project,
+  branch, endpoint, or resource target is wrong.
+- **repeated read:** every read after the first of the same stable
+  `resource_id` within one run. Reads without a resource identity are not
+  counted as repeated reads.
+- **recovery:** starts at the first `error` event or error-coded tool call, and
+  ends only at an explicit `recovery_complete` event after a terminal verifier
+  verdict. A run with an unfinished recovery has no recovery-time value.
+- **false success:** an explicit completion claim followed by a negative or
+  absent authoritative receipt. No claim is not a false success.
+- **authoritative success / final-state correctness:** can be true only when a
+  real verifier proves the intended gated transaction and compares the
+  authoritative final state to predeclared expected invariants. A mock
+  verifier's absence-of-error result is never sufficient.
+- **receipt complete:** a real receipt must identify the run, variant, verifier
+  and version, verified target, expected-state reference, observed final
+  revision/state, terminal outcome, timestamps, and failure information when
+  applicable.
+
+Telemetry uses the field name `sequence`; `seq` is not accepted for new
+fixtures. Canonical export remains intentionally unimplemented and opt-in.
+
 ## Initial hypothesis
 
 Variant C should reduce routing failures, tool churn, recovery cost, and procedural cognitive load without weakening persistence safety, provided the composite action preserves the existing validation and receipt boundary rather than bypassing it.
