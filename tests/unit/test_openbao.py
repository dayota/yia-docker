from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from yia.cli import main
from yia.config import normalize_config
from yia.docker import ComposeGenerator
from yia.docker.runner import resolve_service
from yia.docker.openbao import openbao_status, with_openbao_readiness
from yia.errors import ErrorCode, YiaError
from yia.generators import GenerationContext
from yia.initialization import initialize_project
from yia.project import load_project
from yia.state import YiaState
from yia.updating import update_project
from yia.validation import validate_config


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/yia.v2.schema.json"


def _raw(service=None):
    return {
        "version": 2,
        "project": {"name": "openbao"},
        "environment": {"domain": "openbao.localhost"},
        "services": {"openbao": {"version": "2.5.0"} if service is None else service},
        "applications": {},
    }


@pytest.mark.parametrize("version", ["2", "2.5.0", "2.5.0-alpha", "3.0", "10"])
def test_openbao_accepts_explicit_tags(version):
    validate_config(_raw({"version": version}), SCHEMA)


@pytest.mark.parametrize("service", [
    {}, {"version": 2}, {"version": "latest"}, {"version": "1.0"},
    {"version": "2.5.0\n"}, {"version": "2.5.0", "mode": "dev"},
    {"version": "2.5.0", "expose": True},
    {"version": "2.5.0", "token": "not-allowed"},
])
def test_openbao_rejects_unsupported_options(service):
    with pytest.raises(YiaError) as caught:
        validate_config(_raw(service), SCHEMA)
    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.exit_code == 2


def test_openbao_remains_v2_only():
    raw = _raw()
    raw["version"] = 1
    with pytest.raises(YiaError):
        validate_config(raw, ROOT / "schemas/yia.schema.json")


def test_openbao_normalization_and_independent_services(tmp_path):
    normalized = normalize_config(_raw(), project_root=tmp_path)
    assert normalized.services.openbao.version == "2.5.0"
    assert resolve_service(normalized, "openbao") == "openbao"
    assert normalized.to_dict()["services"]["openbao"] == {
        "name": "openbao", "enabled": True, "version": "2.5.0",
    }
    absent = _raw()
    absent["services"] = {}
    assert normalize_config(_raw({"enabled": False}), project_root=tmp_path).canonical_json() == normalize_config(absent, project_root=tmp_path).canonical_json()
    together = _raw()
    together["services"].update(postgres={"version": "18"}, redis={"version": "7.4"})
    config = normalize_config(together, project_root=tmp_path)
    assert all((config.services.postgres, config.services.redis, config.services.openbao))


def test_openbao_generation_is_private_persistent_and_secret_free(tmp_path, monkeypatch):
    monkeypatch.setenv("BAO_TOKEN", "never-copy-token")
    config = normalize_config(_raw(), project_root=tmp_path)
    context = GenerationContext(config=config, state=YiaState.from_config(config))
    first = tuple(ComposeGenerator().generate(context))
    assert first == tuple(ComposeGenerator().generate(context))
    files = {file.path: file.content for file in first}
    assert set(files) == {"compose/compose.yaml", "openbao/server.hcl"}
    compose = yaml.safe_load(files["compose/compose.yaml"])
    service = compose["services"]["openbao"]
    assert "ports" not in service
    assert "apache" not in compose["services"]
    assert service["image"] == "openbao/openbao:2.5.0"
    assert service["command"] == ["bao", "server", "-config=/yia/openbao/server.hcl"]
    assert service["volumes"][0] == {
        "type": "volume", "source": "openbao-data", "target": "/openbao/file",
    }
    assert service["volumes"][1]["read_only"]
    assert compose["volumes"] == {"openbao-data": {}}
    assert service["networks"] == ["yia"]
    hcl = files["openbao/server.hcl"].decode()
    assert 'storage "raft"' in hcl
    assert 'path = "/openbao/file"' in hcl
    assert "generated" in hcl.lower()
    assert b"never-copy-token" not in b"".join(files.values())
    assert "BAO_TOKEN" not in service["environment"]


class Compose:
    def __init__(self, *, initialized=True, sealed=False, fails=False):
        self.initialized = initialized
        self.sealed = sealed
        self.fails = fails

    def converge(self):
        if self.fails:
            raise YiaError(ErrorCode.DOCKER_UNAVAILABLE, "Docker operation failed")

    def force_recreate_services(self, services):
        assert not services

    def run(self, arguments, **kwargs):
        if any("bao status" in argument for argument in arguments):
            return SimpleNamespace(stdout=json.dumps({
                "initialized": self.initialized, "sealed": self.sealed,
                "unexpected": "must-not-leak",
            }))
        return SimpleNamespace(stdout='{"initialized": true, "sealed": false}')


