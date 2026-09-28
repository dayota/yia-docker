from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from yia.documentation import (
    DocumentationResult,
    install_documentation,
    validate_documentation,
)
from yia.errors import ErrorCode, YiaError
from yia.project import (
    Project,
    generate_project,
    generation_is_current,
    load_project,
    validate_project_environment,
)
from yia.resources import template_path


_PROJECT_FILES = (Path("Makefile"), Path(".env.example"), Path(".env"))


@dataclass(frozen=True, slots=True)
class InitializationResult:
    project: str
    config_path: str
    created_project_files: tuple[str, ...]
    preserved_project_files: tuple[str, ...]
    generation_changed: bool
    documentation: DocumentationResult
    applications: tuple[str, ...]
    runtimes: tuple[str, ...]
    services: tuple[str, ...]
    urls: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "ok",
            "project": self.project,
            "config": self.config_path,
            "created_project_files": list(self.created_project_files),
            "preserved_project_files": list(self.preserved_project_files),
            "generation": {
                "changed": self.generation_changed,
                "status": "current",
            },
            "documentation": self.documentation.to_dict(),
            "applications": list(self.applications),
            "runtimes": list(self.runtimes),
            "services": list(self.services),
            "urls": list(self.urls),
            "next_command": "make up",
        }


def _verify_yia_submodule(project_root: Path, yia_root: Path) -> None:
    submodule = project_root / ".yia"
    try:
        valid = submodule.is_dir() and submodule.resolve() == yia_root.resolve()
    except OSError:
        valid = False
    if valid:
        return
    raise YiaError(
        ErrorCode.DEPENDENCY_MISSING,
        "Le sous-module Yia attendu dans .yia est absent ou invalide.",
        {
            "dependency": ".yia",
            "path": str(submodule),
            "expected": str(yia_root.resolve()),
        },
    )


def _check_project_file(path: Path) -> bool:
    if path.is_symlink():
        raise YiaError(
            ErrorCode.GENERIC,
            "Un fichier projet géré par init ne peut pas être un lien symbolique.",
            {"path": str(path)},
        )
    if not path.exists():
        return False
    if not path.is_file():
        raise YiaError(
            ErrorCode.GENERIC,
            "Le chemin projet attendu n'est pas un fichier.",
            {"path": str(path)},
        )
    return True


def _create_file(path: Path, content: bytes) -> bool:
    if _check_project_file(path):
        return False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
    except FileExistsError:
        if _check_project_file(path):
            return False
        raise
    except YiaError:
        raise
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Un fichier projet requis par init ne peut pas être créé.",
            {"path": str(path), "error_type": type(exc).__name__},
        ) from exc
    return True


def _read_template(*parts: str) -> bytes:
    source = template_path(*parts)
    try:
        return source.read_bytes()
    except OSError as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Un template projet Yia ne peut pas être lu.",
            {"path": str(source), "error_type": type(exc).__name__},
        ) from exc


def _sync_project_files(project_root: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    contents = (
        (Path("Makefile"), _read_template("project", "Makefile")),
        (Path(".env.example"), _read_template("project", ".env.example")),
    )
    created: list[str] = []
    preserved: list[str] = []

    for relative_path, content in contents:
        target = project_root / relative_path
        bucket = created if _create_file(target, content) else preserved
        bucket.append(relative_path.as_posix())

    dotenv_example = project_root / ".env.example"
    try:
        dotenv_content = dotenv_example.read_bytes()
    except OSError as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            ".env.example ne peut pas être lu pour initialiser .env.",
            {
                "path": str(dotenv_example),
                "error_type": type(exc).__name__,
            },
        ) from exc
    dotenv = project_root / ".env"
    bucket = created if _create_file(dotenv, dotenv_content) else preserved
    bucket.append(".env")

    return tuple(sorted(created)), tuple(sorted(preserved))


def _is_initialized(project: Project) -> bool:
    for relative_path in _PROJECT_FILES:
        path = project.root / relative_path
        if path.is_symlink() or not path.is_file():
            return False
    if not generation_is_current(project):
        return False
    try:
        validate_documentation(project.config)
    except YiaError:
        return False
    return True


def _assert_final_state(project: Project) -> None:
    if not generation_is_current(project):
        raise YiaError(
            ErrorCode.GENERATION_FAILED,
            "L'initialisation n'a pas produit un runtime Yia cohérent.",
            {"path": str(project.runtime_path)},
        )
    validate_documentation(project.config)


def initialize_project(
    config_path: str | Path,
    *,
    yia_root: Path,
) -> InitializationResult:
    resolved_config = Path(config_path).resolve()
    project_root = resolved_config.parent
    _verify_yia_submodule(project_root, yia_root)

    # La source managed peut être absente avant le clonage.
    project = load_project(resolved_config, require_environment=False, require_dependencies=False)
    if _is_initialized(project):
        raise YiaError(
            ErrorCode.GENERIC,
            "Le projet Yia est déjà initialisé.",
            {
                "project": project.config.project.name,
                "suggestion": "Exécuter make update pour synchroniser le projet.",
            },
        )

    from yia.sources import synchronize_sources
    from yia.project import validate_project_dependencies

    synchronize_sources(project.config)
    validate_project_dependencies(project, allow_missing_managed=False)
    created, preserved = _sync_project_files(project.root)
    validate_project_environment(project)

    documentation = install_documentation(project.config)
    generation = generate_project(project)
    _assert_final_state(project)

    postgres = project.config.services.postgres
    return InitializationResult(
        project=project.config.project.name,
        config_path=str(project.config_path),
        created_project_files=created,
        preserved_project_files=preserved,
        generation_changed=generation.changed,
        documentation=documentation,
        applications=tuple(
            application.name for application in project.config.applications
        ),
        runtimes=project.config.runtime_names,
        services=("postgres",) if postgres is not None else (),
        urls=tuple(
            sorted(
                f"http://{application.web.hostname}"
                for application in project.config.applications
                if application.web is not None
            )
        ),
    )


__all__ = ["InitializationResult", "initialize_project"]
