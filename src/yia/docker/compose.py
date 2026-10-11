from __future__ import annotations

from typing import Iterable

import yaml
from .secrets import PHP_APPLICATIONS_PATH, PHP_BOOTSTRAP, secret_mounts, secret_target

from yia.config import ApplicationConfig, NormalizedConfig
from yia.generators import GeneratedFile, GenerationContext
from yia.versions import YIA_VERSION

from .apache import APACHE_VHOSTS_CONTAINER_PATH, APACHE_VHOSTS_PATH
from .node import (
    NODE_BUILD_CONTEXT,
    NODE_HEALTHCHECK_CONTAINER_PATH,
    node_service_name,
)
from .php import (
    PHP_BUILD_CONTEXT,
    PHP_FPM_BASE_PORT,
    PHP_FPM_CONFIG_CONTAINER_PATH,
    php_applications_by_runtime,
    php_configuration_path,
    duration_seconds,
)
from .python import (
    PYTHON_BUILD_CONTEXT,
    PYTHON_HEALTHCHECK_CONTAINER_PATH,
    python_service_name,
)
from .postgres import (
    POSTGRES_CONTAINER_PORT,
    POSTGRES_DATA_VOLUME,
    POSTGRES_SERVICE_NAME,
    postgres_data_path,
    postgres_environment,
)
from .openbao import (
    OPENBAO_CONFIGURATION,
    OPENBAO_CONFIG_PATH,
    OPENBAO_CONFIG_CONTAINER_PATH,
    OPENBAO_DATA_VOLUME,
    OPENBAO_HEALTH_URL,
)


COMPOSE_PATH = "compose/compose.yaml"
NETWORK_NAME = "yia"
RUNTIME_ROOT = "/workspace"
APACHE_BUILD_CONTEXT = "../../.yia/docker/apache"


def _healthcheck(test: list[str]) -> dict[str, object]:
    return {
        "test": test,
        "interval": "10s",
        "timeout": "5s",
        "retries": 5,
        "start_period": "5s",
    }


def _application_target(application: ApplicationConfig) -> str:
    return f"{RUNTIME_ROOT}/{application.name}"


def _bind_mount(application: ApplicationConfig) -> dict[str, str]:
    return {
        "type": "bind",
        "source": application.path.as_posix(),
        "target": _application_target(application),
    }


def _dependency_mount(
    application: ApplicationConfig,
    *,
    source: str,
    directory: str,
) -> dict[str, str]:
    return {
        "type": "volume",
        "source": source,
        "target": f"{_application_target(application)}/{directory}",
    }


def _php_volume_name(application: ApplicationConfig) -> str:
    return f"php-{application.name}-vendor"


def _node_volume_name(application: ApplicationConfig) -> str:
    return f"node-{application.name}-modules"


def _apache_service(config: NormalizedConfig) -> dict[str, object] | None:
    web_applications = [
        application
        for application in config.applications
        if application.web is not None
    ]
    if not web_applications:
        return None

    dependencies = {
        (
            application.runtime.name
            if application.type == "php"
            else node_service_name(application)
            if application.type == "node"
            else python_service_name(application)
        )
        for application in web_applications
    }
    volumes: list[dict[str, object]] = [
        {
            "type": "bind",
            "source": f"../{APACHE_VHOSTS_PATH}",
            "target": APACHE_VHOSTS_CONTAINER_PATH,
            "read_only": True,
        }
    ]
    volumes.extend(
        {
            **_bind_mount(application),
            "read_only": True,
        }
        for application in web_applications
        if application.type == "php"
    )
    return {
        "image": f"yia/apache:{YIA_VERSION}",
        "build": {
            "context": APACHE_BUILD_CONTEXT,
            "dockerfile": "Dockerfile",
        },
        "ports": ["80:80"],
        "networks": [NETWORK_NAME],
        "volumes": volumes,
        "depends_on": {
            dependency: {"condition": "service_healthy"}
            for dependency in sorted(dependencies)
        },
        "healthcheck": _healthcheck(
            [
                "CMD",
                "wget",
                "-q",
                "-O",
                "/dev/null",
                "http://127.0.0.1/.yia-health",
            ]
        ),
    }