def _initialized(root):
    (root / ".yia").symlink_to(ROOT, target_is_directory=True)
    config = root / "yia.yml"
    config.write_text(yaml.safe_dump(_raw()))
    result = initialize_project(config, yia_root=ROOT)
    assert result.services == ("openbao",)
    return load_project(config)


@pytest.mark.parametrize(("initialized", "sealed", "state"), [
    (False, True, "uninitialized"), (True, True, "sealed"),
])
def test_update_reports_manual_operation_required(tmp_path, monkeypatch, initialized, sealed, state):
    project = _initialized(tmp_path)
    compose = Compose(initialized=initialized, sealed=sealed, fails=True)
    monkeypatch.setattr("yia.updating.compose_for_project", lambda **kwargs: compose)
    with pytest.raises(YiaError) as caught:
        update_project(project)
    assert caught.value.code is ErrorCode.OPENBAO_NOT_READY
    assert caught.value.exit_code == 5
    assert caught.value.details["state"] == state
    assert caught.value.details["service"] == "openbao"
    assert "must-not-leak" not in str(caught.value.to_dict())
    assert project.compose_path.is_file()


def test_ready_update_is_idempotent_and_protects_human_files(tmp_path, monkeypatch):
    project = _initialized(tmp_path)
    monkeypatch.setattr("yia.updating.compose_for_project", lambda **kwargs: Compose())
    human = tmp_path / ".agents/docs/domain/human.md"
    human.write_text("keep\n")
    first = update_project(project)
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in project.runtime_path.rglob("*") if path.is_file()}
    second = update_project(project)
    assert first.services == second.services == ("openbao",)
    assert not second.changed
    assert before == {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before}
    assert human.read_text() == "keep\n"
    document = tmp_path / ".agents/docs/architecture/development-environment.md"
    assert "openbao-data" in document.read_text()
    assert "openbao:8200" in document.read_text()


def test_validate_does_not_require_a_token(tmp_path, capsys):
    config = tmp_path / "yia.yml"
    config.write_text(yaml.safe_dump(_raw()))
    assert main(["validate", "--config", str(config), "--json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["status"] == "ok"
    assert output.err == ""
    assert not (tmp_path / ".yia-runtime").exists()


@pytest.mark.parametrize("payload", ["not-json", "[]", '{}', '{"initialized": 1, "sealed": false}'])
def test_status_rejects_malformed_responses_without_exposing_them(payload):
    compose = SimpleNamespace(run=lambda *args, **kwargs: SimpleNamespace(stdout=payload))
    assert openbao_status(compose) == {
        "state": "unavailable", "initialized": None, "sealed": None,
    }


def test_ready_status_requires_successful_health_endpoint():
    class Unhealthy(Compose):
        def run(self, arguments, **kwargs):
            if "wget" in arguments:
                raise YiaError(ErrorCode.DOCKER_UNAVAILABLE, "health unavailable")
            return super().run(arguments, **kwargs)
    assert openbao_status(Unhealthy()) == {
        "state": "unavailable", "initialized": True, "sealed": False,
    }


def test_readiness_preserves_unrelated_docker_errors(tmp_path, monkeypatch):
    monkeypatch.setattr("yia.docker.openbao.time.sleep", lambda seconds: None)
    config = normalize_config(_raw(), project_root=tmp_path)
    compose = Compose(fails=True)
    with pytest.raises(YiaError) as caught:
        with_openbao_readiness(config, compose, compose.converge)
    assert caught.value.code is ErrorCode.DOCKER_UNAVAILABLE


def test_readiness_retries_stale_healthcheck_once(tmp_path, monkeypatch):
    monkeypatch.setattr("yia.docker.openbao.time.sleep", lambda seconds: None)
    config = normalize_config(_raw(), project_root=tmp_path)
    calls = []
    def operation():
        calls.append(True)
        if len(calls) == 1:
            raise YiaError(ErrorCode.DOCKER_UNAVAILABLE, "stale healthcheck")
    with_openbao_readiness(config, Compose(), operation)
    assert len(calls) == 2


def test_readiness_checks_even_successful_compose_operation(tmp_path):
    config = normalize_config(_raw(), project_root=tmp_path)
    compose = Compose(sealed=True)
    with pytest.raises(YiaError) as caught:
        with_openbao_readiness(config, compose, compose.converge)
    assert caught.value.code is ErrorCode.OPENBAO_NOT_READY
