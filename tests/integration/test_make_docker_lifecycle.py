from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RUN_DOCKER_INTEGRATION = os.environ.get("YIA_RUN_DOCKER_INTEGRATION") == "1"


def _make(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["make", "--no-print-directory", *arguments],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.mark.skipif(
    not RUN_DOCKER_INTEGRATION,
    reason="set YIA_RUN_DOCKER_INTEGRATION=1 to run Docker integration tests",
)
def test_make_lifecycle_preserves_then_explicitly_destroys_postgres_data(
    tmp_path: Path,
) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not available")

    project_name = f"yia-api-{uuid.uuid4().hex[:12]}"
    shutil.copy(ROOT / "templates" / "project" / "Makefile", tmp_path / "Makefile")
    os.symlink(ROOT, tmp_path / ".yia", target_is_directory=True)
    (tmp_path / "yia.yml").write_text(
        f"""version: 1
project:
  name: {project_name}
environment:
  domain: {project_name}.localhost
services:
  postgres:
    version: "18"
applications: {{}}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=integration-only\n"
        "POSTGRES_USER=yia_test\n"
        "POSTGRES_DB=yia_test\n",
        encoding="utf-8",
    )
    volume_name = f"{project_name}_postgres-data"

    try:
        generated = _make(tmp_path, "generate")
        assert generated.returncode == 0, generated.stderr
        started = _make(tmp_path, "up")
        assert started.returncode == 0, started.stderr

        status = _make(tmp_path, "ps", "FORMAT=json")
        payload = json.loads(status.stdout)
        assert status.returncode == 0, status.stderr
        assert payload["services"][0]["service"] == "postgres"
        assert payload["services"][0]["health"] == "healthy"

        inserted = _make(
            tmp_path,
            "exec",
            "SERVICE=postgres",
            "CMD=psql -U yia_test -d yia_test -v ON_ERROR_STOP=1 "
            "-c \"CREATE TABLE phase10_probe (value integer);\"",
        )
        assert inserted.returncode == 0, inserted.stderr

        stopped = _make(tmp_path, "down")
        assert stopped.returncode == 0, stopped.stderr
        restarted = _make(tmp_path, "up")
        assert restarted.returncode == 0, restarted.stderr
        queried = _make(
            tmp_path,
            "exec",
            "SERVICE=postgres",
            "CMD=psql -U yia_test -d yia_test -tAc "
            "\"SELECT count(*) FROM phase10_probe;\"",
        )
        assert queried.returncode == 0, queried.stderr
        assert queried.stdout.strip() == "0"

        destroyed = _make(tmp_path, "destroy")
        assert destroyed.returncode == 0, destroyed.stderr
        volume = subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            check=False,
            capture_output=True,
            text=True,
        )
        assert volume.returncode == 0

        destroyed_data = _make(tmp_path, "destroy-data", "YES=1")
        assert destroyed_data.returncode == 0, destroyed_data.stderr
        volume = subprocess.run(
            ["docker", "volume", "inspect", volume_name],
            check=False,
            capture_output=True,
            text=True,
        )
        assert volume.returncode != 0
    finally:
        _make(tmp_path, "destroy-data", "YES=1")
