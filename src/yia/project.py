from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from yia.config import NormalizedConfig, load_normalized_config
from yia.docker import COMPOSE_PATH, docker_generators
from yia.errors import ErrorCode, YiaError
from yia.generators import GenerationEngine, GenerationResult
from yia.resources import schema_path


@dataclass(frozen=True, slots=True)
class Project:
    config_path: Path
    config: NormalizedConfig

    @property
    def root(self) -> Path:
        return self.config.project_root

    @property
    def dotenv_path(self) -> Path:
        return self.root / ".env"

    @property
    def runtime_path(self) -> Path:
        return self.root / ".yia-runtime"

    @property
    def compose_path(self) -> Path:
        return self.runtime_path / COMPOSE_PATH


def _dotenv_value(path: Path, key: str) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le fichier .env ne peut pas être lu.",
            {"path": str(path), "error_type": type(exc).__name__},
        ) from exc

    value: str | None = None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, separator, candidate = line.partition("=")
        if not separator or name.strip() != key:
            continue
        candidate = candidate.strip()
        if (
            len(candidate) >= 2
            and candidate[0] == candidate[-1]
            and candidate[0] in {"'", '"'}
        ):
            candidate = candidate[1:-1]
        value = candidate
    return value


def validate_project_environment(project: Project) -> None:
    if project.config.services.postgres is None:
        return

    password = os.environ.get("POSTGRES_PASSWORD")
    if password is None:
        password = _dotenv_value(project.dotenv_path, "POSTGRES_PASSWORD")
    if password:
        return

    raise YiaError(
        ErrorCode.CONFIG_INVALID,
        "POSTGRES_PASSWORD doit être défini et non vide dans .env.",
        {
            "path": str(project.dotenv_path),
            "variable": "POSTGRES_PASSWORD",
            "constraint": "required_non_empty",
        },
    )


def validate_project_dependencies(project: Project) -> None:
    errors: list[dict[str, object]] = []
    for application in project.config.applications:
        if application.type != "node":
            continue
        package_path = application.path / "package.json"
        try:
            payload = json.loads(package_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            errors.append(
                {
                    "path": str(package_path),
                    "application": application.name,
                    "constraint": "required_file",
                }
            )
            continue
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(
                {
                    "path": str(package_path),
                    "application": application.name,
                    "constraint": "valid_json",
                    "error_type": type(exc).__name__,
                }
            )
            continue

        scripts = payload.get("scripts") if isinstance(payload, dict) else None
        dev = scripts.get("dev") if isinstance(scripts, dict) else None
        if not isinstance(dev, str) or not dev.strip():
            errors.append(
                {
                    "path": str(package_path),
                    "application": application.name,
                    "constraint": "non_empty_scripts_dev",
                }
            )

    if errors:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Les dépendances applicatives déclarées sont invalides.",
            {"validation_errors": errors},
        )


def load_project(
    config_path: str | Path,
    *,
    require_environment: bool = True,
) -> Project:
    resolved_config_path = Path(config_path).resolve()
    config = load_normalized_config(
        resolved_config_path,
        schema_path("yia.schema.json"),
    )
    project = Project(config_path=resolved_config_path, config=config)
    validate_project_dependencies(project)
    if require_environment:
        validate_project_environment(project)
    return project


def generation_engine() -> GenerationEngine:
    return GenerationEngine(docker_generators())


def generate_project(project: Project) -> GenerationResult:
    return generation_engine().generate(project.config)


def generation_is_current(project: Project) -> bool:
    return generation_engine().is_current(project.config)


def require_current_generation(project: Project) -> None:
    if generation_is_current(project):
        return
    raise YiaError(
        ErrorCode.GENERATION_FAILED,
        "Les artefacts Yia sont absents ou obsolètes.",
        {
            "path": str(project.runtime_path),
            "suggestion": "Exécuter make generate avant cette commande.",
        },
    )


def runtime_project_identity(config_path: str | Path) -> tuple[Path, str]:
    resolved_config = Path(config_path).resolve()
    root = resolved_config.parent
    compose_path = root / ".yia-runtime" / COMPOSE_PATH
    source = compose_path if compose_path.is_file() else resolved_config
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "L'identité du projet Yia ne peut pas être déterminée.",
            {"path": str(source), "error_type": type(exc).__name__},
        ) from exc

    name: object = None
    if source == compose_path and isinstance(payload, dict):
        name = payload.get("name")
    elif isinstance(payload, dict):
        project = payload.get("project")
        if isinstance(project, dict):
            name = project.get("name")
    if not isinstance(name, str) or not name:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le nom du projet Yia est absent ou invalide.",
            {"path": str(source)},
        )
    return root, name
