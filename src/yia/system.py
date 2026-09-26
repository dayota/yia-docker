from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from yia.errors import ErrorCode, YiaError


APT_PACKAGES = (
    "docker-compose-v2",
    "docker.io",
    "git",
    "make",
    "python3",
    "python3-venv",
)


def _command_check(
    name: str,
    arguments: Sequence[str],
) -> dict[str, str]:
    executable = shutil.which(name)
    if executable is None:
        return {"name": name, "status": "error", "details": f"{name} introuvable"}
    try:
        result = subprocess.run(
            [executable, *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "name": name,
            "status": "error",
            "details": type(exc).__name__,
        }
    details = (result.stdout or result.stderr).splitlines()
    return {
        "name": name,
        "status": "ok" if result.returncode == 0 else "error",
        "details": details[0] if details else f"exit {result.returncode}",
    }


def installation_checks(
    *,
    project_root: Path | None = None,
    yia_root: Path | None = None,
) -> list[dict[str, str]]:
    checks = [
        {
            "name": "python",
            "status": "ok" if sys.version_info >= (3, 12) else "error",
            "details": sys.version.split()[0],
        },
        _command_check("git", ["--version"]),
        _command_check("make", ["--version"]),
        _command_check("docker", ["--version"]),
    ]

    docker = shutil.which("docker")
    if docker is None:
        checks.extend(
            [
                {
                    "name": "docker-compose",
                    "status": "error",
                    "details": "Docker absent",
                },
                {
                    "name": "docker-daemon",
                    "status": "error",
                    "details": "Docker absent",
                },
            ]
        )
    else:
        checks.append(
            _command_check("docker", ["compose", "version"])
            | {"name": "docker-compose"}
        )
        checks.append(
            _command_check("docker", ["info", "--format", "{{.ServerVersion}}"])
            | {"name": "docker-daemon"}
        )

    if project_root is not None and yia_root is not None:
        resolved_project = project_root.resolve()
        resolved_yia = yia_root.resolve()
        if resolved_project != resolved_yia:
            submodule = resolved_project / ".yia"
            status = (
                "ok"
                if submodule.is_dir() and submodule.resolve() == resolved_yia
                else "error"
            )
            checks.append(
                {
                    "name": "yia-submodule",
                    "status": status,
                    "details": str(submodule),
                }
            )
    return checks


def tool_versions() -> dict[str, str | None]:
    """Return stable version information without contacting the Docker daemon."""
    versions: dict[str, str | None] = {"python": sys.version.split()[0]}
    commands = (
        ("git", "git", ["--version"]),
        ("make", "make", ["--version"]),
        ("docker", "docker", ["--version"]),
        ("docker-compose", "docker", ["compose", "version"]),
    )
    for key, executable, arguments in commands:
        check = _command_check(executable, arguments)
        versions[key] = check["details"] if check["status"] == "ok" else None
    return versions


def install_dependencies() -> None:
    apt_get = shutil.which("apt-get")
    if apt_get is None:
        raise YiaError(
            ErrorCode.DEPENDENCY_MISSING,
            "Yia V1 ne peut installer les dépendances que sur un système APT.",
            {"dependency": "apt-get"},
        )

    prefix: list[str] = []
    if os.geteuid() != 0:
        sudo = shutil.which("sudo")
        if sudo is None:
            raise YiaError(
                ErrorCode.DEPENDENCY_MISSING,
                "L'installation APT nécessite les privilèges root ou sudo.",
                {"dependency": "sudo"},
            )
        prefix = [sudo]

    commands = (
        [*prefix, apt_get, "update"],
        [*prefix, apt_get, "install", "--yes", *APT_PACKAGES],
    )
    for command in commands:
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            raise YiaError(
                ErrorCode.DEPENDENCY_MISSING,
                "L'installation des dépendances système a échoué.",
                {"operation": "apt-install", "exit_code": result.returncode},
            )
