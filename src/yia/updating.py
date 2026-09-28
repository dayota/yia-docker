from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from yia.documentation import (
    DocumentationResult,
    update_documentation,
    validate_documentation,
)
from yia.docker.runner import compose_for_project
from yia.errors import ErrorCode, YiaError
from yia.project import Project, generate_project, generation_is_current
from yia.state import assert_state_compatible, read_state


@dataclass(frozen=True, slots=True)
class UpdateResult:
    project: str
    generation_changed: bool
    changed_paths: tuple[str, ...]
    documentation: DocumentationResult
    compose_applied: bool
    forced_services: tuple[str, ...]
    services: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return self.generation_changed or self.documentation.changed

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "ok",
            "project": self.project,
            "changed": self.changed,
            "generation": {
                "changed": self.generation_changed,
                "changed_paths": list(self.changed_paths),
            },
            "documentation": self.documentation.to_dict(),
            "docker": {
                "applied": self.compose_applied,
                "forced_services": list(self.forced_services),
                "services": list(self.services),
            },
            "persistent_data": "preserved",
        }


def _read_compose(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _compose_name(compose: Mapping[str, Any] | None) -> str | None:
    if compose is None:
        return None
    name = compose.get("name")
    return name if isinstance(name, str) and name else None


def _compose_services(
    compose: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    if compose is None:
        return {}
    raw_services = compose.get("services")
    if not isinstance(raw_services, Mapping):
        return {}
    return {
        str(name): service
        for name, service in raw_services.items()
        if isinstance(name, str) and isinstance(service, Mapping)
    }


def _bind_config_services(changed_paths: tuple[str, ...]) -> set[str]:
    services: set[str] = set()
    if "apache/vhosts.conf" in changed_paths:
        services.add("apache")
    for path in changed_paths:
        parts = Path(path).parts
        if len(parts) == 3 and parts[0] == "php" and parts[2] == "fpm-pools.conf":
            services.add(f"php-{parts[1]}")
    return services


def _forced_services(
    *,
    changed_paths: tuple[str, ...],
    previous_compose: Mapping[str, Any] | None,
    current_compose: Mapping[str, Any],
    previous_compose_existed: bool,
) -> tuple[str, ...]:
    previous_services = _compose_services(previous_compose)
    current_services = _compose_services(current_compose)
    forced: list[str] = []
    for service in sorted(_bind_config_services(changed_paths)):
        if service not in current_services:
            continue
        if previous_compose is None:
            if previous_compose_existed:
                forced.append(service)
            continue
        if previous_services.get(service) == current_services[service]:
            forced.append(service)
    return tuple(forced)


def _assert_project_name_stable(
    project: Project,
    previous_compose: Mapping[str, Any] | None,
) -> None:
    previous_name = _compose_name(previous_compose)
    current_name = project.config.project.compose_name
    if previous_name is None or previous_name == current_name:
        return
    raise YiaError(
        ErrorCode.MIGRATION_REQUIRED,
        "Le nom Docker Compose d'un projet initialisé ne peut pas changer automatiquement.",
        {
            "component": "docker-project-name",
            "current_name": previous_name,
            "requested_name": current_name,
            "suggestion": "Restaurer project.name ou effectuer une migration explicite.",
        },
    )


def update_project(project: Project) -> UpdateResult:
    from yia.sources import synchronize_sources
    from yia.project import validate_project_dependencies

    previous_compose_existed = project.compose_path.is_file()
    previous_compose = _read_compose(project.compose_path)
    _assert_project_name_stable(project, previous_compose)

    state = read_state(project.root)
    if state is not None:
        assert_state_compatible(
            state, configuration_schema_version=project.config.schema_version
        )

    synchronize_sources(project.config)
    validate_project_dependencies(project, allow_missing_managed=False)
    documentation = update_documentation(project.config)
    generation = generate_project(project)
    current_compose = _read_compose(project.compose_path)
    if current_compose is None:
        raise YiaError(
            ErrorCode.GENERATION_FAILED,
            "Le Compose généré par Yia est absent ou invalide après update.",
            {"path": str(project.compose_path)},
        )

    services = tuple(sorted(_compose_services(current_compose)))
    forced_services = _forced_services(
        changed_paths=generation.changed_paths,
        previous_compose=previous_compose,
        current_compose=current_compose,
        previous_compose_existed=previous_compose_existed,
    )

    compose_applied = bool(services)
    if compose_applied:
        from yia.initialization_hooks import run_initialization_hooks

        compose = compose_for_project(
            project_root=project.root,
            project_name=project.config.project.compose_name,
            compose_path=project.compose_path,
            dotenv_path=project.dotenv_path,
        )
        compose.converge()
        compose.force_recreate_services(forced_services)
        run_initialization_hooks(project.config, compose)

    if not generation_is_current(project):
        raise YiaError(
            ErrorCode.GENERATION_FAILED,
            "La génération Yia reste obsolète après update.",
            {"path": str(project.runtime_path)},
        )
    validate_documentation(project.config)

    return UpdateResult(
        project=project.config.project.name,
        generation_changed=generation.changed,
        changed_paths=generation.changed_paths,
        documentation=documentation,
        compose_applied=compose_applied,
        forced_services=forced_services,
        services=services,
    )


__all__ = ["UpdateResult", "update_project"]
