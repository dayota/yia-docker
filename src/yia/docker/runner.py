from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from yia.config import NormalizedConfig
from yia.errors import ErrorCode, YiaError

from .node import node_service_name


@dataclass(frozen=True, slots=True)
class ContainerStatus:
    name: str
    service: str
    state: str
    health: str | None
    status: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "name": self.name,
            "service": self.service,
            "state": self.state,
            "health": self.health,
            "status": self.status,
        }


def _docker_path() -> str:
    docker = shutil.which("docker")
    if docker is None:
        raise YiaError(
            ErrorCode.DEPENDENCY_MISSING,
            "La commande Docker est introuvable.",
            {"dependency": "docker"},
        )
    return docker


def _run(
    arguments: Sequence[str],
    *,
    cwd: Path,
    capture_output: bool = False,
    input_text: str | None = None,
    operation: str,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(arguments),
            cwd=cwd,
            check=False,
            capture_output=capture_output,
            text=True,
            input=input_text,
        )
    except OSError as exc:
        raise YiaError(
            ErrorCode.DOCKER_UNAVAILABLE,
            "Docker ne peut pas être exécuté.",
            {"operation": operation, "error_type": type(exc).__name__},
        ) from exc

    if result.returncode != 0:
        raise YiaError(
            ErrorCode.DOCKER_UNAVAILABLE,
            "Une opération Docker a échoué.",
            {"operation": operation, "exit_code": result.returncode},
        )
    return result


def check_docker_access(project_root: Path) -> None:
    docker = _docker_path()
    _run(
        [docker, "compose", "version"],
        cwd=project_root,
        capture_output=True,
        operation="compose-version",
    )
    _run(
        [docker, "info", "--format", "{{.ServerVersion}}"],
        cwd=project_root,
        capture_output=True,
        operation="docker-info",
    )


class DockerCompose:
    def __init__(
        self,
        *,
        project_root: Path,
        project_name: str,
        compose_path: Path,
        dotenv_path: Path,
    ) -> None:
        self.project_root = project_root
        self.project_name = project_name
        self.compose_path = compose_path
        self.dotenv_path = dotenv_path

    def _base_command(self) -> list[str]:
        command = [
            _docker_path(),
            "compose",
            "--project-name",
            self.project_name,
            "--project-directory",
            str(self.project_root),
        ]
        if self.dotenv_path.is_file():
            command.extend(["--env-file", str(self.dotenv_path)])
        command.extend(["--file", str(self.compose_path)])
        return command

    def run(
        self,
        arguments: Sequence[str],
        *,
        capture_output: bool = False,
        operation: str,
    ) -> subprocess.CompletedProcess[str]:
        return _run(
            [*self._base_command(), *arguments],
            cwd=self.project_root,
            capture_output=capture_output,
            operation=operation,
        )

    def up(self) -> None:
        self.run(
            ["up", "--detach", "--wait", "--remove-orphans"],
            operation="compose-up",
        )

    def down(self) -> None:
        self.run(["down", "--remove-orphans"], operation="compose-down")

    def restart(self) -> None:
        self.run(["stop"], operation="compose-stop")
        self.run(["up", "--detach", "--wait"], operation="compose-restart")

    def build(self, *, no_cache: bool = False) -> None:
        arguments = ["build"]
        if no_cache:
            arguments.append("--no-cache")
        self.run(arguments, operation="compose-build")

    def recreate(self) -> None:
        self.run(
            ["up", "--detach", "--wait", "--force-recreate", "--remove-orphans"],
            operation="compose-recreate",
        )

    def logs(self, service: str | None, *, follow: bool) -> None:
        arguments = ["logs", "--no-color"]
        if follow:
            arguments.append("--follow")
        if service is not None:
            arguments.append(service)
        self.run(arguments, operation="compose-logs")

    def shell(self, service: str) -> None:
        self.run(["exec", service, "/bin/sh"], operation="compose-shell")

    def execute(self, service: str, command: Sequence[str]) -> None:
        self.run(["exec", service, *command], operation="compose-exec")


def compose_for_project(
    *,
    project_root: Path,
    project_name: str,
    compose_path: Path,
    dotenv_path: Path,
) -> DockerCompose:
    return DockerCompose(
        project_root=project_root,
        project_name=project_name,
        compose_path=compose_path,
        dotenv_path=dotenv_path,
    )


def resolve_service(config: NormalizedConfig, requested: str) -> str:
    aliases: dict[str, set[str]] = {}

    def add(alias: str, service: str) -> None:
        aliases.setdefault(alias, set()).add(service)

    if any(application.web is not None for application in config.applications):
        add("apache", "apache")
    if config.services.postgres is not None:
        add("postgres", "postgres")

    for application in config.applications:
        if application.type == "php":
            service = application.runtime.name
        else:
            service = node_service_name(application)
        add(service, service)
        add(application.name, service)
        add(application.runtime.name, service)

    matches = sorted(aliases.get(requested, set()))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le nom de service Yia est ambigu.",
            {"service": requested, "matches": matches},
        )
    raise YiaError(
        ErrorCode.GENERIC,
        "Le service Yia demandé est inconnu.",
        {"service": requested, "available": sorted(aliases)},
    )


