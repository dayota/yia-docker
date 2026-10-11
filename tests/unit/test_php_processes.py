import copy
import json
import shutil
import subprocess
import pwd
import grp
import os
from pathlib import Path

import pytest
import yaml

from yia.project import load_project, generate_project
from yia.errors import YiaError
from yia.cli import main


def process_project(root):
    (root / "public").mkdir()
    raw = {"version": 2, "project": {"name": "processes"},
           "environment": {"domain": "processes.localhost"},
           "services": {"redis": {"version": "7.4"}},
           "applications": {"api": {
               "type": "php", "path": ".", "source": {"type": "linked"},
               "runtime": {"php": "8.4"},
               "processes": {
                   "horizon": {"command": ["php", "artisan", "horizon"], "stop_grace_period": "20s", "depends_on": ["redis"]},
                   "reverb": {"command": ["php", "artisan", "reverb:start", "--port=8080"],
                              "port": 8080, "stop_grace_period": "10s",
                              "healthcheck": {"test": ["php", "-r", "exit(0);"], "interval": "1s", "timeout": "1s", "retries": 2, "start_period": "1s"}},
               },
               "web": {"hostname": "processes.localhost", "public_directory": "public",
                       "proxy_routes": [{"path": "/app/", "process": "reverb", "websocket": True},
                                        {"path": "/apps/", "process": "reverb", "websocket": False}]},
           }}}
    config = root / "yia.yml"
    config.write_text(yaml.safe_dump(raw))
    return raw, config


