from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from yia.config import normalize_config
from yia.docker import ComposeGenerator
from yia.generators import GenerationContext
from yia.state import YiaState


RUN_DOCKER_INTEGRATION = os.environ.get("YIA_RUN_DOCKER_INTEGRATION") == "1"


def _compose(
    docker: str,
    compose_path: Path,
    env_path: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            docker,
            "compose",
            "--env-file",
            str(env_path),
            "-f",
            str(compose_path),
            *arguments,
        ],
        check=check,
        capture_output=True,
        text=True,
        timeout=240,
    )


@pytest.mark.skipif(
    not RUN_DOCKER_INTEGRATION,
    reason="set YIA_RUN_DOCKER_INTEGRATION=1 to run Docker integration tests",
)
def test_postgres_is_healthy_and_persists_data_across_recreation(
    tmp_path: Path,
) -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker CLI is not available")

    project_name = f"yia-pg-{uuid.uuid4().hex[:12]}"
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": project_name},
            "environment": {"domain": f"{project_name}.localhost"},
            "services": {"postgres": {"version": "18"}},
            "applications": {},
        },
        project_root=tmp_path,
    )
    context = GenerationContext(config=config, state=YiaState.from_config(config))
    generated = tuple(ComposeGenerator().generate(context))
    compose_path = tmp_path / ".yia-runtime" / generated[0].path
    compose_path.parent.mkdir(parents=True)
    compose_path.write_bytes(generated[0].content)
    env_path = tmp_path / ".env"
    env_path.write_text(
        "POSTGRES_PASSWORD=integration-only\n"
        "POSTGRES_USER=yia_test\n"
        "POSTGRES_DB=yia_test\n",
        encoding="utf-8",
    )

    try:
        _compose(docker, compose_path, env_path, "up", "-d", "--wait", "postgres")
        _compose(
            docker,
            compose_path,
            env_path,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "yia_test",
            "-d",
            "yia_test",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            "CREATE TABLE phase9_probe (value integer); "
            "INSERT INTO phase9_probe VALUES (9);",
        )

        _compose(docker, compose_path, env_path, "down")
        _compose(docker, compose_path, env_path, "up", "-d", "--wait", "postgres")
        result = _compose(
            docker,
            compose_path,
            env_path,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "yia_test",
            "-d",
            "yia_test",
            "-tAc",
            "SELECT value FROM phase9_probe;",
        )

        assert result.stdout.strip() == "9"
    finally:
        _compose(
            docker,
            compose_path,
            env_path,
            "down",
            "--volumes",
            "--remove-orphans",
            check=False,
        )
