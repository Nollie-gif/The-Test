#!/usr/bin/env python3
"""Local, non-mutating commit preflight for The-Test.

The command deliberately does *not* call the API driver, create a RUN record,
commit, or push.  It checks the exact staged diff, records a short-lived local
marker in ``.git/``, and lets the versioned pre-commit hook verify that the
same diff is still being committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


MARKER_VERSION = 1
MARKER_MAX_AGE_SECONDS = 15 * 60
ALLOWED_BRANCH_PREFIX = "agent/"
PROTECTED_BRANCHES = {"main", "master"}


class PreflightStop(RuntimeError):
    """A deliberate, actionable refusal to continue the guarded path."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StagedSnapshot:
    branch: str
    head: str
    diff_sha256: str
    files: tuple[str, ...]


def _run(
    root: Path,
    args: Sequence[str],
    *,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=text,
    )


def _git_text(root: Path, *args: str) -> str:
    result = _run(root, args)
    if result.returncode:
        raise PreflightStop("GIT-ERROR", "Git could not inspect the repository safely.")
    assert isinstance(result.stdout, str)
    return result.stdout


def _git_bytes(root: Path, *args: str) -> bytes:
    result = _run(root, args, text=False)
    if result.returncode:
        raise PreflightStop("GIT-ERROR", "Git could not inspect the repository safely.")
    assert isinstance(result.stdout, bytes)
    return result.stdout


def _nul_paths(raw: bytes) -> tuple[str, ...]:
    return tuple(part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part)


def find_repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise PreflightStop("NOT-A-REPOSITORY", "Run this command from inside The-Test.")
    return Path(result.stdout.strip()).resolve()


def current_branch(root: Path) -> str:
    branch = _git_text(root, "branch", "--show-current").strip()
    if not branch:
        raise PreflightStop("DETACHED-HEAD", "Check out a new agent/... branch before committing.")
    if branch in PROTECTED_BRANCHES:
        raise PreflightStop("PROTECTED-BRANCH", "Direct commits to main are not allowed.")
    if not branch.startswith(ALLOWED_BRANCH_PREFIX):
        raise PreflightStop("NON-FEATURE-BRANCH", "Use an agent/... feature branch for this change.")
    return branch


