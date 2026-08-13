# Runner (fixture mode) — README

Purpose
- Lightweight, deterministic runner designed to support fixture/testing and non-evidentiary example runs.
- Emits telemetry to `events.jsonl` and writes `run.json`, `receipt.json`, and `environment.json`.

Quick start (fixture mode)
- Example (from repository root):
  - python -m runner.runner --exp EXP-001 --variant A --fixture --outdir /tmp/out
- Produced files in outdir:
  - environment.json — captured environment manifest (no secrets)
  - events.jsonl — newline-delimited JSON telemetry (canonical evidence for derived metrics)
  - receipt.json — verifier output (authoritative for run.success)
  - run.json — run metadata (validated by runner/schemas/run.schema.json)

Notes on authority
- events.jsonl is the canonical telemetry/evidence stream; derived metrics should be computed from it.
- `agent_success_claim` events are recorded but are NOT authoritative for `run.success`.
- The verifier's `receipt.json` is authoritative for `run.success` and `failure_stage`.

Tests & validation (local)
- Validate example fixtures (fixture-only validator):
  - python3 scripts/validate_runs.py
  - This script intentionally only validates runs whose `run_id` or directory name starts with `FIXTURE-` or `TEST-RUN-` to avoid touching real evidence.
- Run the unit tests:
  - pytest -q
  - All tests use `tmp_path` or `FIXTURE-/TEST-RUN-*` ids and are designed to be ephemeral.

CI / Research Validation integration (project-manager)
- I attempted to add a Research Validation workflow to this branch, but the repository did not permit creating or updating `.github/workflows/research-validation.yml` from this agent.
- Action requested (PM): integrate the new fixture validator (`scripts/validate_runs.py`) and the added pytest tests into the project's existing Research Validation workflow without replacing or disabling the current validation behavior.
  - The new validator only targets `FIXTURE-` and `TEST-RUN-` directories; it is safe to run in CI when combined with existing repo validations.
  - Recommend adding a step before or after the existing validations to run: `python scripts/validate_runs.py` and then `pytest -q` (or the repository's existing test command). Ensure the workflow keeps existing validation steps and does not accidentally validate real evidence.

Safety and guardrails enforced by this implementation
- The fixture validator and tests only validate or create artifacts for `FIXTURE-` or `TEST-RUN-` ids or use ephemeral temporary directories (`tmp_path`). No RUN-### or persistent evidence artifacts are created by tests or the validator.
- The runner remains adapter-architecture neutral — adapters A/B/C implement the same AdapterBase contract and emit telemetry through the Telemetry API.
- `events.jsonl` is treated as the primary evidence stream; the verifier's `receipt.json` is authoritative for final `run.success`.

What to do next (integration plan)
1. PM: merge branch `add-runner` into a review branch or open a PR.
2. PM or CI owner: add the `scripts/validate_runs.py` step and run `pytest -q` in the repository's existing Research Validation workflow, keeping current validation steps intact.
3. Run CI and inspect the Research Validation result. If any validator or tests fail, collect the failing run/example files and CI logs and follow the validation/failure policy below.

Validation / failure policy (automatic)
- If the fixture validator or tests report failures that indicate schema or contract mismatches, the agent will:
  1. Stop further automated changes.
  2. Report the exact failing evidence (paths and file contents for `run.json` / `events.jsonl` and the full validator/pytest error output).
  3. Wait for PM approval before proposing or making any schema or contract changes.

Contacts/ownership
- Authoring agent: GitHub Copilot automation (branch: add-runner)
- Integration owner: project manager / CI owner (to add validator & tests into existing Research Validation workflow)

Limitations
- CI workflow file (.github/workflows/research-validation.yml) was not created due to repository permission restrictions. I treated that as an integration blocker and left it for PM review as requested.

Files added on branch `add-runner` (summary)
- runner/
  - __main__.py (CLI entrypoint)
  - telemetry.py (JSONL telemetry emitter)
  - adapters/base.py
  - adapters/variant_a.py
  - adapters/variant_b.py
  - adapters/variant_c.py
  - verifier.py (mock verifier)
  - runner.py (fixture-mode orchestrator)
  - utils.py (atomic JSON write, FIXTURE-* allocator)
  - env_freeze.py (environment manifest capture)
  - schemas/run.schema.json (run schema)
  - tests/
    - test_telemetry.py
    - test_adapters.py
    - test_verifier.py
    - test_runner_fixture.py
- scripts/
  - validate_runs.py (fixture-only run validator)
- datasets/runs/EXP-001/FIXTURE-000/ (example non-evidentiary fixture)
  - environment.json
  - events.jsonl
  - receipt.json
  - run.json
- runner/README.md (this file)

End of README
