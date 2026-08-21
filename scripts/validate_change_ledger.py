"""Require CHANGELOG.md / AGENT_HANDOFF.md to be touched for a meaningful change.

Deliberately does not add an ENGINE_CHANGELOG.md layer: the RSH/EXP/OBS/PRT
record system and PRO-### protocol updates already carry the "why" for
research and protocol decisions. This script only closes the narrower gap —
a concise, scannable record of changes to the repository's own
infrastructure — without duplicating that existing system.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LEDGER_DOMAINS: list[tuple[str, list[str]]] = [
    (
        "CHANGELOG.md",
        [
            "runner/*",
            "scripts/*",
            ".github/workflows/*",
            "schemas/*",
        ],
    ),
    (
        "AGENT_HANDOFF.md",
        [
            "scripts/preflight_commit.py",
            "scripts/install_preflight_hook.py",
            ".githooks/pre-commit",
            ".github/workflows/*",
        ],
    ),
]

EXEMPT_TRAILER = re.compile(r"^Ledger-Exempt:\s*(\S+)\s+\S.*$", re.MULTILINE)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def _merge_base() -> str | None:
    base = subprocess.run(
        ["git", "merge-base", "HEAD", "origin/main"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return base.stdout.strip() if base.returncode == 0 else None


def changed_paths() -> set[str]:
    merge_base = _merge_base()
    if merge_base is None:
        return set()
    output = _git("diff", "--name-only", f"{merge_base}..HEAD")
    return {line for line in output.splitlines() if line}


def exempted_ledgers() -> set[str]:
    merge_base = _merge_base()
    if merge_base is None:
        return set()
    log = _git("log", f"{merge_base}..HEAD", "--format=%B")
    return {m.group(1) for m in EXEMPT_TRAILER.finditer(log)}


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def main() -> int:
    diff = changed_paths()
    if not diff:
        print("No branch diff against origin/main found; skipping.")
        return 0

    exempt = exempted_ledgers()
    failures: list[str] = []

    for ledger_file, patterns in LEDGER_DOMAINS:
        sensitive_touched = [p for p in diff if matches_any(p, patterns) and p != ledger_file]
        if not sensitive_touched:
            continue
        if ledger_file in diff or ledger_file in exempt:
            continue
        failures.append(
            f"{ledger_file} was not updated, but this branch touches: {', '.join(sorted(sensitive_touched))}. "
            f"Update {ledger_file}, or add a commit trailer 'Ledger-Exempt: {ledger_file} <reason>'."
        )

    if failures:
        print("Change-ledger check failed:\n")
        print("\n".join(f"  - {f}" for f in failures))
        return 1
    print("Change-ledger check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