def _php_services(
    config: NormalizedConfig,
) -> tuple[dict[str, dict[str, object]], set[str]]:
    services: dict[str, dict[str, object]] = {}
    volumes: set[str] = set()
    for runtime_name, applications in php_applications_by_runtime(config).items():
        version = applications[0].runtime.version
        mounts: list[dict[str, object]] = [
            {
                "type": "bind",
                "source": f"../{php_configuration_path(version)}",
                "target": PHP_FPM_CONFIG_CONTAINER_PATH,
                "read_only": True,
            }
        ]
        for application in applications:
            volume_name = _php_volume_name(application)
            volumes.add(volume_name)
            mounts.extend(
                [
                    _bind_mount(application),
                    _dependency_mount(
                        application,
                        source=volume_name,
                        directory="vendor",
                    ),
                ]
            )
            mounts.extend(secret_mounts(application.name, application.secret_files))

        has_secrets = any(application.secret_files for application in applications)
        has_processes = any(application.processes for application in applications)
        if has_secrets or has_processes:
            mounts.append({"type": "bind", "source": f"../php/{version}/applications.json",
                           "target": PHP_APPLICATIONS_PATH, "read_only": True})

        services[runtime_name] = {
            "image": f"yia/php:{version}-{YIA_VERSION}",
            "build": {
                "context": PHP_BUILD_CONTEXT,
                "dockerfile": f"{version}/Dockerfile",
            },
            "environment": {
                "YIA_GID": "${YIA_GID:-1000}",
                "YIA_UID": "${YIA_UID:-1000}",
            },
            "extra_hosts": ["host.docker.internal:host-gateway"],
            "expose": [
                str(PHP_FPM_BASE_PORT + index)
                for index in range(len(applications))
            ],
            "volumes": mounts,
            "networks": [NETWORK_NAME],
            "healthcheck": _healthcheck(
                ["CMD", "php", PHP_BOOTSTRAP, "fpm", PHP_APPLICATIONS_PATH, "php-fpm", "-t"]
                if has_secrets else ["CMD", "php-fpm", "-t"]
            ),
        }
        if has_processes:
            service = services[runtime_name]
            service["command"] = ["php", "/usr/local/lib/yia/php-supervisor.php", "run", PHP_APPLICATIONS_PATH]
            service["tmpfs"] = ["/run/yia-php"]
            dependencies = sorted({dependency for app in applications for process in app.processes for dependency in process.depends_on})
            if dependencies:
                service["depends_on"] = {dependency: {"condition": "service_healthy"} for dependency in dependencies}
            grace = max((process.stop_grace_period for app in applications for process in app.processes), key=duration_seconds)
            service["stop_grace_period"] = f"{max(10, duration_seconds(grace)) + 1:g}s"
            service["expose"].extend(str(process.port) for app in applications for process in app.processes if process.port is not None)
            service["healthcheck"] = _healthcheck(["CMD", "php", "/usr/local/lib/yia/php-supervisor.php", "health", PHP_APPLICATIONS_PATH])
            probes = [process.healthcheck for app in applications for process in app.processes if process.healthcheck is not None]
            if probes:
                service["healthcheck"].update(
                    interval=f"{min(10, *(duration_seconds(probe.interval) for probe in probes)):g}s",
                    timeout=f"{sum(duration_seconds(probe.timeout) for probe in probes) + 1:g}s",
                    retries=1,
                    start_period=f"{max(duration_seconds(probe.start_period) for probe in probes):g}s",
                )

    return services, volumes


def _node_services(
    config: NormalizedConfig,
) -> tuple[dict[str, dict[str, object]], set[str]]:
    services: dict[str, dict[str, object]] = {}
    volumes: set[str] = set()

    for application in config.applications:
        if application.type != "node":
            continue

        volume_name = _node_volume_name(application)
        volumes.add(volume_name)
        environment = {
            "YIA_GID": "${YIA_GID:-1000}",
            "YIA_PACKAGE_MANAGER": application.runtime.package_manager,
            "YIA_UID": "${YIA_UID:-1000}",
        }
        service: dict[str, object] = {
            "image": f"yia/node:{application.runtime.version}-{YIA_VERSION}",
            "build": {
                "context": NODE_BUILD_CONTEXT,
                "dockerfile": f"{application.runtime.version}/Dockerfile",
            },
            "environment": environment,
            "working_dir": _application_target(application),
            "volumes": [
                _bind_mount(application),
                _dependency_mount(
                    application,
                    source=volume_name,
                    directory="node_modules",
                ),
            ],
            "networks": [NETWORK_NAME],
            "healthcheck": _healthcheck(
                ["CMD", "node", NODE_HEALTHCHECK_CONTAINER_PATH]
            ),
        }
        if application.web is not None and application.web.port is not None:
            service["expose"] = [str(application.web.port)]
            environment["YIA_NODE_PORT"] = str(application.web.port)
        services[node_service_name(application)] = service

    return services, volumes


