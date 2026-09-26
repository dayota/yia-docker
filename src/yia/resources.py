from __future__ import annotations

import sysconfig
from pathlib import Path

from yia.errors import ErrorCode, YiaError


def schema_path(filename: str) -> Path:
    candidates = (
        Path(__file__).resolve().parents[2] / "schemas" / filename,
        Path(sysconfig.get_path("data")) / "share" / "yia" / "schemas" / filename,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise YiaError(
        ErrorCode.GENERIC,
        f"Le schéma Yia {filename!r} est introuvable.",
        {"searched_paths": [str(candidate) for candidate in candidates]},
    )
