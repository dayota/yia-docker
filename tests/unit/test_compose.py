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
        "node-only",
        "php-node",
        "multi-php",
        "postgres",
        "full",
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
        "node-only",
        "php-node",
        "multi-php",
        "postgres",
        "full",
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
    assert node["expose"] == ["3000"]
    assert "ports" not in node

    postgres = compose["services"]["postgres"]
    assert postgres["image"] == "postgres:18"
    assert "ports" not in postgres
    assert postgres["volumes"] == [
        {
            "type": "volume",
            "source": "postgres-data",
            "target": "/var/lib/postgresql",
        }
    ]


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


@pytest.mark.parametrize(
    ("version", "target"),
    [
        ("17", "/var/lib/postgresql/data"),
        ("18", "/var/lib/postgresql"),
        ("18.1-alpine", "/var/lib/postgresql"),
    ],
)
def test_postgres_volume_target_follows_official_image_layout(
    tmp_path: Path,
    version: str,
    target: str,
) -> None:
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "database"},
            "environment": {"domain": "database.localhost"},
            "services": {"postgres": {"version": version}},
            "applications": {},
        },
        project_root=tmp_path,
    )

    _, compose = _compose_payload(config)

    assert compose["services"]["postgres"]["volumes"][0]["target"] == target


def test_compose_generator_integrates_with_idempotent_engine(tmp_path: Path) -> None:
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "minimal"},
            "environment": {"domain": "minimal.localhost"},
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
    assert second.manifest.generators == ("docker-compose",)
