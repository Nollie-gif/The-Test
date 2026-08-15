# Contributing to The-Test

The-Test is a research lab for AI-agent interaction environments. Consistency is part of the experiment: repository organization should reduce bookkeeping, not create another memory task.

## Before adding evidence or an experiment

1. Read `RESEARCH_PROTOCOL.md`.
2. Use `REGISTRY.md` to find the next ID in the correct family.
3. Start from the matching file in `templates/`.
4. Keep observations atomic. Do not turn one incident into several claims unless they are independently useful evidence.
5. Pre-register experiment task, variants, metrics, and success criteria before reviewing results.
6. Preserve failed runs.

## Record metadata

Durable `RSH`, `EXP`, `OBS`, and `PRT` records require frontmatter fields:

- `id`
- `title`
- `status`
- `related_ids`
- `date`
- `author`

Keep `related_ids` as an inline YAML list so the dependency-free validator can parse it reliably.

## Controlled runs

- Use sequential `RUN-###` IDs.
- `RUN-000` is reserved for the example fixture.
- Store run JSON under `datasets/runs/`.
- Use `schemas/run.schema.json` as the run-data contract.
- Real experimental evidence begins at `RUN-001`.
- Never delete an ugly run merely because it damages a preferred hypothesis.

## Guarded commit flow

The-Test intentionally does not rely on a contributor remembering hidden Git,
CI, or research-safety steps. Normal commits must use the local preflight:

1. Work on a fresh `agent/...` branch — never commit directly to `main`.
2. Stage only the exact files intended for the commit.
3. Run the preflight with the same Python environment used for tests:

   ```powershell
   & "path\to\python.exe" .\scripts\preflight_commit.py
   ```

4. Commit only if it prints `COMMIT-READY`. Any `STOP-*` result means stop and
   resolve that condition first.

Install the versioned hook once per local clone:

```powershell
& "path\to\python.exe" .\scripts\install_preflight_hook.py
```

The hook accepts a normal `git commit` only when a preflight marker is less
than 15 minutes old and matches the current branch, `HEAD`, and exact staged
diff. It does not replace review or CI. `git commit --no-verify` is an explicit
process violation, not an approved shortcut.

The preflight never calls the API driver, runs `run-next`, creates a `RUN-###`
record, commits, or pushes. It checks no-reply identity without printing the
email, staged scope/whitespace, branch freshness, pytest, and both repository
validators. GitHub Actions remains the independent remote backstop.

## Prototype rule

A prototype implements an experiment variant. It must not silently redesign the experiment, change success criteria, or hide a failure. If the desired architecture changes, update the experiment design before benchmarking it.

## License

No project license is selected by this workflow. Licensing is an explicit owner decision and should not be inferred from repository visibility.
