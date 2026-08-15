#!/usr/bin/env python3
"""Install The-Test's versioned local pre-commit guardrail for this clone."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("STOP-NOT-A-REPOSITORY: Run this command from inside The-Test.")
    return Path(result.stdout.strip()).resolve()


def main() -> int:
    try:
        root = repo_root()
        hook = root / ".githooks" / "pre-commit"
        if not hook.is_file():
            raise RuntimeError("STOP-HOOK-MISSING: The versioned pre-commit hook is missing.")
        configured = subprocess.run(
            ["git", "config", "--local", "core.hooksPath", ".githooks"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        if configured.returncode:
            raise RuntimeError("STOP-HOOK-INSTALL-FAILED: Git could not enable the local hook path.")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("HOOK-READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
