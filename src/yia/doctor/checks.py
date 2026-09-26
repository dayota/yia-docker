from __future__ import annotations

from pathlib import Path
from typing import Any

from yia.documentation import validate_documentation
from yia.docker.runner import project_containers
from yia.errors import YiaError
from yia.project import Project, generation_is_current
from yia.system import installation_checks


def _overall_status(checks: list[dict[str, str]]) -> str:
    if any(check["status"] == "error" for check in checks):
        return "error"
    if any(check["status"] == "warning" for check in checks):
        return "warning"
    return "ok"


def run_checks(
    project: Project | None = None,
    *,
    yia_root: Path | None = None,
) -> dict[str, Any]:
    checks = installation_checks(
        project_root=project.root if project is not None else None,
        yia_root=yia_root,
    )
    if project is None:
        return {"status": _overall_status(checks), "checks": checks}

    checks.append(
        {
            "name": "configuration",
            "status": "ok",
            "details": str(project.config_path),
        }
    )
    try:
        validate_documentation(project.config)
    except YiaError as exc:
        checks.append(
            {
                "name": "documentation",
                "status": "error",
                "details": exc.code.value,
            }
        )
    else:
        checks.append(
            {
                "name": "documentation",
                "status": "ok",
                "details": ".agents/docs",
            }
        )
    current = generation_is_current(project)
    checks.append(
        {
            "name": "generation",
            "status": "ok" if current else "warning",
            "details": "à jour" if current else "absente ou obsolète",
        }
    )

    docker_ready = all(
        check["status"] == "ok"
        for check in checks
        if check["name"] in {"docker", "docker-compose", "docker-daemon"}
    )
    if docker_ready:
        containers = project_containers(project.root, project.config.project.name)
        if not containers:
            checks.append(
                {
                    "name": "containers",
                    "status": "warning",
                    "details": "environnement arrêté",
                }
            )
        else:
            unhealthy = [
                container.service or container.name
                for container in containers
                if container.state != "running"
                or container.health in {"unhealthy", "starting"}
            ]
            checks.append(
                {
                    "name": "containers",
                    "status": "error" if unhealthy else "ok",
                    "details": (
                        ", ".join(unhealthy)
                        if unhealthy
                        else f"{len(containers)} service(s) sain(s)"
                    ),
                }
            )

    return {"status": _overall_status(checks), "checks": checks}
