import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from yia.config import NormalizedConfig, load_normalized_config, normalize_config
from yia.docker import ComposeGenerator
from yia.generators import GenerationContext, GenerationEngine
from yia.state import YiaState


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "yia.schema.json"


def _fixture_config(name: str) -> NormalizedConfig:
    project_root = ROOT / "tests" / "projects" / name
    return load_normalized_config(project_root / "yia.yml", SCHEMA)


def _compose_payload(config: NormalizedConfig) -> tuple[bytes, dict[str, object]]:
    context = GenerationContext(config=config, state=YiaState.from_config(config))
    files = tuple(ComposeGenerator().generate(context))

    assert len(files) == 1
    assert files[0].path == "compose/compose.yaml"
    payload = yaml.safe_load(files[0].content)
    assert isinstance(payload, dict)
    return files[0].content, payload


@pytest.mark.parametrize(
    "fixture",
    [
        "minimal",
        "php-only",
        "php-85",
        "node-only",
        "php-node",
        "multi-php",
        "postgres",
        "full",
        "framework-apis",
    ],
)
def test_applicable_fixtures_generate_deterministic_compose(fixture: str) -> None:
    config = _fixture_config(fixture)

    first_content, first_payload = _compose_payload(config)
    second_content, second_payload = _compose_payload(config)

    assert first_content == second_content
    assert first_payload == second_payload
    assert first_payload["name"] == config.project.compose_name
    assert first_payload["networks"] == {"yia": {}}
    assert "container_name" not in first_content.decode("utf-8")
    for service in first_payload["services"].values():
        assert service["networks"] == ["yia"]
        assert "healthcheck" in service


