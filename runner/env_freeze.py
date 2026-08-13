"""Capture a minimal environment manifest for reproducibility.

Do not include secrets. Keep output small and deterministic where possible.
"""

from __future__ import annotations

import platform
import sys
from typing import Dict, Any


def capture_environment_manifest() -> Dict[str, Any]:
    manifest = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "executable": sys.executable,
        "cwd": None,
        "packages": {},
    }
    return manifest
