import json
from pathlib import Path

from yia.cli import build_parser, default_schema_path, main


ROOT = Path(__file__).resolve().parents[2]


def test_configuration_schema_is_available() -> None:
    assert default_schema_path().is_file()


def test_version_command(capsys) -> None:
    exit_code = main(["version"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("Yia 0.1.0\n")
    assert captured.err == ""


def test_validate_json_success_contains_only_json_on_stdout(
    monkeypatch,
    capsys,
) -> None:
    project_root = ROOT / "tests" / "projects" / "minimal"
    monkeypatch.chdir(project_root)

    exit_code = main(["validate", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert captured.err == ""
    assert captured.out.count("\n") == 1


def test_validate_json_error_is_structured_and_uses_exit_code_2(
    monkeypatch,
    capsys,
) -> None:
    project_root = ROOT / "tests" / "projects" / "invalid"
    monkeypatch.chdir(project_root)

    exit_code = main(["validate", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "YIA_CONFIG_INVALID"
    assert payload["error"]["details"]["expected_schema_version"] == 1
    assert captured.err == ""
    assert captured.out.count("\n") == 1


def test_validate_human_error_is_written_to_stderr(monkeypatch, capsys) -> None:
    project_root = ROOT / "tests" / "projects" / "invalid"
    monkeypatch.chdir(project_root)

    exit_code = main(["validate"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "YIA_CONFIG_INVALID" in captured.err


def test_public_cli_commands_are_registered() -> None:
    parser = build_parser()
    commands = next(
        action.choices
        for action in parser._actions
        if hasattr(action, "choices") and action.choices
    )

    assert set(commands) == {
        "build",
        "check-install",
        "clean",
        "config",
        "destroy",
        "destroy-data",
        "doctor",
        "down",
        "exec",
        "generate",
        "init",
        "install",
        "logs",
        "ps",
        "rebuild",
        "reset",
        "restart",
        "shell",
        "status",
        "test",
        "up",
        "update",
        "validate",
        "version",
    }


def test_config_displays_normalized_model_without_dotenv_values(
    tmp_path: Path,
    capsys,
) -> None:
    (tmp_path / "yia.yml").write_text(
        """version: 1
project:
  name: safe-config
environment:
  domain: safe-config.localhost
services:
  postgres:
    version: "18"
applications: {}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=must-not-appear\n",
        encoding="utf-8",
    )

    exit_code = main(["config", "--config", str(tmp_path / "yia.yml")])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["services"]["postgres"]["version"] == "18"
    assert "must-not-appear" not in captured.out


def test_validate_rejects_missing_postgres_password_as_structured_json(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    (tmp_path / "yia.yml").write_text(
        """version: 1
project:
  name: missing-secret
environment:
  domain: missing-secret.localhost
services:
  postgres:
    version: "18"
applications: {}
""",
        encoding="utf-8",
    )

    exit_code = main(
        ["validate", "--config", str(tmp_path / "yia.yml"), "--json"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 2
    assert payload["error"]["code"] == "YIA_CONFIG_INVALID"
    assert payload["error"]["details"]["variable"] == "POSTGRES_PASSWORD"
    assert captured.err == ""


def test_clean_removes_only_generated_runtime(tmp_path: Path, capsys) -> None:
    (tmp_path / ".yia-runtime" / "state").mkdir(parents=True)
    (tmp_path / ".yia-runtime" / "state" / "file").write_text("generated")
    (tmp_path / ".yia-data").mkdir()
    (tmp_path / ".yia-data" / "persistent").write_text("keep")
    (tmp_path / ".env").write_text("SECRET=keep\n")

    exit_code = main(["clean", "--config", str(tmp_path / "yia.yml")])

    assert exit_code == 0
    assert not (tmp_path / ".yia-runtime").exists()
    assert (tmp_path / ".yia-data" / "persistent").read_text() == "keep"
    assert (tmp_path / ".env").read_text() == "SECRET=keep\n"
    assert capsys.readouterr().err == ""


def test_destroy_data_requires_explicit_confirmation_and_targets_project_volumes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    source = ROOT / "tests" / "projects" / "minimal" / "yia.yml"
    config = tmp_path / "yia.yml"
    config.write_bytes(source.read_bytes())
    removed: list[tuple[str, ...]] = []
    environments: list[str] = []
    monkeypatch.setattr(
        "yia.cli.project_volumes",
        lambda _root, _name: ("minimal_postgres-data",),
    )
    monkeypatch.setattr(
        "yia.cli.remove_project_environment",
        lambda _root, name: environments.append(name),
    )
    monkeypatch.setattr(
        "yia.cli.remove_project_volumes",
        lambda _root, volumes: removed.append(tuple(volumes)),
    )

    exit_code = main(
        ["destroy-data", "--config", str(config), "--yes"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert environments == ["minimal"]
    assert removed == [("minimal_postgres-data",)]
    assert "minimal_postgres-data" in captured.out


def test_status_json_distinguishes_stale_and_stopped_environment(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    source = ROOT / "tests" / "projects" / "minimal" / "yia.yml"
    config = tmp_path / "yia.yml"
    config.write_bytes(source.read_bytes())
    monkeypatch.setattr("yia.cli.generation_is_current", lambda _project: False)
    monkeypatch.setattr("yia.cli.project_containers", lambda _root, _name: ())

    exit_code = main(["status", "--config", str(config), "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "warning"
    assert payload["generation"] == "stale"
    assert payload["environment"] == "stopped"
    assert payload["versions"]["yia"] == "0.1.0"
    assert captured.err == ""
