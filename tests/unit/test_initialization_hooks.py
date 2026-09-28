from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from yia.config import load_normalized_config
from yia.docker.compose import _compose_model
from yia.errors import ErrorCode, YiaError
from yia.initialization_hooks import run_initialization_hooks


SCHEMA = Path(__file__).resolve().parents[2] / "schemas/yia.schema.json"


def _project(tmp_path: Path):
    (tmp_path / "db").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "api").mkdir()
    (tmp_path / "db/init.sql").write_text(
        "CREATE ROLE reader;\nCREATE DATABASE secondary;\n", encoding="utf-8"
    )
    (tmp_path / "scripts/service.sh").write_text("exit 0\n", encoding="utf-8")
    (tmp_path / "api/init.sh").write_text("exit 0\n", encoding="utf-8")
    config_path = tmp_path / "yia.yml"
    config_path.write_text(
        """version: 2
project: {name: demo}
environment: {domain: demo.localhost}
services:
  postgres:
    version: "18"
    initialization:
      sql: db/init.sql
      once: {id: users-v1, script: scripts/service.sh}
applications:
  api:
    type: php
    path: api
    source: {type: linked}
    runtime: {php: "8.2"}
    initialization:
      once: {id: app-v1, script: init.sh}
""",
        encoding="utf-8",
    )
    return load_normalized_config(config_path, SCHEMA)


def test_sql_and_once_hooks_generate_mounts_and_run_once(tmp_path: Path) -> None:
    config = _project(tmp_path)
    postgres = _compose_model(config)["services"]["postgres"]
    targets = {volume["target"] for volume in postgres["volumes"]}
    assert "/yia-init/init.sql" in targets
    assert "/docker-entrypoint-initdb.d/10-yia.sh" in targets
    assert "/yia-init/once.sh" in targets
    expected = hashlib.sha256((tmp_path / "db/init.sql").read_bytes()).hexdigest()

    class Compose:
        calls: list[list[str]] = []

        def run(self, arguments, **_kwargs):
            self.calls.append(list(arguments))
            return subprocess.CompletedProcess(arguments, 0, stdout=expected)

    compose = Compose()
    run_initialization_hooks(config, compose)
    run_initialization_hooks(config, compose)
    assert len(compose.calls) == 4  # SQL marker checked twice; each hook once.
    assert len(list((tmp_path / ".yia-data/once").glob("*.done"))) == 2


def test_sql_marker_absent_or_changed_is_explicit_error(tmp_path: Path) -> None:
    config = _project(tmp_path)

    class Compose:
        def run(self, arguments, **_kwargs):
            return subprocess.CompletedProcess(arguments, 0, stdout="wrong-hash")

    with pytest.raises(YiaError) as caught:
        run_initialization_hooks(config, Compose())
    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert "diffère" in caught.value.message
    assert not (tmp_path / ".yia-data").exists()


def test_hook_failure_has_no_success_marker_and_can_retry(tmp_path: Path) -> None:
    config = _project(tmp_path)
    expected = hashlib.sha256((tmp_path / "db/init.sql").read_bytes()).hexdigest()

    class Compose:
        fail = True

        def run(self, arguments, **_kwargs):
            if arguments[:3] == ["exec", "-T", "postgres"] and any(
                str(argument).endswith("once.sh") for argument in arguments
            ):
                if self.fail:
                    raise YiaError(ErrorCode.DOCKER_UNAVAILABLE, "script failed")
            return subprocess.CompletedProcess(arguments, 0, stdout=expected)

    compose = Compose()
    with pytest.raises(YiaError) as caught:
        run_initialization_hooks(config, compose)
    assert caught.value.code is ErrorCode.GENERATION_FAILED
    assert not list((tmp_path / ".yia-data/once").glob("*.done"))
    compose.fail = False
    run_initialization_hooks(config, compose)
    assert len(list((tmp_path / ".yia-data/once").glob("*.done"))) == 2


def test_initialization_paths_must_exist_and_be_contained(tmp_path: Path) -> None:
    config = _project(tmp_path)
    path = tmp_path / "yia.yml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("sql: db/init.sql", "sql: ../outside.sql"),
        encoding="utf-8",
    )
    with pytest.raises(YiaError):
        load_normalized_config(path, SCHEMA)


def test_custom_pg_dump_archive_is_not_a_sql_script(tmp_path: Path) -> None:
    _project(tmp_path)
    (tmp_path / "db/init.sql").write_bytes(b"PGDMP\0binary archive")
    with pytest.raises(YiaError) as caught:
        load_normalized_config(tmp_path / "yia.yml", SCHEMA)
    assert any(
        error["constraint"] == "plain_sql_file"
        for error in caught.value.details["validation_errors"]
    )
