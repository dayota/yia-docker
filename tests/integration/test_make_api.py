import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_consumer_make_validate_json_has_clean_stdout(tmp_path: Path) -> None:
    shutil.copy(ROOT / "templates" / "project" / "Makefile", tmp_path / "Makefile")
    shutil.copy(ROOT / "templates" / "project" / "yia.yml", tmp_path / "yia.yml")
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
