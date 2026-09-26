from __future__ import annotations

import shutil
import sys
from typing import Any


def run_checks() -> dict[str, Any]:
    checks = [
        {
            "name": "python",
            "status": "ok" if sys.version_info >= (3, 12) else "error",
            "details": sys.version.split()[0],
        },
        {
            "name": "docker",
            "status": "ok" if shutil.which("docker") else "warning",
            "details": shutil.which("docker") or "docker introuvable",
        },
        {
            "name": "git",
            "status": "ok" if shutil.which("git") else "error",
            "details": shutil.which("git") or "git introuvable",
        },
        {
            "name": "make",
            "status": "ok" if shutil.which("make") else "error",
            "details": shutil.which("make") or "make introuvable",
        },
    ]

    overall = "error" if any(c["status"] == "error" for c in checks) else "ok"
    if overall == "ok" and any(c["status"] == "warning" for c in checks):
        overall = "warning"

    return {"status": overall, "checks": checks}
