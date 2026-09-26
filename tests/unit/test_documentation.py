from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from yia.config import normalize_config
from yia.documentation import (
    AGENTS_END_MARKER,
    AGENTS_START_MARKER,
    DEVELOPMENT_ENVIRONMENT_PATH,
    install_documentation,
    update_documentation,
    validate_documentation,
)
from yia.errors import ErrorCode, YiaError
from yia.state import YiaState, write_state


def _config(project_root: Path, *, domain: str = "demo.localhost"):
    return normalize_config(
        {
            "version": 1,
            "project": {"name": "demo"},
            "environment": {"domain": domain},
            "services": {
                "postgres": {
                    "enabled": True,
                    "version": "18",
                    "expose": False,
                }
            },
            "applications": {
                "api": {
                    "type": "php",
                    "path": "apps/api",
                    "runtime": {"php": "8.4"},
                    "framework": {"name": "laravel", "version": 13},
                    "web": {
                        "hostname": f"api.{domain}",
                        "public_directory": "public",
                    },
                },
                "frontend": {
                    "type": "node",
                    "path": "apps/frontend",
                    "runtime": {"node": "24", "package_manager": "pnpm"},
                    "framework": {"name": "nuxt", "version": 4},
                    "web": {"hostname": domain, "port": 3000},
                },
            },
        },
        project_root=project_root,
    )


