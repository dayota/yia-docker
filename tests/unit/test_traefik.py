from pathlib import Path
import json

import pytest
import yaml

from yia.config import normalize_config
from yia.docker import ComposeGenerator
from yia.errors import YiaError
from yia.generators import GenerationContext
from yia.state import YiaState
from yia.validation import validate_config
from yia.initialization import initialize_project
from yia.project import load_project
from yia.doctor import run_checks

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/yia.v2.schema.json"


def raw():
    return {
        "version": 2, "project": {"name": "demo"},
        "environment": {"domain": "demo.localhost"}, "applications": {},
        "services": {"redis": {"version": "7.4"}, "openbao": {"version": "2.5.0"}},
        "traefik": {"network": "proxy", "containers": {
            "openbao": {"expose": True, "labels": {
                "traefik.http.routers.demo-bao.rule": "Host(`bao.demo.localhost`)",
                "traefik.http.services.demo-bao.loadbalancer.server.port": "8200",
            }},
        }},
    }


def generated(config, root):
    model = normalize_config(config, project_root=root)
    context = GenerationContext(config=model, state=YiaState.from_config(model))
    files = {file.path: file.content for file in ComposeGenerator().generate(context)}
    return yaml.safe_load(files["compose/compose.yaml"])


def test_explicit_infrastructure_exposure_preserves_private_services(tmp_path):
    config = raw()
    validate_config(config, SCHEMA)
    compose = generated(config, tmp_path)
    assert "traefik" not in compose["services"]
    assert compose["networks"]["traefik"] == {"external": True, "name": "proxy"}
    bao = compose["services"]["openbao"]
    assert bao["networks"] == ["yia", "traefik"]
    assert bao["labels"]["traefik.enable"] == "true"
    assert bao["labels"]["traefik.docker.network"] == "proxy"
    assert "ports" not in bao
    redis = compose["services"]["redis"]
    assert redis["networks"] == ["yia"]
    assert redis["labels"] == {"traefik.enable": "false"}


@pytest.mark.parametrize("change", [
    lambda c: c["traefik"].update(network="demo_yia"),
    lambda c: c["traefik"].update(network="${NETWORK}"),
    lambda c: c["traefik"]["containers"].update(missing={}),
    lambda c: c["traefik"]["containers"]["openbao"].update(expose=False),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.enable": "false"}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.docker.network": "other"}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"com.docker.compose.project": "other"}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.foo": True}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.foo": "${SECRET}"}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.foo": "line\nsecret"}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.http.middlewares.auth.basicauth.users": "secret-sensitive-value"}),
    lambda c: c["traefik"]["containers"]["openbao"]["labels"].update({"traefik.http.middlewares.auth.headers.customrequestheaders.authorization": "secret-sensitive-value"}),
])
def test_invalid_traefik_contract_is_rejected(change):
    config = raw()
    change(config)
    with pytest.raises(YiaError) as caught:
        validate_config(config, SCHEMA)
    assert caught.value.exit_code == 2
    assert "secret-sensitive-value" not in json.dumps(caught.value.to_dict())
    assert "${SECRET}" not in json.dumps(caught.value.to_dict())


def test_absence_preserves_canonical_model_and_compose(tmp_path):
    config = raw()
    del config["traefik"]
    model = normalize_config(config, project_root=tmp_path)
    assert "traefik" not in model.to_dict()
    compose = generated(config, tmp_path)
    assert compose["networks"] == {"yia": {}}
    assert all("labels" not in service for service in compose["services"].values())


def web_raw():
    config = raw()
    config["applications"] = {"api": {
        "type": "python", "source": {"type": "linked"}, "path": "../api",
        "runtime": {"python": "3.12"}, "framework": {"name": "fastapi", "version": "1"},
        "web": {"hostname": "demo.localhost", "port": 8000},
    }}
    config["traefik"]["containers"]["apache"] = {"expose": True, "labels": {
        "traefik.http.routers.demo.rule": "Host(`demo.localhost`)",
        "traefik.http.services.demo.loadbalancer.server.port": "80",
    }}
    return config


