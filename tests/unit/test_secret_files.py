from pathlib import Path
import json

import pytest
import yaml

from yia.cli import main
from yia.errors import YiaError
from yia.project import generate_project, load_project
from yia.documentation.manager import render_development_environment


def secret_project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    secret = tmp_path / "external-password"
    secret.write_text("synthetic-file-value\n")
    monkeypatch.setenv("POSTGRES_PASSWORD", "synthetic-ignored-value")
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic-ignored-value")
    raw = {
        "version": 2, "project": {"name": "secret-files"},
        "environment": {"domain": "secret-files.localhost"},
        "services": {
            "postgres": {"version": "18", "secret_files": {"POSTGRES_PASSWORD": str(secret)}},
            "redis": {"version": "7.4", "secret_files": {"REDIS_PASSWORD": str(secret)}},
        },
        "applications": {
            "api": {"type": "php", "path": ".", "source": {"type": "linked"},
                    "runtime": {"php": "8.4"}, "secret_files": {"DB_PASSWORD": str(secret)}}
        },
    }
    config = root / "yia.yml"
    config.write_text(yaml.safe_dump(raw))
    return root, secret, config, raw


def test_files_take_precedence_without_reading_or_exporting_values(tmp_path, monkeypatch):
    root, secret, config, _ = secret_project(tmp_path, monkeypatch)
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == secret:
            pytest.fail("generation must not open secret contents")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    project = load_project(config)
    assert generate_project(project).changed
    snapshot = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in project.runtime_path.rglob("*") if p.is_file()}
    assert not generate_project(project).changed
    assert snapshot == {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in snapshot}
    for content, _ in snapshot.values():
        assert b"synthetic-file-value" not in content
        assert b"synthetic-ignored-value" not in content
    compose = yaml.safe_load(project.compose_path.read_text())
    for service, variable in (("postgres", "POSTGRES_PASSWORD"), ("redis", "REDIS_PASSWORD")):
        spec = compose["services"][service]
        assert variable not in spec["environment"]
        destination = spec["environment"][variable + "_FILE"]
        assert any(m["source"] == str(secret) and m["target"] == destination and m["read_only"] for m in spec["volumes"])
    assert "/tmp" in compose["services"]["redis"]["tmpfs"]
    assert compose["services"]["postgres"]["entrypoint"] == ["/bin/sh", "/yia/start.sh"]
    pools = (root / ".yia-runtime/php/8.4/fpm-pools.conf").read_text()
    assert "env[DB_PASSWORD] = $" in pools


@pytest.mark.parametrize("kind", ["missing", "directory", "unreadable", "empty"])
def test_unavailable_file_has_no_fallback_and_structured_error(tmp_path, monkeypatch, capsys, kind):
    root, secret, config, _ = secret_project(tmp_path, monkeypatch)
    if kind == "missing":
        secret.unlink()
    elif kind == "directory":
        secret.unlink()
        secret.mkdir()
    elif kind == "unreadable":
        secret.chmod(0)
    else:
        secret.write_bytes(b"")
    assert main(["validate", "--config", str(config), "--json"]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["error"]["code"] == "YIA_CONFIG_INVALID"
    assert "synthetic-ignored-value" not in output.out
    assert output.err == ""
    assert not (root / ".yia-runtime").exists()


def test_secret_content_change_does_not_change_generated_state(tmp_path, monkeypatch):
    _, secret, config, _ = secret_project(tmp_path, monkeypatch)
    project = load_project(config)
    generate_project(project)
    previous_hash = project.config.configuration_hash
    secret.write_text("another-synthetic-value")
    project = load_project(config)
    assert project.config.configuration_hash == previous_hash
    assert not generate_project(project).changed


def test_documentation_only_names_secret_variables(tmp_path, monkeypatch):
    _, secret, config, _ = secret_project(tmp_path, monkeypatch)
    rendered = render_development_environment(load_project(config).config)
    assert "DB_PASSWORD" in rendered
    assert str(secret) not in rendered
    assert "synthetic-file-value" not in rendered
    assert "obligatoire dans `.env`" not in rendered


def test_invalid_secret_mapping_omits_arbitrary_values(tmp_path, monkeypatch, capsys):
    _, _, config, raw = secret_project(tmp_path, monkeypatch)
    raw["services"]["redis"]["secret_files"]["REDIS_PASSWORD"] = {"value": "do-not-echo"}
    config.write_text(yaml.safe_dump(raw))
    assert main(["validate", "--config", str(config), "--json"]) == 2
    assert "do-not-echo" not in capsys.readouterr().out


@pytest.mark.parametrize("operation", ["exec", "shell"])
def test_php_exec_uses_application_bootstrap(tmp_path, monkeypatch, operation):
    _, _, config, _ = secret_project(tmp_path, monkeypatch)
    generate_project(load_project(config))
    calls = []

    class Compose:
        def execute(self, service, command):
            calls.append((service, command))

    monkeypatch.setattr("yia.cli._compose", lambda project: Compose())
    arguments = [operation, "--config", str(config), "--service", "api"]
    if operation == "exec":
        arguments.extend(["--command", "php artisan about"])
    assert main(arguments) == 0
    assert calls[0][0] == "php-8.4"
    if operation == "exec":
        assert calls[0][1][-3:] == ["php", "artisan", "about"]
    else:
        assert calls[0][1][-1] == "/bin/sh"
    assert "api" in calls[0][1]
    assert "synthetic-file-value" not in str(calls)


def test_non_php_rejection_does_not_echo_runtime_blocks(tmp_path, monkeypatch, capsys):
    _, _, config, raw = secret_project(tmp_path, monkeypatch)
    app = raw["applications"]["api"]
    app["type"] = "node"
    app["runtime"] = {"node": "24"}
    app["secret_files"]["DB_PASSWORD"] = "synthetic-do-not-echo"
    config.write_text(yaml.safe_dump(raw))
    assert main(["validate", "--config", str(config), "--json"]) == 2
    assert "synthetic-do-not-echo" not in capsys.readouterr().out


def test_pool_namespace_cannot_alias_other_application():
    from yia.docker.secrets import pool_secret_variable
    assert pool_secret_variable("1", "_2_PASSWORD") != pool_secret_variable("1--2", "PASSWORD")