@pytest.mark.parametrize(
    "fixture",
    [
        "minimal",
        "php-only",
        "php-85",
        "node-only",
        "php-node",
        "multi-php",
        "postgres",
        "full",
        "framework-apis",
    ],
)
def test_applicable_fixtures_are_valid_docker_compose(
    fixture: str,
    tmp_path: Path,
) -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker CLI is not available")

    content, _ = _compose_payload(_fixture_config(fixture))
    compose_path = tmp_path / "compose.yaml"
    compose_path.write_bytes(content)

    result = subprocess.run(
        [
            docker,
            "compose",
            "-f",
            str(compose_path),
            "config",
            "--quiet",
            "--no-interpolate",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


def test_minimal_project_has_only_the_private_network() -> None:
    _, compose = _compose_payload(_fixture_config("minimal"))

    assert compose["services"] == {}
    assert compose["networks"] == {"yia": {}}
    assert "volumes" not in compose


def test_full_topology_contains_expected_services_volumes_and_ports() -> None:
    _, compose = _compose_payload(_fixture_config("full"))

    assert list(compose["services"]) == [
        "apache",
        "node-24-frontend",
        "php-8.4",
        "postgres",
    ]
    assert list(compose["volumes"]) == [
        "node-frontend-modules",
        "php-api-vendor",
        "postgres-data",
    ]

    apache = compose["services"]["apache"]
    assert apache["ports"] == ["80:80"]
    assert apache["depends_on"] == {
        "node-24-frontend": {"condition": "service_healthy"},
        "php-8.4": {"condition": "service_healthy"},
    }

    php = compose["services"]["php-8.4"]
    assert php["image"] == "yia/php:8.4-0.1.0"
    assert php["build"] == {
        "context": "../../.yia/docker/php",
        "dockerfile": "8.4/Dockerfile",
    }
    assert php["environment"] == {
        "YIA_GID": "${YIA_GID:-1000}",
        "YIA_UID": "${YIA_UID:-1000}",
    }
    assert php["extra_hosts"] == ["host.docker.internal:host-gateway"]
    assert php["expose"] == ["9000"]
    assert "user" not in php
    assert php["volumes"][0] == {
        "type": "bind",
        "source": "../php/8.4/fpm-pools.conf",
        "target": "/usr/local/etc/php-fpm.d/yia-pools.conf",
        "read_only": True,
    }
    assert php["volumes"][1]["source"].endswith("/tests/projects/full/apps/api")
    assert php["volumes"][1]["target"] == "/workspace/api"
    assert php["volumes"][2] == {
        "type": "volume",
        "source": "php-api-vendor",
        "target": "/workspace/api/vendor",
    }
    assert "ports" not in php

    node = compose["services"]["node-24-frontend"]
    assert node["image"] == "yia/node:24-0.1.0"
    assert node["build"] == {
        "context": "../../.yia/docker/node",
        "dockerfile": "24/Dockerfile",
    }
    assert node["environment"] == {
        "YIA_GID": "${YIA_GID:-1000}",
        "YIA_NODE_PORT": "3000",
        "YIA_PACKAGE_MANAGER": "pnpm",
        "YIA_UID": "${YIA_UID:-1000}",
    }
    assert "user" not in node
    assert node["expose"] == ["3000"]
    assert "ports" not in node
    assert node["healthcheck"]["test"] == [
        "CMD",
        "node",
        "/usr/local/lib/yia/node-healthcheck.js",
    ]

    postgres = compose["services"]["postgres"]
    assert postgres["image"] == "postgres:18"
    assert postgres["environment"] == {
        "POSTGRES_DB": "${POSTGRES_DB:-postgres}",
        "POSTGRES_PASSWORD": (
            "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}"
        ),
        "POSTGRES_USER": "${POSTGRES_USER:-postgres}",
    }
    assert postgres["healthcheck"]["test"] == [
        "CMD-SHELL",
        'pg_isready -U "$${POSTGRES_USER}" -d "$${POSTGRES_DB}"',
    ]
    assert "ports" not in postgres
    assert postgres["volumes"] == [
        {
            "type": "volume",
            "source": "postgres-data",
            "target": "/var/lib/postgresql",
        }
    ]


def test_framework_api_topology_uses_shared_php_and_private_python() -> None:
    _, compose = _compose_payload(_fixture_config("framework-apis"))
    assert list(compose["services"]) == [
        "apache", "php-8.2", "python-3.12-fastapi",
    ]
    assert list(compose["volumes"]) == [
        "php-laminas-vendor", "php-zend-vendor", "python-fastapi-venv",
    ]
    assert compose["services"]["apache"]["depends_on"] == {
        "php-8.2": {"condition": "service_healthy"},
        "python-3.12-fastapi": {"condition": "service_healthy"},
    }
    python = compose["services"]["python-3.12-fastapi"]
    assert python["expose"] == ["8000"]
    assert "ports" not in python
    assert python["volumes"][1] == {
        "type": "volume",
        "source": "python-fastapi-venv",
        "target": "/workspace/fastapi/.venv",
    }


def test_php_85_compose_uses_pinned_build_private_fpm_and_vendor_volume() -> None:
    _, compose = _compose_payload(_fixture_config("php-85"))
    assert list(compose["services"]) == ["apache", "php-8.5"]
    php = compose["services"]["php-8.5"]
    assert php["image"] == "yia/php:8.5-0.1.0"
    assert php["build"] == {
        "context": "../../.yia/docker/php",
        "dockerfile": "8.5/Dockerfile",
    }
    assert php["expose"] == ["9000"]
    assert "ports" not in php
    assert "php-api-vendor" in compose["volumes"]
    assert compose["services"]["apache"]["depends_on"] == {
        "php-8.5": {"condition": "service_healthy"},
    }


def test_apache_is_generated_only_for_http_applications(tmp_path: Path) -> None:
    (tmp_path / "apps" / "worker").mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "workers"},
            "environment": {"domain": "workers.localhost"},
            "applications": {
                "worker": {
                    "type": "php",
                    "path": "apps/worker",
                    "runtime": {"php": "8.4"},
                }
            },
        },
        project_root=tmp_path,
    )

    _, compose = _compose_payload(config)

    assert list(compose["services"]) == ["php-8.4"]
    assert "apache" not in compose["services"]


def test_php_runtime_is_shared_by_version(tmp_path: Path) -> None:
    for name in ("api", "worker"):
        (tmp_path / "apps" / name).mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "shared-php"},
            "environment": {"domain": "shared-php.localhost"},
            "applications": {
                "worker": {
                    "type": "php",
                    "path": "apps/worker",
                    "runtime": {"php": "8.4"},
                },
                "api": {
                    "type": "php",
                    "path": "apps/api",
                    "runtime": {"php": "8.4"},
                },
            },
        },
        project_root=tmp_path,
    )

    _, compose = _compose_payload(config)

    assert list(compose["services"]) == ["php-8.4"]
    assert list(compose["volumes"]) == ["php-api-vendor", "php-worker-vendor"]
    php = compose["services"]["php-8.4"]
    assert len(php["volumes"]) == 5
    assert php["expose"] == ["9000", "9001"]


