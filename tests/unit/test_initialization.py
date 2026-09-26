from __future__ import annotations

from pathlib import Path

import pytest

from yia.documentation import validate_documentation
from yia.errors import ErrorCode, YiaError
from yia.initialization import initialize_project
from yia.project import generation_is_current, load_project


ROOT = Path(__file__).resolve().parents[2]


def _minimal_project(root: Path) -> Path:
    (root / ".yia").symlink_to(ROOT, target_is_directory=True)
    config = root / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: initialized
environment:
  domain: initialized.localhost
applications: {}
""",
        encoding="utf-8",
    )
    return config


def _file_snapshot(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".yia" not in path.relative_to(root).parts
    }


def test_initialize_assembles_project_files_documentation_and_runtime(
    tmp_path: Path,
) -> None:
    config_path = _minimal_project(tmp_path)

    result = initialize_project(config_path, yia_root=ROOT)

    assert result.project == "initialized"
    assert result.generation_changed is True
    assert result.documentation.changed is True
    assert set(result.created_project_files) == {
        ".env",
        ".env.example",
        "Makefile",
    }
    assert (tmp_path / "Makefile").read_bytes() == (
        ROOT / "templates/project/Makefile"
    ).read_bytes()
    assert (tmp_path / ".env").read_bytes() == (
        tmp_path / ".env.example"
    ).read_bytes()
    assert (tmp_path / ".yia-runtime/compose/compose.yaml").is_file()
    assert not (tmp_path / ".yia-data").exists()

    project = load_project(config_path)
    assert generation_is_current(project) is True
    validate_documentation(project.config)


def test_initialize_preserves_existing_project_files_and_human_content(
    tmp_path: Path,
) -> None:
    config_path = _minimal_project(tmp_path)
    (tmp_path / "Makefile").write_text("# Makefile humain\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("CUSTOM=\n", encoding="utf-8")
    (tmp_path / ".env").write_text("CUSTOM=local-value\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        "# Règles humaines\n\nConserver cette règle.\n",
        encoding="utf-8",
    )

    result = initialize_project(config_path, yia_root=ROOT)

    assert result.created_project_files == ()
    assert result.preserved_project_files == (
        ".env",
        ".env.example",
        "Makefile",
    )
    assert (tmp_path / "Makefile").read_text() == "# Makefile humain\n"
    assert (tmp_path / ".env.example").read_text() == "CUSTOM=\n"
    assert (tmp_path / ".env").read_text() == "CUSTOM=local-value\n"
    assert "Conserver cette règle." in (tmp_path / "AGENTS.md").read_text()


def test_second_init_is_refused_without_rewriting_project(tmp_path: Path) -> None:
    config_path = _minimal_project(tmp_path)
    initialize_project(config_path, yia_root=ROOT)
    before = _file_snapshot(tmp_path)

    with pytest.raises(YiaError) as caught:
        initialize_project(config_path, yia_root=ROOT)

    assert caught.value.code is ErrorCode.GENERIC
    assert caught.value.details == {
        "project": "initialized",
        "suggestion": "Exécuter make update pour synchroniser le projet.",
    }
    assert _file_snapshot(tmp_path) == before


def test_invalid_config_is_rejected_before_any_project_file_is_created(
    tmp_path: Path,
) -> None:
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    config = tmp_path / "yia.yml"
    config.write_text("version: 999\n", encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        initialize_project(config, yia_root=ROOT)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert {path.name for path in tmp_path.iterdir()} == {".yia", "yia.yml"}


def test_init_requires_the_expected_read_only_yia_submodule(tmp_path: Path) -> None:
    config = tmp_path / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: missing-yia
environment:
  domain: missing-yia.localhost
applications: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(YiaError) as caught:
        initialize_project(config, yia_root=ROOT)

    assert caught.value.code is ErrorCode.DEPENDENCY_MISSING
    assert caught.value.details["dependency"] == ".yia"
    assert not (tmp_path / "Makefile").exists()


def test_init_creates_dotenv_then_reports_required_postgres_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    (tmp_path / ".yia").symlink_to(ROOT, target_is_directory=True)
    config = tmp_path / "yia.yml"
    config.write_text(
        """version: 1
project:
  name: database
environment:
  domain: database.localhost
services:
  postgres:
    version: "18"
applications: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(YiaError) as caught:
        initialize_project(config, yia_root=ROOT)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.details["variable"] == "POSTGRES_PASSWORD"
    assert (tmp_path / ".env").is_file()
    assert "POSTGRES_PASSWORD=" in (tmp_path / ".env").read_text()
    assert not (tmp_path / ".yia-runtime").exists()
    assert not (tmp_path / ".agents").exists()


def test_init_rejects_project_file_symlinks(tmp_path: Path) -> None:
    config_path = _minimal_project(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside-env"
    outside.write_text("DO_NOT_COPY=outside\n", encoding="utf-8")
    (tmp_path / ".env.example").symlink_to(outside)

    with pytest.raises(YiaError) as caught:
        initialize_project(config_path, yia_root=ROOT)

    assert caught.value.code is ErrorCode.GENERIC
    assert caught.value.details["path"] == str(tmp_path / ".env.example")
    assert not (tmp_path / ".env").exists()