def has_noreply_identity(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized == "noreply@github.com" or normalized.endswith("@users.noreply.github.com")


def assert_noreply_identity(root: Path) -> None:
    result = _run(root, ("config", "--get", "user.email"))
    assert isinstance(result.stdout, str)
    if result.returncode or not has_noreply_identity(result.stdout):
        raise PreflightStop(
            "IDENTITY-NOT-NOREPLY",
            "Git commit identity must use a GitHub no-reply email. The value is intentionally not displayed.",
        )


def _summarize(paths: tuple[str, ...]) -> str:
    shown = ", ".join(paths[:5])
    return shown if len(paths) <= 5 else f"{shown}, … (+{len(paths) - 5})"


def staged_paths(root: Path) -> tuple[str, ...]:
    return _nul_paths(_git_bytes(root, "diff", "--cached", "--name-only", "-z"))


def assert_clean_staging_area(root: Path) -> tuple[str, ...]:
    unstaged = _nul_paths(_git_bytes(root, "diff", "--name-only", "-z"))
    if unstaged:
        raise PreflightStop(
            "UNSTAGED-CHANGES",
            f"Stage or resolve tracked changes first: {_summarize(unstaged)}",
        )

    untracked = _nul_paths(_git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z"))
    if untracked:
        raise PreflightStop(
            "UNTRACKED-FILES",
            f"Decide what to do with untracked files first: {_summarize(untracked)}",
        )

    staged = staged_paths(root)
    if not staged:
        raise PreflightStop("NO-STAGED-CHANGES", "Stage the exact intended files before running preflight.")
    return staged


def assert_staged_diff_is_clean(root: Path) -> None:
    result = _run(root, ("diff", "--cached", "--check"))
    if result.returncode:
        raise PreflightStop("INVALID-STAGED-DIFF", "The staged diff has whitespace errors.")


def assert_current_with_origin_main(root: Path) -> None:
    fetch = _run(root, ("fetch", "--quiet", "origin", "main"))
    if fetch.returncode:
        raise PreflightStop(
            "FRESHNESS-UNKNOWN",
            "Could not verify origin/main. Restore network access and run preflight again.",
        )
    ancestry = _run(root, ("merge-base", "--is-ancestor", "origin/main", "HEAD"))
    if ancestry.returncode:
        raise PreflightStop(
            "BRANCH-STALE",
            "Bring current origin/main into this feature branch before committing.",
        )


def staged_snapshot(root: Path, branch: str | None = None) -> StagedSnapshot:
    resolved_branch = branch or current_branch(root)
    return StagedSnapshot(
        branch=resolved_branch,
        head=_git_text(root, "rev-parse", "HEAD").strip(),
        diff_sha256=hashlib.sha256(
            _git_bytes(root, "diff", "--cached", "--binary", "--no-ext-diff")
        ).hexdigest(),
        files=staged_paths(root),
    )


def _git_dir(root: Path) -> Path:
    raw = Path(_git_text(root, "rev-parse", "--git-dir").strip())
    return raw if raw.is_absolute() else root / raw


def marker_path(root: Path) -> Path:
    return _git_dir(root) / "preflight" / "commit-ready.json"


def preflight_script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def write_marker(root: Path, snapshot: StagedSnapshot) -> None:
    path = marker_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "marker_version": MARKER_VERSION,
        "created_at_epoch": int(time.time()),
        "preflight_script_sha256": preflight_script_sha256(),
        "branch": snapshot.branch,
        "head": snapshot.head,
        "staged_diff_sha256": snapshot.diff_sha256,
        "staged_files": list(snapshot.files),
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def _load_marker(root: Path) -> dict[str, object]:
    path = marker_path(root)
    if not path.is_file():
        raise PreflightStop("PREFLIGHT-MARKER-MISSING", "Run scripts/preflight_commit.py before committing.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PreflightStop("PREFLIGHT-MARKER-INVALID", "The local preflight marker is invalid.") from exc
    if not isinstance(value, dict):
        raise PreflightStop("PREFLIGHT-MARKER-INVALID", "The local preflight marker is invalid.")
    return value


def _same_snapshot(marker: dict[str, object], snapshot: StagedSnapshot) -> bool:
    return (
        marker.get("branch") == snapshot.branch
        and marker.get("head") == snapshot.head
        and marker.get("staged_diff_sha256") == snapshot.diff_sha256
        and marker.get("staged_files") == list(snapshot.files)
    )


def verify_marker(root: Path) -> None:
    branch = current_branch(root)
    assert_noreply_identity(root)
    assert_clean_staging_area(root)
    marker = _load_marker(root)
    if marker.get("marker_version") != MARKER_VERSION:
        raise PreflightStop("PREFLIGHT-MARKER-STALE", "The preflight marker was made by a different guardrail version.")
    if marker.get("preflight_script_sha256") != preflight_script_sha256():
        raise PreflightStop("PREFLIGHT-MARKER-STALE", "The guardrail changed after preflight ran.")
    created_at = marker.get("created_at_epoch")
    if not isinstance(created_at, int) or not 0 <= time.time() - created_at <= MARKER_MAX_AGE_SECONDS:
        raise PreflightStop("PREFLIGHT-MARKER-EXPIRED", "Run preflight again; its approval window is 15 minutes.")
    if not _same_snapshot(marker, staged_snapshot(root, branch)):
        raise PreflightStop("PREFLIGHT-MARKER-MISMATCH", "The branch, HEAD, or staged diff changed after preflight.")


def run_required_checks(root: Path) -> None:
    checks = (
        ("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ("research validation", [sys.executable, "scripts/validate_research_repo.py"]),
        ("fixture validation", [sys.executable, "scripts/validate_runs.py"]),
    )
    for name, command in checks:
        result = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
        if result.returncode:
            raise PreflightStop("CHECK-FAILED", f"{name} failed. Run that check directly for its local diagnostic output.")


def run_preflight(root: Path) -> None:
    branch = current_branch(root)
    assert_noreply_identity(root)
    assert_clean_staging_area(root)
    assert_staged_diff_is_clean(root)
    assert_current_with_origin_main(root)
    before = staged_snapshot(root, branch)
    run_required_checks(root)
    assert_clean_staging_area(root)
    after = staged_snapshot(root, branch)
    if before != after:
        raise PreflightStop("WORKTREE-CHANGED-DURING-CHECKS", "The exact staged scope changed while checks ran.")
    write_marker(root, after)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or verify The-Test's local commit guardrail.")
    parser.add_argument(
        "--verify-marker",
        action="store_true",
        help="Verify the fresh local marker; used only by the pre-commit hook.",
    )
    args = parser.parse_args(argv)
    try:
        root = find_repo_root()
        if args.verify_marker:
            verify_marker(root)
        else:
            run_preflight(root)
    except PreflightStop as exc:
        print(f"STOP-{exc.code}: {exc.message}", file=sys.stderr)
        return 1
    print("COMMIT-READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