def test_node_processes_are_isolated_while_the_image_is_shared(tmp_path: Path) -> None:
    for name in ("admin", "frontend"):
        (tmp_path / "apps" / name).mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "shared-node"},
            "environment": {"domain": "shared-node.localhost"},
            "applications": {
                name: {
                    "type": "node",
                    "path": f"apps/{name}",
                    "runtime": {"node": "24"},
                }
                for name in ("admin", "frontend")
            },
        },
        project_root=tmp_path,
    )

    _, compose = _compose_payload(config)

    assert list(compose["services"]) == ["node-24-admin", "node-24-frontend"]
    assert {
        service["image"] for service in compose["services"].values()
    } == {"yia/node:24-0.1.0"}
    assert list(compose["volumes"]) == [
        "node-admin-modules",
        "node-frontend-modules",
    ]
    for service in compose["services"].values():
        assert service["build"] == {
            "context": "../../.yia/docker/node",
            "dockerfile": "24/Dockerfile",
        }
        assert service["environment"]["YIA_PACKAGE_MANAGER"] == "pnpm"
        assert "YIA_NODE_PORT" not in service["environment"]


def test_node_package_managers_and_ports_are_configured_per_application(
    tmp_path: Path,
) -> None:
    for name in ("admin", "frontend"):
        (tmp_path / "apps" / name).mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "node-managers"},
            "environment": {"domain": "node-managers.localhost"},
            "applications": {
                "admin": {
                    "type": "node",
                    "path": "apps/admin",
                    "runtime": {"node": "22", "package_manager": "npm"},
                    "web": {
                        "hostname": "admin.node-managers.localhost",
                        "port": 3100,
                    },
                },
                "frontend": {
                    "type": "node",
                    "path": "apps/frontend",
                    "runtime": {"node": "24", "package_manager": "yarn"},
                    "web": {
                        "hostname": "node-managers.localhost",
                        "port": 3200,
                    },
                },
            },
        },
        project_root=tmp_path,
    )

    _, compose = _compose_payload(config)

    admin = compose["services"]["node-22-admin"]
    frontend = compose["services"]["node-24-frontend"]
    assert admin["build"]["dockerfile"] == "22/Dockerfile"
    assert admin["environment"]["YIA_PACKAGE_MANAGER"] == "npm"
    assert admin["environment"]["YIA_NODE_PORT"] == "3100"
    assert frontend["build"]["dockerfile"] == "24/Dockerfile"
    assert frontend["environment"]["YIA_PACKAGE_MANAGER"] == "yarn"
    assert frontend["environment"]["YIA_NODE_PORT"] == "3200"


def test_postgres_is_published_only_when_explicitly_exposed(tmp_path: Path) -> None:
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "database"},
            "environment": {"domain": "database.localhost"},
            "services": {
                "postgres": {"enabled": True, "version": "18", "expose": True}
            },
            "applications": {},
        },
        project_root=tmp_path,
    )

    _, compose = _compose_payload(config)

    assert compose["services"]["postgres"]["ports"] == ["5432:5432"]


def test_postgres_password_value_is_never_written_to_compose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSTGRES_PASSWORD", "a-local-secret-value")
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "database"},
            "environment": {"domain": "database.localhost"},
            "services": {"postgres": {"version": "18"}},
            "applications": {},
        },
        project_root=tmp_path,
    )

    content, _ = _compose_payload(config)

    assert b"a-local-secret-value" not in content
    assert b"POSTGRES_PASSWORD must be set in .env" in content


def test_postgres_compose_generator_is_idempotent(tmp_path: Path) -> None:
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "database"},
            "environment": {"domain": "database.localhost"},
            "services": {"postgres": {"version": "18"}},
            "applications": {},
        },
        project_root=tmp_path,
    )
    engine = GenerationEngine([ComposeGenerator()])

    first = engine.generate(config)
    compose_content = (tmp_path / ".yia-runtime/compose/compose.yaml").read_bytes()
    second = engine.generate(config)

    assert first.changed is True
    assert second.changed is False
    assert (
        tmp_path / ".yia-runtime/compose/compose.yaml"
    ).read_bytes() == compose_content
    assert b"postgres-data" in compose_content
    assert second.manifest.generators == ("docker-compose",)