def _parse_json_lines(output: str) -> Iterable[dict[str, Any]]:
    for line in output.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise YiaError(
                ErrorCode.DOCKER_UNAVAILABLE,
                "Docker a retourné un état de containers illisible.",
                {"operation": "docker-ps", "error_type": type(exc).__name__},
            ) from exc
        if isinstance(payload, dict):
            yield payload


def project_containers(
    project_root: Path,
    project_name: str,
) -> tuple[ContainerStatus, ...]:
    docker = _docker_path()
    result = _run(
        [
            docker,
            "ps",
            "--all",
            "--filter",
            f"label=com.docker.compose.project={project_name}",
            "--format",
            "json",
        ],
        cwd=project_root,
        capture_output=True,
        operation="docker-ps",
    )
    containers: list[ContainerStatus] = []
    for item in _parse_json_lines(result.stdout):
        labels = {
            part.partition("=")[0]: part.partition("=")[2]
            for part in str(item.get("Labels", "")).split(",")
            if "=" in part
        }
        health = str(item.get("HealthStatus", "")).strip() or None
        if health is None:
            status = str(item.get("Status", ""))
            for candidate in ("healthy", "unhealthy", "starting"):
                if f"({candidate})" in status:
                    health = candidate
                    break
        containers.append(
            ContainerStatus(
                name=str(item.get("Names", "")),
                service=labels.get("com.docker.compose.service", ""),
                state=str(item.get("State", "unknown")).lower(),
                health=health,
                status=str(item.get("Status", "")),
            )
        )
    return tuple(sorted(containers, key=lambda item: (item.service, item.name)))


def project_volumes(project_root: Path, project_name: str) -> tuple[str, ...]:
    docker = _docker_path()
    result = _run(
        [
            docker,
            "volume",
            "ls",
            "--filter",
            f"label=com.docker.compose.project={project_name}",
            "--format",
            "{{.Name}}",
        ],
        cwd=project_root,
        capture_output=True,
        operation="docker-volume-list",
    )
    return tuple(sorted(line for line in result.stdout.splitlines() if line))


def _project_resource_names(
    project_root: Path,
    project_name: str,
    resource: str,
) -> tuple[str, ...]:
    docker = _docker_path()
    result = _run(
        [
            docker,
            resource,
            "ls",
            "--filter",
            f"label=com.docker.compose.project={project_name}",
            "--format",
            "{{.Name}}",
        ],
        cwd=project_root,
        capture_output=True,
        operation=f"docker-{resource}-list",
    )
    return tuple(sorted(line for line in result.stdout.splitlines() if line))


def project_container_names(
    project_root: Path,
    project_name: str,
) -> tuple[str, ...]:
    docker = _docker_path()
    result = _run(
        [
            docker,
            "ps",
            "--all",
            "--filter",
            f"label=com.docker.compose.project={project_name}",
            "--format",
            "{{.Names}}",
        ],
        cwd=project_root,
        capture_output=True,
        operation="docker-container-list",
    )
    return tuple(sorted(line for line in result.stdout.splitlines() if line))


def project_networks(project_root: Path, project_name: str) -> tuple[str, ...]:
    return _project_resource_names(project_root, project_name, "network")


def remove_project_environment(project_root: Path, project_name: str) -> None:
    docker = _docker_path()
    containers = project_container_names(project_root, project_name)
    if containers:
        _run(
            [docker, "rm", "--force", *containers],
            cwd=project_root,
            operation="docker-container-remove",
        )
    networks = project_networks(project_root, project_name)
    if networks:
        _run(
            [docker, "network", "rm", *networks],
            cwd=project_root,
            operation="docker-network-remove",
        )


def down_project_environment(project_root: Path, project_name: str) -> None:
    docker = _docker_path()
    containers = project_container_names(project_root, project_name)
    if containers:
        _run(
            [docker, "stop", *containers],
            cwd=project_root,
            operation="docker-container-stop",
        )
        _run(
            [docker, "rm", *containers],
            cwd=project_root,
            operation="docker-container-remove",
        )
    networks = project_networks(project_root, project_name)
    if networks:
        _run(
            [docker, "network", "rm", *networks],
            cwd=project_root,
            operation="docker-network-remove",
        )


def remove_project_volumes(
    project_root: Path,
    volumes: Sequence[str],
) -> None:
    if not volumes:
        return
    docker = _docker_path()
    _run(
        [docker, "volume", "rm", *volumes],
        cwd=project_root,
        operation="docker-volume-remove",
    )
