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
    GitSourceConfig,
    NormalizedConfig,
    OnceHookConfig,
    OpenBaoConfig,
    PackageManager,
    PostgresConfig,
    ProjectConfig,
    RedisConfig,
    RuntimeConfig,
    ServicesConfig,
    SourceConfig,
    TraefikConfig,
    TraefikContainerConfig,
    WebConfig,
    ProcessConfig,
    HealthcheckConfig,
    ProxyRouteConfig,
)


def _normalize_secrets(block: Mapping[str, Any], root: Path):
    return tuple(
        (name, (root / path).absolute())
        for name, path in sorted(block.get("secret_files", {}).items())
    )


def _normalize_processes(application, root):
    result = []
    for name, raw in sorted(application.get("processes", {}).items()):
        health = raw.get("healthcheck")
        result.append(ProcessConfig(
            name=name, command=tuple(raw["command"]),
            working_directory=(root / raw.get("working_directory", ".")).resolve(),
            depends_on=tuple(sorted(raw.get("depends_on", []))),
            stop_grace_period=raw["stop_grace_period"], port=raw.get("port"),
            healthcheck=HealthcheckConfig(test=tuple(health["test"]), interval=health["interval"],
                                         timeout=health["timeout"], retries=health["retries"],
                                         start_period=health["start_period"]) if health else None,
        ))
    return tuple(result)


def _normalize_once(
    initialization: object, *, root: Path
) -> OnceHookConfig | None:
    if not isinstance(initialization, Mapping):
        return None
    once = initialization.get("once")
    if not isinstance(once, Mapping):
        return None
    return OnceHookConfig(
        id=str(once["id"]), script=(root / str(once["script"])).resolve()
    )


def _normalize_services(
    config: Mapping[str, Any], project_root: Path
) -> ServicesConfig:
    services = config.get("services", {})
    postgres = services.get("postgres") if isinstance(services, Mapping) else None
    redis = services.get("redis") if isinstance(services, Mapping) else None
    openbao = services.get("openbao") if isinstance(services, Mapping) else None
    openbao_config = (
        OpenBaoConfig(name="openbao", version=str(openbao["version"]))
        if isinstance(openbao, Mapping) and openbao.get("enabled", True)
        else None
    )
    redis_config = (
        RedisConfig(
            name="redis",
            version=str(redis["version"]),
            expose=bool(redis.get("expose", False)),
            secret_files=_normalize_secrets(redis, project_root),
        )
        if isinstance(redis, Mapping) and redis.get("enabled", True)
        else None
    )
    if not isinstance(postgres, Mapping) or not postgres.get("enabled", True):
        return ServicesConfig(postgres=None, redis=redis_config, openbao=openbao_config)

    return ServicesConfig(
        redis=redis_config,
        openbao=openbao_config,
        postgres=PostgresConfig(
            name="postgres",
            version=str(postgres["version"]),
            expose=bool(postgres.get("expose", False)),
            secret_files=_normalize_secrets(postgres, project_root),
            init_sql=(
                (project_root / str(postgres["initialization"]["sql"])).resolve()
                if isinstance(postgres.get("initialization"), Mapping)
                and "sql" in postgres["initialization"]
                else None
            ),
            once=_normalize_once(postgres.get("initialization"), root=project_root),
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
            xdebug=bool(runtime.get("xdebug", False)),
        )

    if application_type == "python":
        version = str(runtime["python"])
        return RuntimeConfig(
            name=f"python-{version}",
            type="python",
            version=version,
            package_manager=None,
            xdebug=None,
        )

    version = str(runtime["node"])
    return RuntimeConfig(
        name=f"node-{version}",
        type="node",
        version=version,
        package_manager=cast(PackageManager, runtime.get("package_manager", "pnpm")),
        xdebug=None,
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
        proxy_routes=tuple(ProxyRouteConfig(
            path=route["path"], process=route["process"], websocket=route["websocket"],
            timeout=route.get("timeout", 60),
        ) for route in sorted(web.get("proxy_routes", []), key=lambda route: route["path"])),
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
        source = application.get("source")
        normalized_source = None
        if isinstance(source, Mapping):
            git = source.get("git")
            normalized_source = SourceConfig(
                type=cast(Any, source["type"]),
                git=(
                    GitSourceConfig(
                        ssh=str(git["ssh"]),
                        branch=str(git["branch"]),
                        version=str(git["version"]),
                    )
                    if isinstance(git, Mapping)
                    else None
                ),
            )
        normalized.append(
            ApplicationConfig(
                name=name,
                type=cast(ApplicationType, application["type"]),
                path=application_path,
                runtime=_normalize_runtime(application),
                framework=_normalize_framework(application),
                web=_normalize_web(application, application_path),
                source=normalized_source,
                secret_files=_normalize_secrets(application, project_root),
                processes=_normalize_processes(application, application_path),
                once=_normalize_once(
                    application.get("initialization"), root=application_path
                ),
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
    traefik = config.get("traefik")

    return NormalizedConfig(
        schema_version=int(config["version"]),
        project_root=resolved_root,
        project=ProjectConfig(
            name=str(project["name"]),
            compose_name=str(project["name"]),
        ),
        environment=EnvironmentConfig(domain=str(environment["domain"])),
        services=_normalize_services(config, resolved_root),
        applications=_normalize_applications(config, resolved_root),
        traefik=(
            TraefikConfig(
                network=str(traefik["network"]),
                containers=tuple(
                    TraefikContainerConfig(
                        name=name,
                        expose=target.get("expose", False),
                        labels=tuple(sorted(target.get("labels", {}).items())),
                    )
                    for name, target in sorted(traefik.get("containers", {}).items())
                ),
            ) if isinstance(traefik, Mapping) else None
        ),
    )


def load_normalized_config(
    config_path: Path,
    schema_path: Path,
) -> NormalizedConfig:
    resolved_config_path = config_path.resolve()
    project_root = resolved_config_path.parent
    config = load_config(resolved_config_path)
    selected_schema = (
        schema_path
        if config.get("version") == 1
        else schema_path.with_name("yia.v2.schema.json")
    )
    validate_config(config, selected_schema, project_root=project_root)
    return normalize_config(config, project_root=project_root)