def test_supervision_uses_one_private_runtime_and_deterministic_configuration(tmp_path, monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    _, config = process_project(tmp_path)
    project = load_project(config)
    assert generate_project(project).changed
    assert not generate_project(project).changed
    compose = yaml.safe_load(project.compose_path.read_text())
    assert set(compose["services"]) == {"apache", "php-8.4", "redis"}
    runtime = compose["services"]["php-8.4"]
    assert "ports" not in runtime
    assert runtime["networks"] == ["yia"]
    assert runtime["depends_on"] == {"redis": {"condition": "service_healthy"}}
    assert runtime["stop_grace_period"] == "21s"
    assert "/run/yia-php" in runtime["tmpfs"]
    manifest = json.loads((project.runtime_path / "php/8.4/applications.json").read_text())
    assert manifest["api"]["processes"]["horizon"]["command"] == ["php", "artisan", "horizon"]
    assert manifest["api"]["processes"]["horizon"]["working_directory"] == "/workspace/api"
    vhost = (project.runtime_path / "apache/vhosts.conf").read_text()
    assert 'ProxyPass "/app/" "http://php-8.4:8080/app/"' in vhost
    assert "upgrade=websocket" in vhost
    assert 'ProxyPass "/apps/" "http://php-8.4:8080/apps/"' in vhost
    assert vhost.index("ProxyPass ") < vhost.index("SetHandler")
    assert 'SetHandler "proxy:fcgi://php-8.4:9000"' in vhost


@pytest.mark.parametrize("case", ["missing_process", "missing_port", "duplicate_port", "fpm_port", "bad_cwd", "absent_dependency", "self_dependency", "apache_cycle", "bad_argv", "injected_path", "overlapping_routes"])
def test_process_and_route_contract_rejects_invalid_configuration(tmp_path, monkeypatch, case):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    raw, config = process_project(tmp_path)
    app = raw["applications"]["api"]
    if case == "missing_process": app["web"]["proxy_routes"][0]["process"] = "absent"
    elif case == "missing_port": del app["processes"]["reverb"]["port"]
    elif case == "duplicate_port": app["processes"]["horizon"]["port"] = 8080
    elif case == "fpm_port": app["processes"]["reverb"]["port"] = 9000
    elif case == "bad_cwd": app["processes"]["horizon"]["working_directory"] = "../"
    elif case == "absent_dependency": app["processes"]["horizon"]["depends_on"] = ["absent"]
    elif case == "self_dependency": app["processes"]["horizon"]["depends_on"] = ["php-8.4"]
    elif case == "apache_cycle": app["processes"]["horizon"]["depends_on"] = ["apache"]
    elif case == "bad_argv": app["processes"]["horizon"]["command"] = "php artisan horizon"
    elif case == "injected_path": app["web"]["proxy_routes"][0]["path"] = "/app/\nProxyRequests On"
    else: app["web"]["proxy_routes"][1]["path"] = "/app/sub/"
    config.write_text(yaml.safe_dump(raw))
    with pytest.raises(YiaError) as error:
        load_project(config)
    assert error.value.exit_code == 2


def test_reload_secrets_only_recreates_consumers(tmp_path, monkeypatch):
    from test_secret_files import secret_project
    _, secret, config, _ = secret_project(tmp_path, monkeypatch)
    project = load_project(config)
    generate_project(project)
    calls = []

    class Compose:
        def force_recreate_services(self, services): calls.append(services)

    monkeypatch.setattr("yia.cli._compose", lambda project: Compose())
    secret.write_text("new-synthetic-value")
    assert main(["reload-secrets", "--config", str(config)]) == 0
    assert calls == [("php-8.4", "postgres", "redis")]


def test_reload_without_file_consumers_does_not_contact_docker(tmp_path, monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    _, config = process_project(tmp_path)
    generate_project(load_project(config))
    monkeypatch.setattr("yia.cli._compose", lambda project: pytest.fail("No consumer: no Docker call"))
    assert main(["reload-secrets", "--config", str(config)]) == 0


def test_managed_working_directory_is_rechecked_after_acquisition(tmp_path, monkeypatch):
    from yia.project import validate_project_dependencies
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    raw, config = process_project(tmp_path)
    app = raw["applications"]["api"]
    app["path"] = "apps/api"
    app["source"] = {"type": "managed", "git": {"ssh": "git@example.test:repo", "branch": "main", "version": "v1"}}
    app["processes"]["horizon"]["working_directory"] = "workers"
    config.write_text(yaml.safe_dump(raw))
    project = load_project(config)
    (tmp_path / "apps/api").mkdir(parents=True)
    with pytest.raises(YiaError):
        validate_project_dependencies(project, allow_missing_managed=False)
    (tmp_path / "apps/api/workers").mkdir()
    validate_project_dependencies(project, allow_missing_managed=False)


def test_local_apache_and_fpm_parse_generated_configuration(tmp_path, monkeypatch):
    apache, fpm = shutil.which("apache2"), shutil.which("php-fpm8.4")
    if apache is None or fpm is None:
        pytest.skip("Apache et FPM locaux requis")
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    _, config = process_project(tmp_path)
    project = load_project(config)
    generate_project(project)
    pools = (project.runtime_path / "php/8.4/fpm-pools.conf").read_text()
    pools = pools.replace("user = yia", "user = " + pwd.getpwuid(os.getuid()).pw_name)
    pools = pools.replace("group = yia", "group = " + grp.getgrgid(os.getgid()).gr_name)
    # Only translate container filesystem paths for this host-side syntax check.
    pools = pools.replace("chdir = /workspace/api", f"chdir = {tmp_path}")
    pool_file = tmp_path / "local-fpm.conf"
    pool_file.write_text("[global]\nerror_log=/dev/null\n" + pools)
    checked = subprocess.run([fpm, "-R", "-t", "-y", str(pool_file)], capture_output=True)
    assert checked.returncode == 0, checked.stderr.decode()
    modules = ["mpm_event", "authz_core", "authz_host", "dir", "mime", "proxy", "proxy_fcgi", "proxy_http", "rewrite", "headers"]
    apache_config = tmp_path / "local-httpd.conf"
    apache_config.write_text(
        f'ServerRoot "{tmp_path}"\nServerName localhost\nListen 127.0.0.1:18080\nErrorLog /dev/null\n'
        + "\n".join(f'LoadModule {name}_module /usr/lib/apache2/modules/mod_{name}.so' for name in modules)
        + f'\nInclude "{project.runtime_path / "apache/vhosts.conf"}"\n'
    )
    checked = subprocess.run([apache, "-t", "-f", str(apache_config)], capture_output=True)
    if b"Operation not permitted" in checked.stderr and b"Listen setup failed" in checked.stderr:
        pytest.skip("Le bac à sable interdit la socket requise par apache -t")
    assert checked.returncode == 0, checked.stderr.decode()


def test_process_status_only_returns_controlled_fields(tmp_path, monkeypatch):
    from yia.docker.processes import process_status
    monkeypatch.setenv("REDIS_PASSWORD", "synthetic")
    _, config = process_project(tmp_path)

    class Compose:
        def run(self, *args, **kwargs):
            return subprocess.CompletedProcess([], 0, json.dumps({"api/horizon": {"state": "exited", "exit_code": 7, "environment": "do-not-copy"}, "api/reverb": {"state": "synthetic-secret"}}))

    result = process_status(load_project(config).config, Compose())
    assert result["api/horizon"] == {"service": "php-8.4", "state": "exited", "exit_code": 7}
    assert result["api/reverb"]["state"] == "unavailable"
    assert "do-not-copy" not in str(result)
    assert "synthetic-secret" not in str(result)