def _python_services(
    config: NormalizedConfig,
) -> tuple[dict[str, dict[str, object]], set[str]]:
    services: dict[str, dict[str, object]] = {}
    volumes: set[str] = set()
    for application in config.applications:
        if application.type != "python":
            continue
        if application.web is None or application.web.port is None:
            raise ValueError("Python application requires a web port")
        volume_name = f"python-{application.name}-venv"
        volumes.add(volume_name)
        services[python_service_name(application)] = {
            "image": f"yia/python:{application.runtime.version}-{YIA_VERSION}",
            "build": {
                "context": PYTHON_BUILD_CONTEXT,
                "dockerfile": f"{application.runtime.version}/Dockerfile",
            },
            "environment": {
                "PYTHONDONTWRITEBYTECODE": "1",
                "YIA_GID": "${YIA_GID:-1000}",
                "YIA_PYTHON_PORT": str(application.web.port),
                "YIA_UID": "${YIA_UID:-1000}",
            },
            "working_dir": _application_target(application),
            "volumes": [
                _bind_mount(application),
                _dependency_mount(application, source=volume_name, directory=".venv"),
            ],
            "networks": [NETWORK_NAME],
            "expose": [str(application.web.port)],
            "healthcheck": _healthcheck(
                ["CMD", "python", PYTHON_HEALTHCHECK_CONTAINER_PATH]
            ),
        }
    return services, volumes


def _postgres_service(config: NormalizedConfig) -> dict[str, object] | None:
    postgres = config.services.postgres
    if postgres is None:
        return None

    service: dict[str, object] = {
        "image": f"postgres:{postgres.version}",
        "environment": postgres_environment(),
        "volumes": [
            {
                "type": "volume",
                "source": POSTGRES_DATA_VOLUME,
                "target": postgres_data_path(postgres.version),
            }
        ],
        "networks": [NETWORK_NAME],
        "healthcheck": _healthcheck(
            [
                "CMD-SHELL",
                'pg_isready -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"',
            ]
        ),
    }
    if postgres.secret_files:
        service["environment"].pop("POSTGRES_PASSWORD", None)
        service["environment"]["POSTGRES_PASSWORD_FILE"] = secret_target("postgres", "POSTGRES_PASSWORD")
        service["volumes"].extend(secret_mounts("postgres", postgres.secret_files))
        service["entrypoint"] = ["/bin/sh", "/yia/start.sh"]
        service["command"] = ["postgres"]
        service["volumes"].extend([
            {"type": "bind", "source": "../../.yia/docker/postgres/start.sh",
             "target": "/yia/start.sh", "read_only": True},
            {"type": "bind", "source": "../../.yia/docker/redis/read-secret.sh",
             "target": "/yia/read-secret.sh", "read_only": True},
        ])
    if postgres.init_sql is not None:
        service["volumes"].extend(
            [
                {
                    "type": "bind",
                    "source": postgres.init_sql.as_posix(),
                    "target": "/yia-init/init.sql",
                    "read_only": True,
                },
                {
                    "type": "bind",
                    "source": "../../.yia/docker/postgres/init-sql.sh",
                    "target": "/docker-entrypoint-initdb.d/10-yia.sh",
                    "read_only": True,
                },
            ]
        )
    if postgres.once is not None:
        service["volumes"].append(
            {
                "type": "bind",
                "source": postgres.once.script.as_posix(),
                "target": "/yia-init/once.sh",
                "read_only": True,
            }
        )
    if postgres.expose:
        service["ports"] = [
            f"{POSTGRES_CONTAINER_PORT}:{POSTGRES_CONTAINER_PORT}"
        ]
    return service


