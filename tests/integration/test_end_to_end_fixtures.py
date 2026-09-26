from __future__ import annotations

import http.client
import json
import os
import shutil
import stat
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/projects"
RUN_DOCKER_INTEGRATION = os.environ.get("YIA_RUN_DOCKER_INTEGRATION") == "1"
PUBLISH_HTTP = os.environ.get("YIA_E2E_PUBLISH_HTTP") == "1"


@dataclass(frozen=True, slots=True)
class FixtureCase:
    name: str
    services: tuple[str, ...]
    responses: tuple[tuple[str, str], ...] = ()


VALID_CASES = (
    FixtureCase("minimal", ()),
    FixtureCase(
        "php-only",
        ("apache", "php-8.4"),
        (("api.php-only.localhost", "Yia PHP fixture: api"),),
    ),
    FixtureCase(
        "node-only",
        ("apache", "node-24-frontend"),
        (("node-only.localhost", "Yia Node fixture: frontend"),),
    ),
    FixtureCase(
        "php-node",
        ("apache", "node-24-frontend", "php-8.4", "postgres"),
        (
            ("api.php-node.localhost", "Yia PHP fixture: api"),
            ("php-node.localhost", "Yia Node fixture: frontend"),
        ),
    ),
    FixtureCase(
        "multi-php",
        ("apache", "php-8.2", "php-8.4"),
        (
            ("api.multi-php.localhost", "Yia PHP fixture: api"),
            ("legacy.multi-php.localhost", "Yia PHP fixture: legacy"),
        ),
    ),
    FixtureCase("postgres", ("postgres",)),
    FixtureCase(
        "full",
        ("apache", "node-24-frontend", "php-8.4", "postgres"),
        (
            ("api.full.localhost", "Yia PHP fixture: api"),
            ("full.localhost", "Yia Node fixture: frontend"),
        ),
    ),
)
DOCKER_CASES = tuple(case for case in VALID_CASES if case.services)


def _run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _engine_make(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "make",
            "--no-print-directory",
            "-C",
            str(ROOT),
            f"PROJECT_ROOT={root}",
            *arguments,
        ]
    )


def _make(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return _run(["make", "--no-print-directory", *arguments], cwd=root)


def _materialize(root: Path, case: FixtureCase) -> str:
    shutil.copytree(FIXTURES / case.name, root, dirs_exist_ok=True)
    project_name = f"yia-e2e-{case.name}-{uuid.uuid4().hex[:8]}"
    config = root / "yia.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            f"name: {case.name}",
            f"name: {project_name}",
            1,
        ),
        encoding="utf-8",
    )
    (root / ".env").write_text(
        "POSTGRES_PASSWORD=e2e-only\n"
        "POSTGRES_USER=yia_e2e\n"
        "POSTGRES_DB=yia_e2e\n",
        encoding="utf-8",
    )
    (root / ".yia").symlink_to(ROOT, target_is_directory=True)
    return project_name


def _snapshot(root: Path) -> dict[str, tuple[bytes, int, int, int]]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _contents(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _container_id(name: str) -> str:
    result = _run(["docker", "inspect", "--format", "{{.Id}}", name], timeout=30)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _compose(
    root: Path,
    project_name: str,
    override: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            "docker",
            "compose",
            "--project-name",
            project_name,
            "--env-file",
            str(root / ".env"),
            "--file",
            str(root / ".yia-runtime/compose/compose.yaml"),
            "--file",
            str(override),
            *arguments,
        ],
        cwd=root,
    )


