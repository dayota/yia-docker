from pathlib import Path

import pytest

from yia.errors import ErrorCode, YiaError
from yia.project import (
    generate_project,
    generation_is_current,
    load_project,
    runtime_project_identity,
)


ROOT = Path(__file__).resolve().parents[2]


def _write_postgres_project(root: Path) -> Path:
    config = root / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: database
environment:
  domain: database.localhost
services:
  postgres:
    version: "18"
applications: {}
""",
        encoding="utf-8",
    )
    return config


def test_postgres_password_is_required_without_leaking_a_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    config = _write_postgres_project(tmp_path)

    with pytest.raises(YiaError) as caught:
        load_project(config)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.details["variable"] == "POSTGRES_PASSWORD"
    assert "value" not in caught.value.details


def test_dotenv_satisfies_postgres_requirement(tmp_path: Path) -> None:
    config = _write_postgres_project(tmp_path)
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=local-test-only\n",
        encoding="utf-8",
    )

    project = load_project(config)

    assert project.root == tmp_path.resolve()


def test_generation_status_detects_content_tampering(tmp_path: Path) -> None:
    source = ROOT / "tests" / "projects" / "minimal" / "yia.yml"
    config = tmp_path / "yia.yml"
    config.write_bytes(source.read_bytes())
    project = load_project(config)

    assert generation_is_current(project) is False
    first = generate_project(project)
    second = generate_project(project)
    assert first.changed is True
    assert second.changed is False
    assert generation_is_current(project) is True

    project.compose_path.write_text("modified\n", encoding="utf-8")

    assert generation_is_current(project) is False


def test_node_application_requires_a_dev_script(tmp_path: Path) -> None:
    application = tmp_path / "apps" / "frontend"
    application.mkdir(parents=True)
    (application / "package.json").write_text(
        '{"private": true, "scripts": {}}\n',
        encoding="utf-8",
    )
    config = tmp_path / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: frontend
environment:
  domain: frontend.localhost
applications:
  frontend:
    type: node
    path: apps/frontend
    runtime:
      node: "24"
""",
        encoding="utf-8",
    )

    with pytest.raises(YiaError) as caught:
        load_project(config)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.details["validation_errors"][0]["constraint"] == (
        "non_empty_scripts_dev"
    )


def test_runtime_identity_prefers_generated_compose_name(tmp_path: Path) -> None:
    config = tmp_path / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: renamed-project
environment:
  domain: renamed-project.localhost
applications: {}
""",
        encoding="utf-8",
    )
    compose = tmp_path / ".yia-runtime" / "compose" / "compose.yaml"
    compose.parent.mkdir(parents=True)
    compose.write_text("name: previous-project\nservices: {}\n", encoding="utf-8")

    root, name = runtime_project_identity(config)

    assert root == tmp_path.resolve()
    assert name == "previous-project"