def _redis_service(config: NormalizedConfig) -> dict[str, object] | None:
    redis = config.services.redis
    if redis is None:
        return None
    service: dict[str, object] = {
        "image": f"redis:{redis.version}",
        "command": ["sh", "/yia/redis-start.sh"],
        "environment": {
            "REDIS_PASSWORD": "${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}",
        },
        "volumes": [
            {"type": "volume", "source": "redis-data", "target": "/data"},
            {
                "type": "bind",
                "source": "../../.yia/docker/redis/start.sh",
                "target": "/yia/redis-start.sh",
                "read_only": True,
            },
        ],
        "networks": [NETWORK_NAME],
        "healthcheck": _healthcheck([
            "CMD-SHELL",
            'test "$$(REDISCLI_AUTH="$${REDIS_PASSWORD}" redis-cli --raw ping)" = PONG',
        ]),
    }
    if redis.secret_files:
        service["environment"] = {"REDIS_PASSWORD_FILE": secret_target("redis", "REDIS_PASSWORD")}
        service["volumes"].extend(secret_mounts("redis", redis.secret_files))
        service["volumes"].append({
            "type": "bind", "source": "../../.yia/docker/redis/healthcheck.sh",
            "target": "/yia/redis-healthcheck.sh", "read_only": True,
        })
        service["volumes"].append({
            "type": "bind", "source": "../../.yia/docker/redis/read-secret.sh",
            "target": "/yia/read-secret.sh", "read_only": True,
        })
        service["tmpfs"] = ["/tmp"]
        service["healthcheck"] = _healthcheck(["CMD", "sh", "/yia/redis-healthcheck.sh"])
    if redis.expose:
        service["ports"] = ["127.0.0.1:6379:6379"]
    return service


def _openbao_service(config: NormalizedConfig) -> dict[str, object] | None:
    openbao = config.services.openbao
    if openbao is None:
        return None
    healthcheck = _healthcheck(["CMD", "wget", "-q", "-O", "/dev/null", OPENBAO_HEALTH_URL])
    healthcheck.update(interval="2s", retries=3)
    return {
        "image": f"openbao/openbao:{openbao.version}",
        "command": ["bao", "server", f"-config={OPENBAO_CONFIG_CONTAINER_PATH}"],
        "environment": {"BAO_ADDR": "http://127.0.0.1:8200"},
        "networks": [NETWORK_NAME],
        "volumes": [
            {"type": "volume", "source": OPENBAO_DATA_VOLUME, "target": "/openbao/file"},
            {
                "type": "bind", "source": f"../{OPENBAO_CONFIG_PATH}",
                "target": OPENBAO_CONFIG_CONTAINER_PATH, "read_only": True,
            },
        ],
        "tmpfs": ["/openbao/logs"],
        "healthcheck": healthcheck,
    }


def _compose_model(config: NormalizedConfig) -> dict[str, object]:
    services: dict[str, dict[str, object]] = {}
    volumes: set[str] = set()

    apache = _apache_service(config)
    if apache is not None:
        services["apache"] = apache

    php_services, php_volumes = _php_services(config)
    services.update(php_services)
    volumes.update(php_volumes)

    node_services, node_volumes = _node_services(config)
    services.update(node_services)
    volumes.update(node_volumes)

    python_services, python_volumes = _python_services(config)
    services.update(python_services)
    volumes.update(python_volumes)

    postgres = _postgres_service(config)
    if postgres is not None:
        services[POSTGRES_SERVICE_NAME] = postgres
        volumes.add(POSTGRES_DATA_VOLUME)

    redis = _redis_service(config)
    if redis is not None:
        services["redis"] = redis
        volumes.add("redis-data")

    openbao = _openbao_service(config)
    if openbao is not None:
        services["openbao"] = openbao
        volumes.add(OPENBAO_DATA_VOLUME)

    compose: dict[str, object] = {
        "name": config.project.compose_name,
        "services": dict(sorted(services.items())),
        "networks": {NETWORK_NAME: {}},
    }
    if volumes:
        compose["volumes"] = {name: {} for name in sorted(volumes)}
    if config.traefik is not None:
        targets = {target.name: target for target in config.traefik.containers}
        compose["networks"]["traefik"] = {
            "external": True, "name": config.traefik.network,
        }
        for name, service in services.items():
            target = targets.get(name)
            exposed = target is not None and target.expose
            labels = dict(target.labels) if target is not None else {}
            labels["traefik.enable"] = str(exposed).lower()
            if exposed:
                service["networks"].append("traefik")
                labels["traefik.docker.network"] = config.traefik.network
            service["labels"] = dict(sorted(labels.items()))
        if "apache" in services:
            services["apache"].pop("ports", None)
    return compose


def _serialize_compose(compose: dict[str, object]) -> str:
    return yaml.safe_dump(
        compose,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


class ComposeGenerator:
    name = "docker-compose"

    def generate(self, context: GenerationContext) -> Iterable[GeneratedFile]:
        yield GeneratedFile.text(
            COMPOSE_PATH,
            _serialize_compose(_compose_model(context.config)),
        )
        if context.config.services.openbao is not None:
            yield GeneratedFile.text(OPENBAO_CONFIG_PATH, OPENBAO_CONFIGURATION)
