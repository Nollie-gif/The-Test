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

## Validation

Before committing:

```bash
python scripts/validate_research_repo.py
```

GitHub Actions runs the same validation automatically.

## Prototype rule

A prototype implements an experiment variant. It must not silently redesign the experiment, change success criteria, or hide a failure. If the desired architecture changes, update the experiment design before benchmarking it.

## License

No project license is selected by this workflow. Licensing is an explicit owner decision and should not be inferred from repository visibility.
