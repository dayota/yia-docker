from pathlib import Path

from yia.doctor import run_checks
from yia.initialization import initialize_project
from yia.project import load_project


ROOT = Path(__file__).resolve().parents[2]


def _initialized_project(root: Path):
    (root / ".yia").symlink_to(ROOT, target_is_directory=True)
    config = root / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: doctor-project
environment:
  domain: doctor-project.localhost
applications: {}
""",
        encoding="utf-8",
    )
    initialize_project(config, yia_root=ROOT)
    return load_project(config)


def _system_checks():
    return [
        {"name": "python", "status": "ok", "details": "3.14"},
        {"name": "git", "status": "ok", "details": "git"},
        {"name": "make", "status": "ok", "details": "make"},
        {"name": "docker", "status": "ok", "details": "docker"},
        {
            "name": "docker-compose",
            "status": "ok",
            "details": "compose",
        },
        {
            "name": "docker-daemon",
            "status": "ok",
            "details": "daemon",
        },
    ]


def test_doctor_validates_initialized_documentation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _initialized_project(tmp_path)
    monkeypatch.setattr(
        "yia.doctor.checks.installation_checks",
        lambda **_kwargs: _system_checks(),
    )
    monkeypatch.setattr("yia.doctor.checks.project_containers", lambda *_args: ())

    payload = run_checks(project, yia_root=ROOT)
    by_name = {check["name"]: check for check in payload["checks"]}

    assert by_name["documentation"] == {
        "name": "documentation",
        "status": "ok",
        "details": ".agents/docs",
    }
    assert by_name["generation"]["status"] == "ok"
    assert payload["status"] == "warning"


def test_doctor_reports_stale_documentation_without_exposing_content(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _initialized_project(tmp_path)
    generated = tmp_path / ".agents/docs/architecture/development-environment.md"
    generated.write_text("sensitive accidental content\n", encoding="utf-8")
    monkeypatch.setattr(
        "yia.doctor.checks.installation_checks",
        lambda **_kwargs: _system_checks(),
    )
    monkeypatch.setattr("yia.doctor.checks.project_containers", lambda *_args: ())

    payload = run_checks(project, yia_root=ROOT)
    documentation = next(
        check for check in payload["checks"] if check["name"] == "documentation"
    )

    assert documentation["status"] == "error"
    assert documentation["details"] == "YIA_GENERIC_ERROR"
    assert "sensitive accidental content" not in str(payload)
    assert payload["status"] == "error"
