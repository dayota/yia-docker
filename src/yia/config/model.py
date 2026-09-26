from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


ApplicationType = Literal["php", "node"]
PackageManager = Literal["pnpm", "npm", "yarn"]


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    name: str
    compose_name: str


@dataclass(frozen=True, slots=True)
class EnvironmentConfig:
    domain: str


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    name: str
    version: str
    expose: bool


@dataclass(frozen=True, slots=True)
class ServicesConfig:
    postgres: PostgresConfig | None


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    name: str
    type: ApplicationType
    version: str
    package_manager: PackageManager | None


@dataclass(frozen=True, slots=True)
class FrameworkConfig:
    name: str
    version: str | None


@dataclass(frozen=True, slots=True)
class WebConfig:
    hostname: str
    public_directory: Path | None
    port: int | None


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    name: str
    type: ApplicationType
    path: Path
    runtime: RuntimeConfig
    framework: FrameworkConfig | None
    web: WebConfig | None

    def to_dict(self) -> dict[str, Any]:
        framework = None
        if self.framework is not None:
            framework = {
                "name": self.framework.name,
                "version": self.framework.version,
            }

        web = None
        if self.web is not None:
            web = {
                "hostname": self.web.hostname,
                "public_directory": (
                    str(self.web.public_directory)
                    if self.web.public_directory is not None
                    else None
                ),
                "port": self.web.port,
            }

        return {
            "name": self.name,
            "type": self.type,
            "path": str(self.path),
            "runtime": {
                "name": self.runtime.name,
                "type": self.runtime.type,
                "version": self.runtime.version,
                "package_manager": self.runtime.package_manager,
            },
            "framework": framework,
            "web": web,
        }


@dataclass(frozen=True, slots=True)
class NormalizedConfig:
    schema_version: int
    project_root: Path
    project: ProjectConfig
    environment: EnvironmentConfig
    services: ServicesConfig
    applications: tuple[ApplicationConfig, ...]

    def application(self, name: str) -> ApplicationConfig:
        for application in self.applications:
            if application.name == name:
                return application
        raise KeyError(f"unknown application {name!r}")

    @property
    def runtime_names(self) -> tuple[str, ...]:
        return tuple(sorted({app.runtime.name for app in self.applications}))

    def to_dict(self) -> dict[str, Any]:
        services: dict[str, Any] = {}
        if self.services.postgres is not None:
            services["postgres"] = {
                "name": self.services.postgres.name,
                "enabled": True,
                "version": self.services.postgres.version,
                "expose": self.services.postgres.expose,
            }

        return {
            "schema_version": self.schema_version,
            "project_root": str(self.project_root),
            "project": {
                "name": self.project.name,
                "compose_name": self.project.compose_name,
            },
            "environment": {"domain": self.environment.domain},
            "services": services,
            "applications": {
                application.name: application.to_dict()
                for application in self.applications
            },
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @property
    def configuration_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