def test_web_applications_still_route_through_apache(tmp_path):
    config = web_raw()
    validate_config(config, SCHEMA)
    compose = generated(config, tmp_path)
    assert "ports" not in compose["services"]["apache"]
    assert compose["services"]["apache"]["networks"] == ["yia", "traefik"]
    assert compose["services"]["python-3.12-api"]["labels"]["traefik.enable"] == "false"
    config["traefik"]["containers"]["python-3.12-api"] = {"expose": True}
    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_web_requires_explicit_apache_exposure():
    config = web_raw()
    del config["traefik"]["containers"]["apache"]
    with pytest.raises(YiaError):
        validate_config(config, SCHEMA)


def test_v1_rejects_traefik():
    config = raw()
    config["version"] = 1
    with pytest.raises(YiaError):
        validate_config(config, ROOT / "schemas/yia.schema.json")


def test_all_services_accept_disabled_labels_without_joining_shared_network(tmp_path):
    config = web_raw()
    config["applications"]["worker"] = {
        "type": "php", "source": {"type": "linked"}, "path": "../worker",
        "runtime": {"php": "8.4"},
    }
    config["traefik"]["containers"].update({
        "php-8.4": {"labels": {"traefik.enable": "false"}},
        "python-3.12-api": {"labels": {"traefik.enable": "false"}},
        "redis": {"labels": {"traefik.enable": "false"}},
    })
    validate_config(config, SCHEMA)
    compose = generated(config, tmp_path)
    assert all(compose["services"][name]["networks"] == ["yia"]
               for name in ("php-8.4", "python-3.12-api", "redis"))


def test_normalization_and_generation_are_deterministic(tmp_path):
    first = raw()
    second = raw()
    labels = second["traefik"]["containers"]["openbao"]["labels"]
    second["traefik"]["containers"]["openbao"]["labels"] = dict(reversed(list(labels.items())))
    assert normalize_config(first, project_root=tmp_path).canonical_json() == normalize_config(second, project_root=tmp_path).canonical_json()
    assert generated(first, tmp_path) == generated(second, tmp_path)


def test_derived_documentation_describes_exposure_without_copying_labels(tmp_path):
    from yia.documentation.manager import render_development_environment
    config = web_raw()
    config["traefik"]["containers"]["openbao"]["labels"]["traefik.http.routers.demo-bao.middlewares"] = "custom-reference@file"
    model = normalize_config(config, project_root=tmp_path)
    document = render_development_environment(model)
    assert "custom-reference@file" not in document
    assert "Traefik externe autorisé" in document
    assert "OpenBao est accessible uniquement" not in document
    assert "exposé sur le port hôte `80`" not in document
    assert "Traefik externe → Apache" in document


@pytest.mark.parametrize("exists", [False, True])
def test_doctor_checks_external_network_and_docs_omit_labels(tmp_path, monkeypatch, exists):
    config = {"version": 2, "project": {"name": "demo"},
              "environment": {"domain": "demo.localhost"}, "applications": {},
              "traefik": {"network": "proxy"}}
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    path = tmp_path / "yia.yml"
    path.write_text(yaml.safe_dump(config))
    initialize_project(path, yia_root=ROOT)
    project = load_project(path)
    monkeypatch.setattr("yia.doctor.checks.installation_checks", lambda **kwargs: [
        {"name": name, "status": "ok", "details": "available"}
        for name in ("docker", "docker-compose", "docker-daemon")
    ])
    monkeypatch.setattr("yia.doctor.checks.external_network_exists", lambda root, name: exists)
    monkeypatch.setattr("yia.doctor.checks.project_containers", lambda *args: ())
    payload = run_checks(project, yia_root=ROOT)
    check = next(check for check in payload["checks"] if check["name"] == "traefik-network")
    assert check["status"] == ("ok" if exists else "error")
    document = (tmp_path / ".agents/docs/architecture/development-environment.md").read_text()
    assert "proxy" in document
    assert "Traefik externe" in document
