from pathlib import Path

import pytest

from yia.config import normalize_config
from yia.docker.runner import DockerCompose, resolve_service
from yia.errors import YiaError


def _config(tmp_path: Path):
    for name in ("api", "frontend", "admin"):
        (tmp_path / "apps" / name).mkdir(parents=True)
    return normalize_config(
        {
            "version": 1,
            "project": {"name": "services"},
            "environment": {"domain": "services.localhost"},
            "services": {"postgres": {"version": "18"}},
            "applications": {
                "api": {
                    "type": "php",
                    "path": "apps/api",
                    "runtime": {"php": "8.4"},
                },
                "admin": {
                    "type": "node",
                    "path": "apps/admin",
                    "runtime": {"node": "24"},
                },
                "frontend": {
                    "type": "node",
                    "path": "apps/frontend",
                    "runtime": {"node": "24"},
                },
            },
        },
        project_root=tmp_path,
    )


def test_service_resolution_maps_applications_and_infrastructure(tmp_path: Path) -> None:
    config = _config(tmp_path)

    assert resolve_service(config, "api") == "php-8.4"
    assert resolve_service(config, "frontend") == "node-24-frontend"
    assert resolve_service(config, "postgres") == "postgres"
    assert resolve_service(config, "php-8.4") == "php-8.4"


def test_shared_node_runtime_alias_is_rejected_as_ambiguous(tmp_path: Path) -> None:
    config = _config(tmp_path)

    with pytest.raises(YiaError) as caught:
        resolve_service(config, "node-24")

    assert caught.value.details["matches"] == [
        "node-24-admin",
        "node-24-frontend",
    ]


def test_compose_command_uses_project_root_and_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compose_path = tmp_path / ".yia-runtime" / "compose" / "compose.yaml"
    compose_path.parent.mkdir(parents=True)
    compose_path.write_text("services: {}\n", encoding="utf-8")
    dotenv = tmp_path / ".env"
    dotenv.write_text("VALUE=test\n", encoding="utf-8")
    calls: list[tuple[list[str], Path]] = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(arguments, *, cwd, **_kwargs):
        calls.append((list(arguments), cwd))
        return Result()

    monkeypatch.setattr("yia.docker.runner._docker_path", lambda: "/usr/bin/docker")
    monkeypatch.setattr("yia.docker.runner.subprocess.run", fake_run)
    compose = DockerCompose(
        project_root=tmp_path,
        project_name="demo",
        compose_path=compose_path,
        dotenv_path=dotenv,
    )

    compose.logs("postgres", follow=False)

    arguments, cwd = calls[0]
    assert cwd == tmp_path
    assert arguments[:4] == [
        "/usr/bin/docker",
        "compose",
        "--project-name",
        "demo",
    ]
    assert ["--env-file", str(dotenv)] == arguments[6:8]
    assert arguments[-3:] == ["logs", "--no-color", "postgres"]
    assert "--follow" not in arguments
