"""Require CHANGELOG.md / AGENT_HANDOFF.md to be touched for a meaningful change.

Deliberately does not add an ENGINE_CHANGELOG.md layer: the RSH/EXP/OBS/PRT
record system and PRO-### protocol updates already carry the "why" for
research and protocol decisions. This script only closes the narrower gap —
a concise, scannable record of changes to the repository's own
infrastructure — without duplicating that existing system.

Enforced from 2026-08-21 forward. Earlier history was not backfilled with
reconstructed entries — see CHANGELOG.md for that boundary.

Self-defense notes (found by adversarial review of the same mechanism in
Campaign-Simulation, then verified here too, not assumed to transfer):
- CI runs this file from a copy fetched from `origin/main`, not from the
  pull request's own branch, so a PR cannot silently weaken this script
  and have the weakened copy grade its own diff as clean. Proven
  insufficient on its own: a PR can still legitimately *exempt* the
  resulting requirement with a trailer and merge its neutered file
  content anyway, which then becomes the trusted copy for every future
  PR. `check_committed_ledger_script_is_sane()` closes that specific gap
  by independently inspecting the PR's own committed version of this file
  (via `git show`, parsed with `ast`, never executed) against this
  trusted script's own `MINIMUM_DOMAIN_COUNT` — not waivable by any
  trailer.
- `check_pattern_coverage()` fails loudly if any domain pattern currently
  matches zero tracked files — the signal a rename/move has silently
  orphaned a pattern instead of quietly stopping protecting the thing it
  was meant to protect.
- None of this stops an already-trusted committer from weakening `main`'s
  copy across two separately-merged PRs. That boundary is branch
  protection and human review, not this script.
"""

from __future__ import annotations

import ast
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
        ],
    ),
]

MINIMUM_DOMAIN_COUNT = 2  # CHANGELOG.md, AGENT_HANDOFF.md
SELF_PATH = "scripts/validate_change_ledger.py"

EXEMPT_TRAILER = re.compile(r"^Ledger-Exempt:\s*(\S+)\s+\S.*$", re.MULTILINE)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    )
    return result.stdout


def tracked_files() -> list[str]:
    return [line for line in _git("ls-files").splitlines() if line]


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
    return {line for line in _git("diff", "--name-only", f"{merge_base}..HEAD").splitlines() if line}


def exempted_ledgers() -> set[str]:
    merge_base = _merge_base()
    if merge_base is None:
        return set()
    log = _git("log", f"{merge_base}..HEAD", "--format=%B")
    return {m.group(1) for m in EXEMPT_TRAILER.finditer(log)}


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def check_pattern_coverage(all_files: list[str]) -> list[str]:
    orphaned: list[str] = []
    for ledger_file, patterns in LEDGER_DOMAINS:
        for pattern in patterns:
            if not any(fnmatch.fnmatch(f, pattern) for f in all_files):
                orphaned.append(f"{ledger_file}: pattern '{pattern}' matches no tracked file")
    return orphaned


def assert_domains_sane() -> list[str]:
    problems: list[str] = []
    if len(LEDGER_DOMAINS) < MINIMUM_DOMAIN_COUNT:
        problems.append(
            f"LEDGER_DOMAINS has only {len(LEDGER_DOMAINS)} entries; expected at least {MINIMUM_DOMAIN_COUNT}."
        )
    for ledger_file, patterns in LEDGER_DOMAINS:
        if not patterns:
            problems.append(f"{ledger_file} has zero domain patterns.")
    return problems


def _count_ledger_domains_in_source(source: str) -> int | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        target_matches = False
        value = None
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "LEDGER_DOMAINS" for t in node.targets
        ):
            target_matches = True
            value = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "LEDGER_DOMAINS"
        ):
            target_matches = True
            value = node.value
        if target_matches:
            if isinstance(value, ast.List):
                return len(value.elts)
            return None
    return None


def check_committed_ledger_script_is_sane(diff: set[str]) -> list[str]:
    if SELF_PATH not in diff:
        return []
    result = subprocess.run(
        ["git", "show", f"HEAD:{SELF_PATH}"], cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return [f"{SELF_PATH} is in the diff but could not be read from HEAD for inspection."]
    count = _count_ledger_domains_in_source(result.stdout)
    if count is None:
        return [
            f"{SELF_PATH}'s proposed content has no statically-parseable LEDGER_DOMAINS list. "
            "Could be a syntax error or a deliberate restructure to hide from this check."
        ]
    if count < MINIMUM_DOMAIN_COUNT:
        return [
            f"{SELF_PATH}'s proposed content would leave LEDGER_DOMAINS with only {count} entries "
            f"(expected at least {MINIMUM_DOMAIN_COUNT}). This cannot be waived by a Ledger-Exempt: "
            "trailer — raise a human decision instead."
        ]
    return []


def main() -> int:
    sanity_problems = assert_domains_sane()
    if sanity_problems:
        print("Change-ledger check failed — the checker's own domains are not sane:\n")
        print("\n".join(f"  - {p}" for p in sanity_problems))
        return 1

    all_files = tracked_files()
    orphaned = check_pattern_coverage(all_files)
    if orphaned:
        print("Change-ledger check failed — a domain pattern is orphaned (likely a rename/move):\n")
        print("\n".join(f"  - {o}" for o in orphaned))
        return 1

    diff = changed_paths()
    if not diff:
        print("No branch diff against origin/main found; skipping.")
        return 0

    self_problems = check_committed_ledger_script_is_sane(diff)
    if self_problems:
        print("Change-ledger check failed — the proposed change to this checker is not sane:\n")
        print("\n".join(f"  - {p}" for p in self_problems))
        return 1

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
