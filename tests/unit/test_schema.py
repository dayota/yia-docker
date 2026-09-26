from pathlib import Path

import pytest

from yia.config import load_config
from yia.errors import ErrorCode, YiaError
from yia.validation import validate_config


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "yia.schema.json"


@pytest.mark.parametrize(
    "fixture",
    ["minimal", "php-only", "node-only", "php-node", "multi-php", "postgres", "full"],
)
def test_valid_fixtures(fixture: str) -> None:
    project_root = ROOT / "tests" / "projects" / fixture
    config = load_config(project_root / "yia.yml")
    validate_config(config, SCHEMA, project_root=project_root)


def test_invalid_fixture() -> None:
    config = load_config(ROOT / "tests" / "projects" / "invalid" / "yia.yml")
    with pytest.raises(YiaError) as caught:
        validate_config(config, SCHEMA)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.exit_code == 2
    assert caught.value.details["expected_schema_version"] == 1
    assert caught.value.details["validation_errors"]
    assert all(
        {"path", "message", "received", "constraint", "expected"} <= error.keys()
        for error in caught.value.details["validation_errors"]
    )


def test_environment_domain_is_required(tmp_path: Path) -> None:
    path = tmp_path / "yia.yml"
    path.write_text(
        "version: 1\nproject:\n  name: demo\napplications: {}\n",
        encoding="utf-8",
    )
    config = load_config(path)
    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


@pytest.mark.parametrize(
    "domain",
    [
        "Bad.localhost",
        "-bad.localhost",
        "bad-.localhost",
        "bad..localhost",
        "bad localhost",
        "bad.localhost\nLoadModule evil modules/evil.so",
    ],
)
def test_environment_domain_must_be_a_safe_dns_hostname(domain: str) -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": domain},
        "applications": {},
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_application_hostname_rejects_configuration_injection() -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "frontend": {
                "type": "node",
                "path": "apps/frontend",
                "runtime": {"node": "24"},
                "web": {
                    "hostname": "demo.localhost\nProxyRequests On",
                    "port": 3000,
                },
            }
        },
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("path", "apps/api\nInclude evil.conf"),
        ("public_directory", "public\nRequire all granted"),
    ],
)
def test_application_paths_reject_configuration_injection(
    field: str,
    value: str,
) -> None:
    application = {
        "type": "php",
        "path": "apps/api",
        "runtime": {"php": "8.4"},
        "web": {
            "hostname": "api.demo.localhost",
            "public_directory": "public",
        },
    }
    if field == "path":
        application["path"] = value
    else:
        application["web"]["public_directory"] = value
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {"api": application},
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_unknown_property_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "yia.yml"
    path.write_text(
        "version: 1\nproject:\n  name: demo\nenvironment:\n  domain: demo.localhost\napplications: {}\nunknown: true\n",
        encoding="utf-8",
    )
    config = load_config(path)
    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_duplicate_hostnames_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "apps" / "api" / "public").mkdir(parents=True)
    (tmp_path / "apps" / "frontend").mkdir(parents=True)
    path = tmp_path / "yia.yml"
    path.write_text(
        """\
version: 1
project:
  name: demo
environment:
  domain: demo.localhost
applications:
  api:
    type: php
    path: apps/api
    runtime:
      php: "8.4"
    web:
      hostname: demo.localhost
      public_directory: public
  frontend:
    type: node
    path: apps/frontend
    runtime:
      node: "24"
    web:
      hostname: demo.localhost
      port: 3000
""",
        encoding="utf-8",
    )

    with pytest.raises(YiaError) as caught:
        validate_config(load_config(path), SCHEMA, project_root=tmp_path)

    errors = caught.value.details["validation_errors"]
    assert errors == [
        {
            "path": "applications.frontend.web.hostname",
            "message": "hostname already used by application 'api'",
            "received": "demo.localhost",
            "constraint": "unique",
            "expected": "a hostname unique within the project",
        }
    ]


@pytest.mark.parametrize("configured_path", ["missing", "../outside", "/tmp/outside"])
def test_invalid_application_paths_are_rejected(
    tmp_path: Path,
    configured_path: str,
) -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "worker": {
                "type": "php",
                "path": configured_path,
                "runtime": {"php": "8.4"},
            }
        },
    }

    with pytest.raises(YiaError) as caught:
        validate_config(config, SCHEMA, project_root=tmp_path)

    assert caught.value.details["validation_errors"][0]["path"] == (
        "applications.worker.path"
    )


@pytest.mark.parametrize(
    ("application_type", "web"),
    [
        ("php", {"hostname": "demo.localhost"}),
        ("node", {"hostname": "demo.localhost"}),
        ("php", {"hostname": "demo.localhost", "port": 3000}),
        (
            "node",
            {"hostname": "demo.localhost", "public_directory": "public"},
        ),
    ],
)
def test_web_configuration_must_match_application_type(
    application_type: str,
    web: dict[str, object],
) -> None:
    runtime = {"php": "8.4"} if application_type == "php" else {"node": "24"}
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "app": {
                "type": application_type,
                "path": "apps/app",
                "runtime": runtime,
                "web": web,
            }
        },
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_php_runtime_rejects_node_package_manager() -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "api": {
                "type": "php",
                "path": "apps/api",
                "runtime": {"php": "8.4", "package_manager": "pnpm"},
            }
        },
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


@pytest.mark.parametrize(
    ("application_type", "runtime"),
    [
        ("php", {"php": "8.4/cli"}),
        ("node", {"node": "latest"}),
    ],
)
def test_runtime_versions_must_be_docker_compatible(
    application_type: str,
    runtime: dict[str, str],
) -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "app": {
                "type": application_type,
                "path": "apps/app",
                "runtime": runtime,
            }
        },
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_postgres_version_must_be_docker_compatible() -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "services": {"postgres": {"version": "latest"}},
        "applications": {},
    }

    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


@pytest.mark.parametrize("public_directory", ["../public", "/var/www/public"])
def test_php_public_directory_must_stay_inside_application(
    tmp_path: Path,
    public_directory: str,
) -> None:
    (tmp_path / "apps" / "api").mkdir(parents=True)
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "api": {
                "type": "php",
                "path": "apps/api",
                "runtime": {"php": "8.4"},
                "web": {
                    "hostname": "demo.localhost",
                    "public_directory": public_directory,
                },
            }
        },
    }

    with pytest.raises(YiaError) as caught:
        validate_config(config, SCHEMA, project_root=tmp_path)

    assert caught.value.details["validation_errors"][0]["path"] == (
        "applications.api.web.public_directory"
    )


def test_php_public_directory_must_exist(tmp_path: Path) -> None:
    (tmp_path / "apps" / "api").mkdir(parents=True)
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "api": {
                "type": "php",
                "path": "apps/api",
                "runtime": {"php": "8.4"},
                "web": {
                    "hostname": "demo.localhost",
                    "public_directory": "public",
                },
            }
        },
    }

    with pytest.raises(YiaError) as caught:
        validate_config(config, SCHEMA, project_root=tmp_path)

    assert caught.value.details["validation_errors"] == [
        {
            "path": "applications.api.web.public_directory",
            "message": "public directory does not exist",
            "received": "public",
            "constraint": "existing_directory",
            "expected": "an existing directory inside the application",
        }
    ]
