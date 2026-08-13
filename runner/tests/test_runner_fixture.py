commit cb33223d5f862d4c3831da9dc34123871a4cd5d9
Author: Codex <codex@openai.com>
Date:   Fri Aug 14 00:18:30 2026 +0530

    runner: add fixture-only preflight validation

diff --git a/runner/tests/test_runner_fixture.py b/runner/tests/test_runner_fixture.py
new file mode 100644
index 0000000..dbed50a
--- /dev/null
+++ b/runner/tests/test_runner_fixture.py
@@ -0,0 +1,69 @@
+import json
+from pathlib import Path
+
+import pytest
+from jsonschema import Draft202012Validator, FormatChecker
+
+from runner import runner as runner_module
+
+
+def test_runner_fixture_end_to_end(tmp_path):
+    outdir = tmp_path / "out_run"
+    # run runner in fixture mode and write into outdir
+    argv = [
+        "--exp",
+        "EXP-001",
+        "--variant",
+        "A",
+        "--fixture",
+        "--outdir",
+        str(outdir),
+    ]
+    runner_module.main(argv)
+
+    # verify files created
+    run_json_path = outdir / "run.json"
+    receipt_path = outdir / "receipt.json"
+    events_path = outdir / "events.jsonl"
+    env_path = outdir / "environment.json"
+
+    assert run_json_path.exists()
+    assert receipt_path.exists()
+    assert events_path.exists()
+    assert env_path.exists()
+
+    run_obj = json.loads(run_json_path.read_text(encoding="utf-8"))
+    # basic schema validation
+    schema_path = Path(__file__).resolve().parents[2] / "runner" / "schemas" / "fixture.schema.json"
+    schema = json.loads(schema_path.read_text(encoding="utf-8"))
+    Draft202012Validator(schema, format_checker=FormatChecker()).validate(run_obj)
+
+    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
+    assert receipt["authoritative"] is False
+    assert receipt["fixture_verified"] == run_obj["fixture_verified"]
+
+    # events are structured JSON lines
+    lines = [l for l in events_path.read_text(encoding="utf-8").splitlines() if l.strip()]
+    for sequence, line in enumerate(lines, start=1):
+        obj = json.loads(line)
+        assert "event_type" in obj
+        assert obj["sequence"] == sequence
+
+
+def test_runner_blocks_non_fixture_mode():
+    with pytest.raises(SystemExit):
+        runner_module.main(["--exp", "EXP-001", "--variant", "A"])
+
+
+def test_runner_default_output_is_under_the_repository_dataset_tree(tmp_path, monkeypatch):
+    fake_repo_root = tmp_path / "repo"
+    fake_runner_file = fake_repo_root / "runner" / "runner.py"
+    fake_runner_file.parent.mkdir(parents=True)
+    fake_runner_file.touch()
+    monkeypatch.setattr(runner_module, "__file__", str(fake_runner_file))
+
+    runner_module.main(["--exp", "EXP-001", "--variant", "B", "--fixture"])
+
+    run_dirs = list((fake_repo_root / "datasets" / "runs" / "EXP-001").glob("FIXTURE-*"))
+    assert len(run_dirs) == 1
+    assert (run_dirs[0] / "run.json").is_file()
