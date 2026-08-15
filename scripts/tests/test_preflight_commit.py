from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import preflight_commit as preflight


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def make_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "123+tester@users.noreply.github.com")
    git(root, "config", "user.name", "Tester")
    (root / "tracked.txt").write_text("base\n", encoding="utf-8")
    git(root, "add", "tracked.txt")
    git(root, "commit", "-m", "initial")
    git(root, "checkout", "-b", "agent/preflight-test")
    return root


def stage_change(root: Path, text: str = "changed\n") -> None:
    (root / "tracked.txt").write_text(text, encoding="utf-8")
    git(root, "add", "tracked.txt")


def test_feature_branch_and_noreply_identity_are_required(tmp_path: Path):
    root = make_repo(tmp_path)

    assert preflight.current_branch(root) == "agent/preflight-test"
    preflight.assert_noreply_identity(root)

    git(root, "checkout", "main")
    with pytest.raises(preflight.PreflightStop) as stopped:
        preflight.current_branch(root)
    assert stopped.value.code == "PROTECTED-BRANCH"


def test_clean_staging_area_rejects_untracked_and_unstaged_files(tmp_path: Path):
    root = make_repo(tmp_path)
    (root / "backup.patch").write_text("not staged\n", encoding="utf-8")

    with pytest.raises(preflight.PreflightStop) as stopped:
        preflight.assert_clean_staging_area(root)
    assert stopped.value.code == "UNTRACKED-FILES"

    (root / "backup.patch").unlink()
    (root / "tracked.txt").write_text("unstaged\n", encoding="utf-8")
    with pytest.raises(preflight.PreflightStop) as stopped:
        preflight.assert_clean_staging_area(root)
    assert stopped.value.code == "UNSTAGED-CHANGES"


def test_marker_is_bound_to_the_exact_staged_diff(tmp_path: Path):
    root = make_repo(tmp_path)
    stage_change(root)
    snapshot = preflight.staged_snapshot(root)
    preflight.write_marker(root, snapshot)

    preflight.verify_marker(root)

    stage_change(root, "different\n")
    with pytest.raises(preflight.PreflightStop) as stopped:
        preflight.verify_marker(root)
    assert stopped.value.code == "PREFLIGHT-MARKER-MISMATCH"


def test_full_preflight_writes_a_marker_only_after_its_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = make_repo(tmp_path)
    stage_change(root)
    monkeypatch.setattr(preflight, "assert_current_with_origin_main", lambda _root: None)
    monkeypatch.setattr(preflight, "run_required_checks", lambda _root: None)

    preflight.run_preflight(root)

    assert preflight.marker_path(root).is_file()
    preflight.verify_marker(root)


def test_marker_contains_no_commit_email_or_absolute_paths(tmp_path: Path):
    root = make_repo(tmp_path)
    stage_change(root)
    preflight.write_marker(root, preflight.staged_snapshot(root))

    marker = json.loads(preflight.marker_path(root).read_text(encoding="utf-8"))
    assert "email" not in marker
    assert marker["staged_files"] == ["tracked.txt"]
    assert str(root) not in json.dumps(marker)