def _container_http_body(container: str, hostname: str) -> str:
    result = _run(
        [
            "docker",
            "exec",
            container,
            "wget",
            "-qO-",
            "--header",
            f"Host: {hostname}",
            "http://127.0.0.1/",
        ],
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def _host_http_body(hostname: str) -> str:
    connection = http.client.HTTPConnection("127.0.0.1", 80, timeout=30)
    try:
        connection.request("GET", "/", headers={"Host": hostname})
        response = connection.getresponse()
        body = response.read().decode("utf-8")
    finally:
        connection.close()
    assert response.status == 200, body
    return body


@pytest.mark.parametrize("case", VALID_CASES, ids=lambda case: case.name)
def test_valid_fixture_converges_through_public_make_api(
    tmp_path: Path,
    case: FixtureCase,
) -> None:
    _materialize(tmp_path, case)

    initialized = _engine_make(tmp_path, "init")
    assert initialized.returncode == 0, initialized.stderr

    validated = _make(tmp_path, "validate", "FORMAT=json")
    assert validated.returncode == 0, validated.stderr
    assert json.loads(validated.stdout)["status"] == "ok"

    tested = _make(tmp_path, "test")
    assert tested.returncode == 0, tested.stderr

    compose = yaml.safe_load(
        (tmp_path / ".yia-runtime/compose/compose.yaml").read_text(encoding="utf-8")
    )
    assert tuple(sorted(compose["services"])) == case.services
    assert (tmp_path / ".agents/docs/architecture/development-environment.md").is_file()
    assert (tmp_path / ".agents/skills/project-docs/SKILL.md").is_file()
    assert not (tmp_path / ".yia-data").exists()

    before = _snapshot(tmp_path / ".yia-runtime")
    generated = _make(tmp_path, "generate")
    assert generated.returncode == 0, generated.stderr
    assert "déjà à jour" in generated.stdout
    assert _snapshot(tmp_path / ".yia-runtime") == before

    if not case.services:
        first = _make(tmp_path, "update")
        after_first = _snapshot(tmp_path / ".yia-runtime")
        second = _make(tmp_path, "update")
        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        assert "déjà à jour" in second.stdout
        assert _snapshot(tmp_path / ".yia-runtime") == after_first


def test_invalid_fixture_fails_before_initialization(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES / "invalid", tmp_path, dirs_exist_ok=True)
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)

    validated = _engine_make(tmp_path, "validate", "FORMAT=json")
    payload = json.loads(validated.stdout)
    initialized = _engine_make(tmp_path, "init")

    assert validated.returncode == 2
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "YIA_CONFIG_INVALID"
    assert initialized.returncode == 2
    assert "YIA_CONFIG_INVALID" in initialized.stderr
    assert not (tmp_path / "Makefile").exists()
    assert not (tmp_path / ".agents").exists()
    assert not (tmp_path / ".yia-runtime").exists()


@pytest.mark.skipif(
    not RUN_DOCKER_INTEGRATION,
    reason="set YIA_RUN_DOCKER_INTEGRATION=1 to run Docker integration tests",
)
@pytest.mark.parametrize("case", DOCKER_CASES, ids=lambda case: case.name)
def test_fixture_runs_end_to_end_with_docker(
    tmp_path: Path,
    case: FixtureCase,
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not available")

    project_name = _materialize(tmp_path, case)
    sources_before = _contents(tmp_path / "apps")
    override = tmp_path / "compose.e2e.yaml"
    isolated_apache = "apache" in case.services and not PUBLISH_HTTP
    if isolated_apache:
        override.write_text(
            "services:\n  apache:\n    ports: !reset []\n",
            encoding="utf-8",
        )

    try:
        initialized = _engine_make(tmp_path, "init")
        assert initialized.returncode == 0, initialized.stderr

        if isolated_apache:
            built = _make(tmp_path, "build")
            assert built.returncode == 0, built.stderr
            first = _compose(
                tmp_path,
                project_name,
                override,
                "up",
                "--detach",
                "--wait",
                "--remove-orphans",
            )
        else:
            first = _make(tmp_path, "update")
        assert first.returncode == 0, first.stderr

        status = _make(tmp_path, "ps", "FORMAT=json")
        assert status.returncode == 0, status.stderr
        services = json.loads(status.stdout)["services"]
        assert tuple(sorted(service["service"] for service in services)) == case.services
        assert all(service["state"] == "running" for service in services)
        assert all(service["health"] == "healthy" for service in services)

        diagnosed = _make(tmp_path, "doctor", "FORMAT=json")
        assert diagnosed.returncode == 0, diagnosed.stderr
        assert json.loads(diagnosed.stdout)["status"] == "ok"

        container_ids = {
            service["name"]: _container_id(service["name"]) for service in services
        }
        runtime_before = _snapshot(tmp_path / ".yia-runtime")

        apache = next(
            (service["name"] for service in services if service["service"] == "apache"),
            None,
        )
        for hostname, expected in case.responses:
            assert apache is not None
            body = (
                _host_http_body(hostname)
                if PUBLISH_HTTP
                else _container_http_body(apache, hostname)
            )
            assert expected in body

        if isolated_apache:
            rebuilt = _make(tmp_path, "build")
            assert rebuilt.returncode == 0, rebuilt.stderr
            second = _compose(
                tmp_path,
                project_name,
                override,
                "up",
                "--detach",
                "--wait",
                "--remove-orphans",
            )
        else:
            second = _make(tmp_path, "update")
        assert second.returncode == 0, second.stderr
        if not isolated_apache:
            assert "déjà à jour" in second.stdout
        assert {
            name: _container_id(name) for name in container_ids
        } == container_ids
        assert _snapshot(tmp_path / ".yia-runtime") == runtime_before
        assert _contents(tmp_path / "apps") == sources_before
    finally:
        _make(tmp_path, "destroy-data", "YES=1")
