commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/README.md b/runner/README.md
new file mode 100644
index 0000000..29e8daf
--- /dev/null
+++ b/runner/README.md
@@ -0,0 +1,40 @@
+# Fixture Runner
+
+This is a **non-evidentiary test rig** for EXP-001. It creates only
+`FIXTURE-*` artifacts and cannot create a canonical `RUN-###` record.
+
+## What it checks
+
+- A/B/C adapters share one fixture interface.
+- Telemetry is recorded in `events.jsonl` with runner-owned `sequence` values.
+- A fixture receipt is produced by `FixtureVerifier`.
+- The fixture validator checks the fixture schema and required sidecars.
+
+`FixtureVerifier` only confirms whether its mock event stream saw an error condition. Its
+`fixture_verified` result is **not** authoritative success and cannot prove
+final-state correctness.
+
+## Local pre-flight
+
+```bash
+python -m pip install -r requirements-dev.txt
+python scripts/validate_research_repo.py
+python scripts/validate_runs.py
+python -m pytest -q
+```
+
+Example isolated fixture:
+
+```bash
+python -m runner --exp EXP-001 --variant A --fixture --outdir /tmp/exp-001-fixture
+```
+
+## Authority boundary
+
+- `schemas/run.schema.json` on `main` remains the sole canonical research RUN
+  contract.
+- `runner/schemas/fixture.schema.json` governs fixture/runtime data only.
+- Sidecars (`environment.json`, `events.jsonl`, `receipt.json`) preserve
+  fixture reproducibility details without expanding the canonical schema.
+- A canonical export layer and `RUN-001` remain blocked until a real verifier,
+  metric mapping, promotion review, and CI checks are accepted.
