from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from yia.errors import ErrorCode, YiaError
from yia.initialization import initialize_project
from yia.project import load_project
from yia.state import YiaState, write_state
from yia.updating import update_project


ROOT = Path(__file__).resolve().parents[2]


def _write_minimal(root: Path, *, name: str = "updated", domain: str = "updated.localhost") -> Path:
    config = root / "yia.yml"
    config.write_text(
        f"""version: 1
project:
  name: {name}
environment:
  domain: {domain}
applications: {{}}
""",
        encoding="utf-8",
    )
    return config


def _prepare_minimal(root: Path) -> Path:
    (root / ".yia").symlink_to(ROOT, target_is_directory=True)
    config = _write_minimal(root)
    initialize_project(config, yia_root=ROOT)
    return config


def _snapshot(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".yia" not in path.relative_to(root).parts
    }


def test_update_regenerates_configuration_and_is_idempotent_without_services(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = _prepare_minimal(tmp_path)
    human = tmp_path / ".agents/docs/domain/product.md"
    human.write_text("# Connaissance humaine\n", encoding="utf-8")
    dotenv = (tmp_path / ".env").read_bytes()
    data = tmp_path / ".yia-data"
    data.mkdir()
    (data / "persistent").write_text("keep", encoding="utf-8")
    _write_minimal(tmp_path, domain="changed.localhost")
    derived = tmp_path / ".agents/docs/architecture/development-environment.md"
    derived.write_text("stale\n", encoding="utf-8")
    monkeypatch.setattr(
        "yia.updating.compose_for_project",
        lambda **_kwargs: pytest.fail("Docker must not run without services"),
    )

    first = update_project(load_project(config_path))
    first_snapshot = _snapshot(tmp_path)
    second = update_project(load_project(config_path))

    assert first.generation_changed is True
    assert first.documentation.changed is True
    assert first.compose_applied is False
    assert second.generation_changed is False
    assert second.documentation.changed is False
    assert second.changed is False
    assert _snapshot(tmp_path) == first_snapshot
    assert human.read_text() == "# Connaissance humaine\n"
    assert (tmp_path / ".env").read_bytes() == dotenv
    assert (data / "persistent").read_text() == "keep"


def test_update_converges_declared_services_on_every_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    config_path = tmp_path / "yia.yml"
    config_path.write_text(
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
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=local-test-only\n",
        encoding="utf-8",
    )
    initialize_project(config_path, yia_root=ROOT)
    calls: list[tuple[str, tuple[str, ...]]] = []

    class Compose:
        def converge(self):
            calls.append(("converge", ()))

        def force_recreate_services(self, services):
            calls.append(("force", tuple(services)))

    monkeypatch.setattr(
        "yia.updating.compose_for_project",
        lambda **_kwargs: Compose(),
    )

    first = update_project(load_project(config_path))
    second = update_project(load_project(config_path))

    assert first.services == ("postgres",)
    assert second.services == ("postgres",)
    assert calls == [
        ("converge", ()),
        ("force", ()),
        ("converge", ()),
        ("force", ()),
    ]


def test_update_recreates_apache_when_only_generated_vhost_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    application = tmp_path / "apps/api/public"
    application.mkdir(parents=True)
    config_path = tmp_path / "yia.yml"

    def write(hostname: str) -> None:
        config_path.write_text(
            f"""version: 1
project:
  name: web
environment:
  domain: web.localhost
applications:
  api:
    type: php
    path: apps/api
    runtime:
      php: "8.4"
    web:
      hostname: {hostname}
      public_directory: public
""",
            encoding="utf-8",
        )

    write("api.web.localhost")
    initialize_project(config_path, yia_root=ROOT)
    write("changed.web.localhost")
    forced: list[tuple[str, ...]] = []

    class Compose:
        def converge(self):
            pass

        def force_recreate_services(self, services):
            forced.append(tuple(services))

    monkeypatch.setattr(
        "yia.updating.compose_for_project",
        lambda **_kwargs: Compose(),
    )

    result = update_project(load_project(config_path))

    assert "apache/vhosts.conf" in result.changed_paths
    assert result.forced_services == ("apache",)
    assert forced == [("apache",)]


def test_update_recreates_php_when_only_generated_pool_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    (tmp_path / "apps/api").mkdir(parents=True)
    config_path = tmp_path / "yia.yml"

    def write(xdebug: bool) -> None:
        config_path.write_text(
            f"""version: 1
project:
  name: php-update
environment:
  domain: php-update.localhost
applications:
  api:
    type: php
    path: apps/api
    runtime:
      php: "8.4"
      xdebug: {str(xdebug).lower()}
""",
            encoding="utf-8",
        )

    write(False)
    initialize_project(config_path, yia_root=ROOT)
    write(True)
    forced: list[tuple[str, ...]] = []

    class Compose:
        def converge(self):
            pass

        def force_recreate_services(self, services):
            forced.append(tuple(services))

    monkeypatch.setattr(
        "yia.updating.compose_for_project",
        lambda **_kwargs: Compose(),
    )

    result = update_project(load_project(config_path))

    assert "php/8.4/fpm-pools.conf" in result.changed_paths
    assert result.forced_services == ("php-8.4",)
    assert forced == [("php-8.4",)]


def test_update_requires_explicit_migration_for_project_rename(
    tmp_path: Path,
) -> None:
    config_path = _prepare_minimal(tmp_path)
    _write_minimal(tmp_path, name="renamed")
    runtime_before = _snapshot(tmp_path)

    with pytest.raises(YiaError) as caught:
        update_project(load_project(config_path))

    assert caught.value.code is ErrorCode.MIGRATION_REQUIRED
    assert caught.value.details["current_name"] == "updated"
    assert caught.value.details["requested_name"] == "renamed"
    assert _snapshot(tmp_path) == runtime_before


def test_update_rejects_incompatible_documentation_state_before_changes(
    tmp_path: Path,
) -> None:
    config_path = _prepare_minimal(tmp_path)
    project = load_project(config_path)
    write_state(
        tmp_path,
        replace(
            YiaState.from_config(project.config),
            documentation_schema_version=2,
        ),
    )
    before = _snapshot(tmp_path)

    with pytest.raises(YiaError) as caught:
        update_project(project)

    assert caught.value.code is ErrorCode.MIGRATION_REQUIRED
    assert _snapshot(tmp_path) == before
