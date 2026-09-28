from __future__ import annotations

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
def test_sql_and_service_hook_run_once_on_new_postgres_volume(tmp_path: Path) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is not available")
    project = f"yia-init-{uuid.uuid4().hex[:12]}"
    shutil.copy(ROOT / "templates/project/Makefile", tmp_path / "Makefile")
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    (tmp_path / "database").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "database/initial.sql").write_text(
        "CREATE ROLE report_reader;\nCREATE DATABASE reporting OWNER report_reader;\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts/once.sh").write_text(
        "#!/bin/sh\nset -eu\n"
        "psql -v ON_ERROR_STOP=1 --username \"$POSTGRES_USER\" "
        "--dbname \"$POSTGRES_DB\" -c "
        "'CREATE TABLE once_probe (value integer);'\n",
        encoding="utf-8",
    )
    (tmp_path / "yia.yml").write_text(
        f"""version: 2
project: {{name: {project}}}
environment: {{domain: {project}.localhost}}
services:
  postgres:
    version: "18"
    initialization:
      sql: database/initial.sql
      once: {{id: probe-v1, script: scripts/once.sh}}
applications: {{}}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=integration-only\n"
        "POSTGRES_USER=yia_test\nPOSTGRES_DB=yia_test\n",
        encoding="utf-8",
    )
    try:
        generated = _make(tmp_path, "generate")
        assert generated.returncode == 0, generated.stderr
        first = _make(tmp_path, "up")
        assert first.returncode == 0, first.stderr
        role = _make(
            tmp_path, "exec", "SERVICE=postgres",
            "CMD=psql -U yia_test -d yia_test -tAc "
            "\"SELECT count(*) FROM pg_roles WHERE rolname = 'report_reader';\"",
        )
        assert role.returncode == 0, role.stderr
        assert role.stdout.strip() == "1"
        assert len(list((tmp_path / ".yia-data/once").glob("*.done"))) == 1

        second = _make(tmp_path, "up")
        assert second.returncode == 0, second.stderr
        (tmp_path / "database/initial.sql").write_text(
            "CREATE ROLE changed;\n", encoding="utf-8"
        )
        changed = _make(tmp_path, "up")
        assert changed.returncode != 0
        assert "YIA_CONFIG_INVALID" in changed.stderr
    finally:
        _make(tmp_path, "destroy-data", "YES=1")
