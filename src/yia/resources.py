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


def template_path(*parts: str) -> Path:
    relative_path = Path(*parts)
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le chemin du template Yia est invalide.",
            {"path": relative_path.as_posix()},
        )

    candidates = (
        Path(__file__).resolve().parents[2] / "templates" / relative_path,
        Path(sysconfig.get_path("data"))
        / "share"
        / "yia"
        / "templates"
        / relative_path,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise YiaError(
        ErrorCode.GENERIC,
        f"Le template Yia {relative_path.as_posix()!r} est introuvable.",
        {"searched_paths": [str(candidate) for candidate in candidates]},
    )
