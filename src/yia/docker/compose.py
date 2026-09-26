from __future__ import annotations

from typing import Iterable

import yaml

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
)
from .postgres import (
    POSTGRES_CONTAINER_PORT,
    POSTGRES_DATA_VOLUME,
    POSTGRES_SERVICE_NAME,
    postgres_data_path,
    postgres_environment,
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
            "healthcheck": _healthcheck(["CMD", "php-fpm", "-t"]),
        }

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
    if postgres.expose:
        service["ports"] = [
            f"{POSTGRES_CONTAINER_PORT}:{POSTGRES_CONTAINER_PORT}"
        ]
    return service


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

    postgres = _postgres_service(config)
    if postgres is not None:
        services[POSTGRES_SERVICE_NAME] = postgres
        volumes.add(POSTGRES_DATA_VOLUME)

    compose: dict[str, object] = {
        "name": config.project.compose_name,
        "services": dict(sorted(services.items())),
        "networks": {NETWORK_NAME: {}},
    }
    if volumes:
        compose["volumes"] = {name: {} for name in sorted(volumes)}
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
