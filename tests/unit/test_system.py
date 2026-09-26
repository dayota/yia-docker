from pathlib import Path

import pytest

from yia.errors import ErrorCode, YiaError
from yia.system import install_dependencies, installation_checks


def test_install_rejects_non_apt_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("yia.system.shutil.which", lambda _name: None)

    with pytest.raises(YiaError) as caught:
        install_dependencies()

    assert caught.value.code is ErrorCode.DEPENDENCY_MISSING
    assert caught.value.details == {"dependency": "apt-get"}


def test_check_install_reports_missing_docker_without_running_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    available = {"git": "/usr/bin/git", "make": "/usr/bin/make"}
    monkeypatch.setattr(
        "yia.system.shutil.which",
        lambda name: available.get(name),
    )

    checks = installation_checks(project_root=tmp_path, yia_root=tmp_path)
    by_name = {check["name"]: check for check in checks}

    assert by_name["docker"]["status"] == "error"
    assert by_name["docker-compose"]["status"] == "error"
    assert by_name["docker-daemon"]["status"] == "error"