def _snapshot(root: Path) -> dict[str, tuple[bytes, int, int]]:
    return {
        path.relative_to(root).as_posix(): (
            path.read_bytes(),
            path.stat().st_ino,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_install_creates_minimal_documentation_structure(tmp_path: Path) -> None:
    result = install_documentation(_config(tmp_path))

    expected_files = {
        ".agents/docs/INDEX.md",
        ".agents/docs/architecture/development-environment.md",
        ".agents/docs/decisions/README.md",
        ".agents/docs/glossary.md",
        ".agents/skills/project-docs/SKILL.md",
        ".agents/skills/update-project-docs/SKILL.md",
        "AGENTS.md",
    }
    assert expected_files == {
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert (tmp_path / ".agents/docs/standards").is_dir()
    assert (tmp_path / ".agents/docs/domain").is_dir()
    assert result.schema_version == 1
    assert result.changed is True
    assert set(result.created) == expected_files
    validate_documentation(_config(tmp_path))


def test_install_is_idempotent_and_does_not_rewrite_files(tmp_path: Path) -> None:
    config = _config(tmp_path)
    install_documentation(config)
    first = _snapshot(tmp_path)

    result = update_documentation(config)

    assert result.changed is False
    assert _snapshot(tmp_path) == first
    assert DEVELOPMENT_ENVIRONMENT_PATH.as_posix() in result.unchanged
    assert "AGENTS.md" in result.unchanged


def test_human_documents_and_custom_skills_are_preserved(tmp_path: Path) -> None:
    config = _config(tmp_path)
    install_documentation(config)
    custom_files = {
        ".agents/docs/INDEX.md": "# Index personnalisé\n",
        ".agents/docs/glossary.md": "# Vocabulaire métier\n\nSecret métier public.\n",
        ".agents/docs/architecture/product.md": "# Architecture humaine\n",
        ".agents/skills/project-docs/SKILL.md": "# Skill personnalisé\n",
        ".agents/skills/update-project-docs/SKILL.md": "# Mise à jour personnalisée\n",
    }
    for relative_path, content in custom_files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    result = update_documentation(config)

    for relative_path, content in custom_files.items():
        assert (tmp_path / relative_path).read_text(encoding="utf-8") == content
    assert ".agents/skills/project-docs/SKILL.md" in result.preserved
    assert ".agents/skills/update-project-docs/SKILL.md" in result.preserved


def test_config_change_only_regenerates_derived_document(tmp_path: Path) -> None:
    config = _config(tmp_path)
    install_documentation(config)
    human_path = tmp_path / ".agents/docs/architecture/product.md"
    human_path.write_text("# À préserver\n", encoding="utf-8")
    before = (tmp_path / DEVELOPMENT_ENVIRONMENT_PATH).read_text(encoding="utf-8")

    result = update_documentation(_config(tmp_path, domain="changed.localhost"))

    after = (tmp_path / DEVELOPMENT_ENVIRONMENT_PATH).read_text(encoding="utf-8")
    assert before != after
    assert "changed.localhost" in after
    assert human_path.read_text(encoding="utf-8") == "# À préserver\n"
    assert result.updated == (DEVELOPMENT_ENVIRONMENT_PATH.as_posix(),)


def test_derived_document_describes_environment_without_dotenv_secret(
    tmp_path: Path,
) -> None:
    secret = "must-never-be-documented"
    (tmp_path / ".env").write_text(f"POSTGRES_PASSWORD={secret}\n", encoding="utf-8")

    install_documentation(_config(tmp_path))

    content = (tmp_path / DEVELOPMENT_ENVIRONMENT_PATH).read_text(encoding="utf-8")
    assert "`demo`" in content
    assert "laravel 13" in content
    assert "nuxt 4" in content
    assert "`php-8.4`" in content
    assert "`node-24`" in content
    assert "api.demo.localhost" in content
    assert "`postgres-data`" in content
    assert "POSTGRES_PASSWORD" not in content
    assert secret not in content
    assert str(tmp_path) not in content


def test_agents_merge_preserves_user_content_without_duplication(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# Règles humaines\n\nToujours tester.\n", encoding="utf-8")
    config = _config(tmp_path)

    install_documentation(config)
    first = agents.read_text(encoding="utf-8")
    update_documentation(config)

    assert agents.read_text(encoding="utf-8") == first
    assert first.startswith("# Règles humaines\n\nToujours tester.\n")
    assert first.count(AGENTS_START_MARKER) == 1
    assert first.count(AGENTS_END_MARKER) == 1


def test_agents_managed_section_is_updated_and_outside_content_is_preserved(
    tmp_path: Path,
) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "Avant\n\n"
        f"{AGENTS_START_MARKER}\nAnciennes règles\n{AGENTS_END_MARKER}\n\n"
        "Après\n",
        encoding="utf-8",
    )

    result = update_documentation(_config(tmp_path))

    content = agents.read_text(encoding="utf-8")
    assert content.startswith("Avant\n\n")
    assert content.endswith("\n\nAprès\n")
    assert "Anciennes règles" not in content
    assert "utiliser le skill\n`project-docs`" in content
    assert "AGENTS.md" in result.updated


def test_ambiguous_agents_markers_fail_without_modifying_file(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    original = f"{AGENTS_START_MARKER}\nsection incomplète\n"
    agents.write_text(original, encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        install_documentation(_config(tmp_path))

    assert caught.value.code is ErrorCode.GENERIC
    assert caught.value.details["start_markers"] == 1
    assert caught.value.details["end_markers"] == 0
    assert agents.read_text(encoding="utf-8") == original


def test_validation_detects_stale_derived_document(tmp_path: Path) -> None:
    config = _config(tmp_path)
    install_documentation(config)
    path = tmp_path / DEVELOPMENT_ENVIRONMENT_PATH
    path.write_text("modification manuelle", encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        validate_documentation(config)

    assert caught.value.code is ErrorCode.GENERIC
    assert {
        "constraint": "derived_document_current",
        "path": DEVELOPMENT_ENVIRONMENT_PATH.as_posix(),
    } in caught.value.details["validation_errors"]


def test_validation_detects_tampered_managed_agents_rules(tmp_path: Path) -> None:
    config = _config(tmp_path)
    install_documentation(config)
    path = tmp_path / "AGENTS.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Ne jamais stocker de secret dans la documentation.",
            "Règle supprimée.",
        ),
        encoding="utf-8",
    )

    with pytest.raises(YiaError) as caught:
        validate_documentation(config)

    assert {
        "constraint": "managed_agents_rules_current",
        "path": "AGENTS.md",
    } in caught.value.details["validation_errors"]


def test_validation_detects_documentation_schema_conflict(tmp_path: Path) -> None:
    config = _config(tmp_path)
    install_documentation(config)
    write_state(
        tmp_path,
        replace(
            YiaState.from_config(config),
            documentation_schema_version=2,
        ),
    )

    with pytest.raises(YiaError) as caught:
        validate_documentation(config)

    assert {
        "constraint": "documentation_schema_version",
        "current_version": 2,
        "expected_version": 1,
    } in caught.value.details["validation_errors"]


def test_documentation_does_not_follow_symlinks_outside_project(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / ".agents").symlink_to(outside, target_is_directory=True)

    with pytest.raises(YiaError) as caught:
        install_documentation(_config(tmp_path))

    assert caught.value.code is ErrorCode.GENERIC
    assert not list(outside.iterdir())
