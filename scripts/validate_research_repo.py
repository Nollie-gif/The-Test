from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD_GLOBS = [
    "research/RSH-*.md",
    "experiments/EXP-*/README.md",
    "datasets/observations/OBS-*.md",
    "prototypes/PRT-*.md",
]
REQUIRED = {"id", "title", "status", "related_ids", "date", "author"}
ID_RE = re.compile(r"^(RSH|EXP|OBS|PRT|RES)-\d{3,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        fail(errors, f"{path.relative_to(ROOT)}: missing YAML frontmatter")
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(errors, f"{path.relative_to(ROOT)}: unterminated frontmatter")
        return {}

    data: dict[str, object] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            fail(errors, f"{path.relative_to(ROOT)}: invalid frontmatter line: {line!r}")
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [] if not inner else [x.strip() for x in inner.split(",")]
        else:
            data[key] = value
    return data


def record_files() -> list[Path]:
    found: list[Path] = []
    for pattern in RECORD_GLOBS:
        found.extend(ROOT.glob(pattern))
    return sorted(set(found))


def validate_records(errors: list[str]) -> set[str]:
    ids: set[str] = set()
    records: list[tuple[Path, dict[str, object]]] = []
    for path in record_files():
        data = parse_frontmatter(path, errors)
        records.append((path, data))
        missing = REQUIRED - set(data)
        if missing:
            fail(errors, f"{path.relative_to(ROOT)}: missing fields {sorted(missing)}")
            continue
        record_id = str(data["id"])
        if not ID_RE.match(record_id):
            fail(errors, f"{path.relative_to(ROOT)}: invalid id {record_id!r}")
        if record_id in ids:
            fail(errors, f"duplicate id: {record_id}")
        ids.add(record_id)
        if record_id not in str(path):
            fail(errors, f"{path.relative_to(ROOT)}: id {record_id} is not reflected in path")
        if not DATE_RE.match(str(data["date"])):
            fail(errors, f"{path.relative_to(ROOT)}: date must be YYYY-MM-DD")
        if not isinstance(data["related_ids"], list):
            fail(errors, f"{path.relative_to(ROOT)}: related_ids must be an inline YAML list")

    for path, data in records:
        related = data.get("related_ids", [])
        if not isinstance(related, list):
            continue
        for related_id in related:
            if related_id and ID_RE.match(str(related_id)) and related_id not in ids:
                fail(errors, f"{path.relative_to(ROOT)}: related id {related_id} does not exist")
    return ids


def validate_registry(errors: list[str], ids: set[str]) -> None:
    registry = ROOT / "REGISTRY.md"
    text = registry.read_text(encoding="utf-8")
    for record_id in sorted(ids):
        if record_id not in text:
            fail(errors, f"REGISTRY.md: missing record {record_id}")

    for raw in re.findall(r"`([^`]+)`", text):
        if not (raw.endswith(".md") or raw.endswith("/")):
            continue
        target = ROOT / raw
        if not target.exists():
            fail(errors, f"REGISTRY.md: target does not exist: {raw}")


def validate_runs(errors: list[str]) -> None:
    required = {
        "run_id", "experiment_id", "variant", "date", "authoritative_success",
        "completion_time_ms", "tool_calls", "wrong_tool_calls", "repeated_reads",
        "permission_routing_errors", "recovery_steps", "recovery_time_ms",
        "human_interventions", "false_success", "final_state_correct",
    }
    run_ids: set[str] = set()
    exp_ids = {str(parse_frontmatter(p, [])["id"]) for p in ROOT.glob("experiments/EXP-*/README.md")}
    for path in sorted(ROOT.glob("datasets/runs/RUN-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = required - set(data)
        if missing:
            fail(errors, f"{path.relative_to(ROOT)}: missing run fields {sorted(missing)}")
            continue
        run_id = str(data["run_id"])
        if not re.match(r"^RUN-\d{3,}$", run_id):
            fail(errors, f"{path.relative_to(ROOT)}: invalid run_id {run_id}")
        if run_id in run_ids:
            fail(errors, f"duplicate run id: {run_id}")
        run_ids.add(run_id)
        if run_id not in path.name:
            fail(errors, f"{path.relative_to(ROOT)}: filename must contain {run_id}")
        if data["experiment_id"] not in exp_ids:
            fail(errors, f"{path.relative_to(ROOT)}: unknown experiment_id {data['experiment_id']}")


def main() -> int:
    errors: list[str] = []
    ids = validate_records(errors)
    validate_registry(errors, ids)
    validate_runs(errors)
    if errors:
        print("Research repository validation FAILED:")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"Research repository validation passed ({len(ids)} records).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
