import json
from pathlib import Path

from yia.cli import default_schema_path, main


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
