from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, cast

from yia.validation import validate_config

from .loader import load_config
from .model import (
    ApplicationConfig,
    ApplicationType,
    EnvironmentConfig,
    FrameworkConfig,
    NormalizedConfig,
    PackageManager,
    PostgresConfig,
    ProjectConfig,
    RuntimeConfig,
    ServicesConfig,
    WebConfig,
)


def _normalize_services(config: Mapping[str, Any]) -> ServicesConfig:
    services = config.get("services", {})
    postgres = services.get("postgres") if isinstance(services, Mapping) else None
    if not isinstance(postgres, Mapping) or not postgres.get("enabled", True):
        return ServicesConfig(postgres=None)

    return ServicesConfig(
        postgres=PostgresConfig(
            name="postgres",
            version=str(postgres["version"]),
            expose=bool(postgres.get("expose", False)),
        )
    )


def _normalize_framework(
    application: Mapping[str, Any],
) -> FrameworkConfig | None:
    framework = application.get("framework")
    if not isinstance(framework, Mapping):
        return None

    version = framework.get("version")
    return FrameworkConfig(
        name=str(framework["name"]),
        version=str(version) if version is not None else None,
    )


def _normalize_runtime(application: Mapping[str, Any]) -> RuntimeConfig:
    application_type = cast(ApplicationType, application["type"])
    runtime = cast(Mapping[str, Any], application["runtime"])

    if application_type == "php":
        version = str(runtime["php"])
        return RuntimeConfig(
            name=f"php-{version}",
            type="php",
            version=version,
            package_manager=None,
        )

    version = str(runtime["node"])
    return RuntimeConfig(
        name=f"node-{version}",
        type="node",
        version=version,
        package_manager=cast(PackageManager, runtime.get("package_manager", "pnpm")),
    )


def _normalize_web(
    application: Mapping[str, Any],
    application_path: Path,
) -> WebConfig | None:
    web = application.get("web")
    if not isinstance(web, Mapping):
        return None

    public_directory = web.get("public_directory")
    return WebConfig(
        hostname=str(web["hostname"]),
        public_directory=(
            (application_path / str(public_directory)).resolve()
            if public_directory is not None
            else None
        ),
        port=int(web["port"]) if "port" in web else None,
    )


def _normalize_applications(
    config: Mapping[str, Any],
    project_root: Path,
) -> tuple[ApplicationConfig, ...]:
    applications = cast(Mapping[str, Mapping[str, Any]], config["applications"])
    normalized: list[ApplicationConfig] = []

    for name in sorted(applications):
        application = applications[name]
        application_path = (project_root / str(application["path"])).resolve()
        normalized.append(
            ApplicationConfig(
                name=name,
                type=cast(ApplicationType, application["type"]),
                path=application_path,
                runtime=_normalize_runtime(application),
                framework=_normalize_framework(application),
                web=_normalize_web(application, application_path),
            )
        )

    return tuple(normalized)


def normalize_config(
    config: Mapping[str, Any],
    *,
    project_root: Path,
) -> NormalizedConfig:
    """Build the deterministic internal model from an already validated config."""

    resolved_root = project_root.resolve()
    project = cast(Mapping[str, Any], config["project"])
    environment = cast(Mapping[str, Any], config["environment"])

    return NormalizedConfig(
        schema_version=int(config["version"]),
        project_root=resolved_root,
        project=ProjectConfig(
            name=str(project["name"]),
            compose_name=str(project["name"]),
        ),
        environment=EnvironmentConfig(domain=str(environment["domain"])),
        services=_normalize_services(config),
        applications=_normalize_applications(config, resolved_root),
    )


def load_normalized_config(
    config_path: Path,
    schema_path: Path,
) -> NormalizedConfig:
    resolved_config_path = config_path.resolve()
    project_root = resolved_config_path.parent
    config = load_config(resolved_config_path)
    validate_config(config, schema_path, project_root=project_root)
    return normalize_config(config, project_root=project_root)
