import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _minimal_consumer(root: Path) -> None:
    shutil.copy(ROOT / "templates" / "project" / "Makefile", root / "Makefile")
    shutil.copy(ROOT / "tests" / "projects" / "minimal" / "yia.yml", root / "yia.yml")
    os.symlink(ROOT, root / ".yia", target_is_directory=True)


def test_consumer_make_validate_json_has_clean_stdout(tmp_path: Path) -> None:
    shutil.copy(ROOT / "templates" / "project" / "Makefile", tmp_path / "Makefile")
    shutil.copy(ROOT / "templates" / "project" / "yia.yml", tmp_path / "yia.yml")
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=integration-only\n",
        encoding="utf-8",
    )
    os.symlink(ROOT, tmp_path / ".yia", target_is_directory=True)

    result = subprocess.run(
        ["make", "--no-print-directory", "validate", "FORMAT=json"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "ok"
    assert result.stdout.count("\n") == 1


def test_consumer_make_help_exposes_the_stable_api(tmp_path: Path) -> None:
    shutil.copy(ROOT / "templates" / "project" / "Makefile", tmp_path / "Makefile")
    os.symlink(ROOT, tmp_path / ".yia", target_is_directory=True)

    result = subprocess.run(
        ["make", "--no-print-directory", "help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    for command in (
        "install",
        "check-install",
        "init",
        "validate",
        "config",
        "generate",
        "update",
        "up",
        "down",
        "restart",
        "ps",
        "status",
        "doctor",
        "logs",
        "shell",
        "exec",
        "build",
        "rebuild",
        "test",
        "clean",
        "reset",
        "destroy",
        "destroy-data",
        "version",
    ):
        assert f"make {command}" in result.stdout
    assert "DESTRUCTIF" in result.stdout


def test_consumer_make_validate_json_error_has_clean_stdout(tmp_path: Path) -> None:
    shutil.copy(ROOT / "templates" / "project" / "Makefile", tmp_path / "Makefile")
    shutil.copy(
        ROOT / "tests" / "projects" / "invalid" / "yia.yml",
        tmp_path / "yia.yml",
    )
    os.symlink(ROOT, tmp_path / ".yia", target_is_directory=True)

    result = subprocess.run(
        ["make", "--no-print-directory", "validate", "FORMAT=json"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "YIA_CONFIG_INVALID"
    assert result.stdout.count("\n") == 1


def test_consumer_make_generate_is_idempotent(tmp_path: Path) -> None:
    _minimal_consumer(tmp_path)

    first = subprocess.run(
        ["make", "--no-print-directory", "generate"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    compose = tmp_path / ".yia-runtime" / "compose" / "compose.yaml"
    first_stat = compose.stat()
    second = subprocess.run(
        ["make", "--no-print-directory", "generate"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "déjà à jour" in second.stdout
    assert compose.stat().st_ino == first_stat.st_ino
    assert compose.stat().st_mtime_ns == first_stat.st_mtime_ns


def test_consumer_make_test_runs_yia_validation_only(tmp_path: Path) -> None:
    _minimal_consumer(tmp_path)

    result = subprocess.run(
        ["make", "--no-print-directory", "test"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Validation Yia du projet réussie" in result.stdout


def test_consumer_make_init_bootstraps_an_empty_project(tmp_path: Path) -> None:
    shutil.copy(ROOT / "tests/projects/minimal/yia.yml", tmp_path / "yia.yml")
    os.symlink(ROOT, tmp_path / ".yia", target_is_directory=True)

    init = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-C",
            str(ROOT),
            f"PROJECT_ROOT={tmp_path}",
            "init",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    validate = subprocess.run(
        ["make", "--no-print-directory", "validate"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert init.returncode == 0, init.stderr
    assert "Projet Yia initialisé" in init.stdout
    assert validate.returncode == 0, validate.stderr
    assert (tmp_path / "Makefile").is_file()
    assert (tmp_path / ".env.example").is_file()
    assert (tmp_path / ".env").is_file()
    assert (tmp_path / ".agents/docs/INDEX.md").is_file()
    assert (tmp_path / ".agents/skills/project-docs/SKILL.md").is_file()
    assert (tmp_path / ".agents/skills/update-project-docs/SKILL.md").is_file()
    assert (tmp_path / ".yia-runtime/compose/compose.yaml").is_file()
    assert not (tmp_path / ".yia-data").exists()


def test_consumer_make_init_does_not_start_docker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shutil.copy(ROOT / "tests/projects/minimal/yia.yml", tmp_path / "yia.yml")
    os.symlink(ROOT, tmp_path / ".yia", target_is_directory=True)
    shutil.copy(ROOT / "templates/project/Makefile", tmp_path / "Makefile")
    docker_log = tmp_path / "docker-was-called"
    docker = tmp_path / "docker"
    docker.write_text(
        f"#!/bin/sh\nprintf called > {docker_log}\nexit 99\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")

    result = subprocess.run(
        ["make", "--no-print-directory", "init"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )

    assert result.returncode == 0, result.stderr
    assert not docker_log.exists()


def test_consumer_make_update_is_idempotent_without_docker_services(
    tmp_path: Path,
) -> None:
    _minimal_consumer(tmp_path)
    initialized = subprocess.run(
        ["make", "--no-print-directory", "init"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert initialized.returncode == 0, initialized.stderr
    config = tmp_path / "yia.yml"
    config.write_text(
        config.read_text(encoding="utf-8").replace(
            "minimal.localhost",
            "updated.localhost",
        ),
        encoding="utf-8",
    )
    derived = tmp_path / ".agents/docs/architecture/development-environment.md"
    derived.write_text("stale\n", encoding="utf-8")

    first = subprocess.run(
        ["make", "--no-print-directory", "update"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    compose = tmp_path / ".yia-runtime/compose/compose.yaml"
    identities = {
        path: (path.stat().st_ino, path.stat().st_mtime_ns)
        for path in (derived, compose)
    }
    second = subprocess.run(
        ["make", "--no-print-directory", "update"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "déjà à jour" in second.stdout
    assert "Ce document est généré par Yia" in derived.read_text(encoding="utf-8")
    assert {
        path: (path.stat().st_ino, path.stat().st_mtime_ns)
        for path in identities
    } == identities
