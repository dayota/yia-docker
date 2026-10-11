from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from yia.cli import main
from yia.config import normalize_config
from yia.docker import ComposeGenerator
from yia.docker.runner import resolve_service
from yia.errors import ErrorCode, YiaError
from yia.generators import GenerationContext
from yia.initialization import initialize_project
from yia.project import load_project
from yia.state import YiaState
from yia.updating import update_project
from yia.validation import validate_config


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/yia.v2.schema.json"


def _raw(redis: dict | None = None) -> dict:
    return {
        "version": 2,
        "project": {"name": "redis"},
        "environment": {"domain": "redis.localhost"},
        "services": {"redis": redis if redis is not None else {"version": "7.4"}},
        "applications": {},
    }


@pytest.mark.parametrize("version", ["7", "7.4", "7.4.2-alpine", "8", "10.0"])
def test_redis_accepts_explicit_tags(version):
    validate_config(_raw({"version": version}), SCHEMA)


@pytest.mark.parametrize("redis", [
    {}, {"version": 7}, {"version": "latest"}, {"version": "6.2"},
    {"version": "7.4\n"}, {"version": "7.4", "expose": "true"},
    {"version": "7.4", "persistent": False},
    {"version": "7.4", "password": "forbidden"},
])
def test_redis_rejects_invalid_options(redis):
    with pytest.raises(YiaError) as caught:
        validate_config(_raw(redis), SCHEMA)
    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.exit_code == 2
    assert caught.value.details["validation_errors"]


def test_v1_still_rejects_redis():
    raw = _raw()
    raw["version"] = 1
    with pytest.raises(YiaError):
        validate_config(raw, ROOT / "schemas/yia.schema.json")


def test_redis_defaults_disabled_and_coexistence(tmp_path):
    config = normalize_config(_raw(), project_root=tmp_path)
    assert config.services.redis.version == "7.4"
    assert config.services.redis.expose is False
    assert resolve_service(config, "redis") == "redis"
    assert config.to_dict()["services"]["redis"] == {
        "name": "redis", "enabled": True, "version": "7.4", "expose": False,
    }
    absent = _raw()
    absent["services"] = {}
    assert normalize_config(_raw({"enabled": False}), project_root=tmp_path).canonical_json() == normalize_config(absent, project_root=tmp_path).canonical_json()
    both = _raw()
    both["services"]["postgres"] = {"version": "18"}
    normalized = normalize_config(both, project_root=tmp_path)
    assert normalized.services.redis is not None
    assert normalized.services.postgres is not None


@pytest.mark.parametrize("expose", [False, True])
def test_redis_compose_is_persistent_private_and_secret_free(tmp_path, monkeypatch, expose):
    monkeypatch.setenv("REDIS_PASSWORD", "never-copy-this-password")
    config = normalize_config(_raw({"version": "7.4", "expose": expose}), project_root=tmp_path)
    context = GenerationContext(config=config, state=YiaState.from_config(config))
    first = tuple(ComposeGenerator().generate(context))
    assert first == tuple(ComposeGenerator().generate(context))
    assert b"never-copy-this-password" not in first[0].content
    payload = yaml.safe_load(first[0].content)
    redis = payload["services"]["redis"]
    assert redis["image"] == "redis:7.4"
    assert redis["networks"] == ["yia"]
    assert redis["environment"] == {"REDIS_PASSWORD": "${REDIS_PASSWORD:?REDIS_PASSWORD must be set in .env}"}
    assert redis["volumes"][0] == {"type": "volume", "source": "redis-data", "target": "/data"}
    assert payload["volumes"] == {"redis-data": {}}
    assert "PONG" in redis["healthcheck"]["test"][1]
    assert redis.get("ports", []) == (["127.0.0.1:6379:6379"] if expose else [])


@pytest.mark.parametrize("password", [None, "", "''", '""'])
def test_validate_reports_missing_password_without_writes(tmp_path, monkeypatch, capsys, password):
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    config = tmp_path / "yia.yml"
    config.write_text(yaml.safe_dump(_raw()))
    if password is not None:
        (tmp_path / ".env").write_text(f"REDIS_PASSWORD={password}\n")
    assert main(["validate", "--config", str(config), "--json"]) == 2
    output = capsys.readouterr()
    error = json.loads(output.out)["error"]
    assert error["code"] == "YIA_CONFIG_INVALID"
    assert error["details"]["variable"] == "REDIS_PASSWORD"
    assert not (tmp_path / ".yia-runtime").exists()
    assert output.err == ""


def test_init_update_and_removal_preserve_files(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    config_path = tmp_path / "yia.yml"
    config_path.write_text(yaml.safe_dump(_raw()))
    secret = "local-test-only"
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"REDIS_PASSWORD='{secret}'\n")
    initialized = initialize_project(config_path, yia_root=ROOT)
    assert initialized.services == ("redis",)
    calls = []

    class Compose:
        def converge(self):
            calls.append("converge")

        def force_recreate_services(self, services):
            assert services == ()

        def down(self):
            calls.append("down")

    monkeypatch.setattr("yia.updating.compose_for_project", lambda **kwargs: Compose())
    human = tmp_path / ".agents/docs/domain/human.md"
    human.write_text("keep\n")
    first = update_project(load_project(config_path))
    snapshot = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (tmp_path / ".yia-runtime").rglob("*") if path.is_file()}
    second = update_project(load_project(config_path))
    assert first.services == second.services == ("redis",)
    assert not second.changed
    assert calls == ["converge", "converge"]
    assert snapshot == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in snapshot}
    derived = tmp_path / ".agents/docs/architecture/development-environment.md"
    assert "redis-data" in derived.read_text()
    assert "REDIS_PASSWORD" in derived.read_text()
    assert secret not in derived.read_text()
    for path in (tmp_path / ".yia-runtime").rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
    config_path.write_text(yaml.safe_dump(_raw({"enabled": False})))
    removed = update_project(load_project(config_path))
    assert removed.services == ()
    assert calls == ["converge", "converge", "down"]
    assert removed.compose_applied
    assert not update_project(load_project(config_path)).compose_applied
    assert human.read_text() == "keep\n"
    assert dotenv.read_text() == f"REDIS_PASSWORD='{secret}'\n"


def test_process_environment_takes_precedence(tmp_path, monkeypatch):
    config = tmp_path / "yia.yml"
    config.write_text(yaml.safe_dump(_raw()))
    (tmp_path / ".env").write_text("REDIS_PASSWORD=dotenv-test-only\n")
    monkeypatch.setenv("REDIS_PASSWORD", "")
    with pytest.raises(YiaError):
        load_project(config)
    monkeypatch.setenv("REDIS_PASSWORD", "environment-test-only")
    assert load_project(config).config.services.redis is not None
