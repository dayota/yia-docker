from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from yia.config import load_normalized_config, normalize_config
from yia.validation import validate_config


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "yia.schema.json"


def _normalize(config: dict[str, object], project_root: Path):
    validate_config(config, SCHEMA, project_root=project_root)
    return normalize_config(config, project_root=project_root)


@pytest.mark.parametrize(
    "fixture",
    ["minimal", "php-only", "node-only", "php-node", "multi-php", "postgres", "full"],
)
def test_all_valid_fixtures_can_be_normalized(fixture: str) -> None:
    project_root = ROOT / "tests" / "projects" / fixture

    config = load_normalized_config(project_root / "yia.yml", SCHEMA)

    assert config.project_root == project_root.resolve()
    assert tuple(app.name for app in config.applications) == tuple(
        sorted(app.name for app in config.applications)
    )


def test_full_configuration_is_normalized() -> None:
    project_root = ROOT / "tests" / "projects" / "full"

    config = load_normalized_config(project_root / "yia.yml", SCHEMA)

    assert config.schema_version == 1
    assert config.project.name == "full"
    assert config.project.compose_name == "full"
    assert config.project_root == project_root.resolve()
    assert config.environment.domain == "full.localhost"

    assert config.services.postgres is not None
    assert config.services.postgres.name == "postgres"
    assert config.services.postgres.version == "18"
    assert config.services.postgres.expose is False

    assert tuple(application.name for application in config.applications) == (
        "api",
        "frontend",
    )

    api = config.application("api")
    assert api.path == (project_root / "apps" / "api").resolve()
    assert api.runtime.name == "php-8.4"
    assert api.runtime.type == "php"
    assert api.runtime.version == "8.4"
    assert api.runtime.package_manager is None
    assert api.framework is not None
    assert api.framework.version == "13"
    assert api.web is not None
    assert api.web.public_directory == (
        project_root / "apps" / "api" / "public"
    ).resolve()
    assert api.web.port is None

    frontend = config.application("frontend")
    assert frontend.runtime.name == "node-24"
    assert frontend.runtime.package_manager == "pnpm"
    assert frontend.web is not None
    assert frontend.web.port == 3000
    assert frontend.web.public_directory is None
    assert config.runtime_names == ("node-24", "php-8.4")


def test_semantically_equivalent_configurations_have_same_model_and_hash(
    tmp_path: Path,
) -> None:
    (tmp_path / "apps" / "api").mkdir(parents=True)
    (tmp_path / "apps" / "frontend").mkdir(parents=True)
    first = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "services": {"postgres": {"version": "18"}},
        "applications": {
            "frontend": {
                "type": "node",
                "path": "./apps/frontend",
                "runtime": {"node": "24"},
                "framework": {"name": "nuxt", "version": 4},
            },
            "api": {
                "type": "php",
                "path": "apps/api",
                "runtime": {"php": "8.4"},
            },
        },
    }
    second = {
        "applications": {
            "api": {
                "runtime": {"php": "8.4"},
                "path": "./apps/api",
                "type": "php",
            },
            "frontend": {
                "framework": {"version": "4", "name": "nuxt"},
                "runtime": {"package_manager": "pnpm", "node": "24"},
                "path": "apps/frontend",
                "type": "node",
            },
        },
        "services": {
            "postgres": {"expose": False, "version": "18", "enabled": True}
        },
        "environment": {"domain": "demo.localhost"},
        "project": {"name": "demo"},
        "version": 1,
    }

    first_model = _normalize(first, tmp_path)
    second_model = _normalize(second, tmp_path)

    assert first_model == second_model
    assert first_model.canonical_json() == second_model.canonical_json()
    assert first_model.configuration_hash == second_model.configuration_hash


def test_absent_and_disabled_postgres_have_same_effective_model(
    tmp_path: Path,
) -> None:
    base = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {},
    }
    disabled = {
        **base,
        "services": {
            "postgres": {
                "enabled": False,
                "version": "18",
                "expose": False,
            }
        },
    }

    assert _normalize(base, tmp_path) == _normalize(disabled, tmp_path)


def test_hash_changes_when_effective_configuration_changes(tmp_path: Path) -> None:
    (tmp_path / "apps" / "frontend").mkdir(parents=True)
    base = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {
            "frontend": {
                "type": "node",
                "path": "apps/frontend",
                "runtime": {"node": "24"},
            }
        },
    }
    changed = {
        **base,
        "applications": {
            "frontend": {
                **base["applications"]["frontend"],  # type: ignore[index]
                "runtime": {"node": "24", "package_manager": "npm"},
            }
        },
    }

    assert _normalize(base, tmp_path).configuration_hash != _normalize(
        changed,
        tmp_path,
    ).configuration_hash


def test_normalized_model_is_immutable(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {},
    }
    model = _normalize(config, tmp_path)

    with pytest.raises(FrozenInstanceError):
        model.schema_version = 2  # type: ignore[misc]


def test_hash_is_repeatable_and_uses_sha256(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {},
    }

    first = _normalize(config, tmp_path)
    second = _normalize(config, tmp_path)

    assert first.configuration_hash == second.configuration_hash
    assert len(first.configuration_hash) == 64
    assert set(first.configuration_hash) <= set("0123456789abcdef")


def test_hash_has_a_stable_reference_vector() -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {},
    }

    model = normalize_config(config, project_root=Path("/workspace/demo"))

    assert model.configuration_hash == (
        "6495c35665eb4c39be01d6f6e68751f69ce3d7e0c19f91fc884ad2b4bb40d57f"
    )


def test_unknown_application_lookup_fails_explicitly(tmp_path: Path) -> None:
    config = {
        "version": 1,
        "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"},
        "applications": {},
    }
    model = _normalize(config, tmp_path)

    with pytest.raises(KeyError, match="unknown"):
        model.application("unknown")
