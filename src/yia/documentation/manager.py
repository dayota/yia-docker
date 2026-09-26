from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from yia.config import ApplicationConfig, NormalizedConfig
from yia.errors import ErrorCode, YiaError
from yia.resources import template_path
from yia.state import read_state
from yia.versions import DOCUMENTATION_SCHEMA_VERSION, YIA_VERSION


DOCS_ROOT = Path(".agents/docs")
SKILLS_ROOT = Path(".agents/skills")
INDEX_PATH = DOCS_ROOT / "INDEX.md"
DEVELOPMENT_ENVIRONMENT_PATH = (
    DOCS_ROOT / "architecture" / "development-environment.md"
)
AGENTS_PATH = Path("AGENTS.md")
AGENTS_START_MARKER = "<!-- YIA:DOCUMENTATION:START -->"
AGENTS_END_MARKER = "<!-- YIA:DOCUMENTATION:END -->"

_DIRECTORIES = (
    DOCS_ROOT / "architecture",
    DOCS_ROOT / "decisions",
    DOCS_ROOT / "standards",
    DOCS_ROOT / "domain",
    SKILLS_ROOT / "project-docs",
    SKILLS_ROOT / "update-project-docs",
)

_HUMAN_TEMPLATES = (
    ("documentation/INDEX.md", INDEX_PATH),
    ("documentation/decisions/README.md", DOCS_ROOT / "decisions/README.md"),
    ("documentation/glossary.md", DOCS_ROOT / "glossary.md"),
    ("skills/project-docs/SKILL.md", SKILLS_ROOT / "project-docs/SKILL.md"),
    (
        "skills/update-project-docs/SKILL.md",
        SKILLS_ROOT / "update-project-docs/SKILL.md",
    ),
)


@dataclass(frozen=True, slots=True)
class DocumentationResult:
    schema_version: int
    created: tuple[str, ...]
    updated: tuple[str, ...]
    preserved: tuple[str, ...]
    unchanged: tuple[str, ...]

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "changed": self.changed,
            "created": list(self.created),
            "updated": list(self.updated),
            "preserved": list(self.preserved),
            "unchanged": list(self.unchanged),
        }


def _display_path(project_root: Path, path: Path) -> str:
    return path.relative_to(project_root).as_posix()


def _ensure_safe_path(project_root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(project_root)
    except ValueError as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Un chemin documentaire sort du projet.",
            {"path": str(path)},
        ) from exc

    current = project_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise YiaError(
                ErrorCode.GENERIC,
                "Un chemin documentaire ne peut pas traverser un lien symbolique.",
                {"path": str(current)},
            )


def _write_if_changed(project_root: Path, path: Path, content: str) -> str:
    _ensure_safe_path(project_root, path)
    encoded = content.encode("utf-8")
    existed = path.exists()
    try:
        if path.is_file() and path.read_bytes() == encoded:
            return "unchanged"
        if existed and not path.is_file():
            raise YiaError(
                ErrorCode.GENERIC,
                "Le chemin documentaire attendu n'est pas un fichier.",
                {"path": str(path)},
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(encoded)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
    except YiaError:
        raise
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Un fichier documentaire ne peut pas être écrit.",
            {"path": str(path), "error_type": type(exc).__name__},
        ) from exc
    return "updated" if existed else "created"


def _install_if_missing(project_root: Path, source: Path, target: Path) -> str:
    _ensure_safe_path(project_root, target)
    try:
        if target.exists():
            if not target.is_file():
                raise YiaError(
                    ErrorCode.GENERIC,
                    "Le chemin documentaire attendu n'est pas un fichier.",
                    {"path": str(target)},
                )
            return "preserved"
        content = source.read_text(encoding="utf-8")
    except YiaError:
        raise
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Un template documentaire Yia ne peut pas être lu.",
            {"path": str(source), "error_type": type(exc).__name__},
        ) from exc
    return _write_if_changed(project_root, target, content)


def _project_relative_path(config: NormalizedConfig, path: Path) -> str:
    try:
        return path.relative_to(config.project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _framework(application: ApplicationConfig) -> str:
    framework = application.framework
    if framework is None:
        return "—"
    if framework.version is None:
        return framework.name
    return f"{framework.name} {framework.version}"


def _table(headers: tuple[str, ...], rows: Iterable[tuple[str, ...]]) -> list[str]:
    rendered_rows = tuple(rows)
    if not rendered_rows:
        return ["_Aucun._"]
    return [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(row) + " |" for row in rendered_rows),
    ]


def render_development_environment(config: NormalizedConfig) -> str:
    web_applications = tuple(
        application for application in config.applications if application.web
    )
    lines = [
        "# Environnement de développement",
        "",
        "> Ce document est généré par Yia à partir de `yia.yml`.",
        "> Ne pas le modifier manuellement.",
        "",
        "## Projet",
        "",
        f"- Nom : `{config.project.name}`",
        f"- Schéma `yia.yml` : `{config.schema_version}`",
        f"- Version Yia : `{YIA_VERSION}`",
        f"- Projet Docker Compose : `{config.project.compose_name}`",
        f"- Réseau Docker : `{config.project.compose_name}_yia`",
        (
            "- Reverse proxy : Apache, exposé sur le port hôte `80`"
            if web_applications
            else "- Reverse proxy : non activé (aucune application web)"
        ),
        "",
        "## Applications",
        "",
        *_table(
            ("Application", "Type", "Chemin", "Framework", "Runtime", "HTTP"),
            (
                (
                    f"`{application.name}`",
                    application.type,
                    f"`{_project_relative_path(config, application.path)}`",
                    _framework(application),
                    f"`{application.runtime.name}`",
                    (
                        f"http://{application.web.hostname}"
                        if application.web is not None
                        else "—"
                    ),
                )
                for application in config.applications
            ),
        ),
        "",
        "## Runtimes",
        "",
        *_table(
            ("Runtime", "Type", "Version", "Applications"),
            (
                (
                    f"`{runtime_name}`",
                    next(
                        application.runtime.type
                        for application in config.applications
                        if application.runtime.name == runtime_name
                    ),
                    next(
                        application.runtime.version
                        for application in config.applications
                        if application.runtime.name == runtime_name
                    ),
                    ", ".join(
                        f"`{application.name}`"
                        for application in config.applications
                        if application.runtime.name == runtime_name
                    ),
                )
                for runtime_name in config.runtime_names
            ),
        ),
        "",
        "## Services d'infrastructure",
        "",
    ]

    postgres = config.services.postgres
    service_rows: list[tuple[str, ...]] = []
    if postgres is not None:
        service_rows.append(
            (
                "`postgres`",
                postgres.version,
                "`5432:5432`" if postgres.expose else "réseau privé uniquement",
                "`postgres-data`",
            )
        )
    lines.extend(
        _table(("Service", "Version", "Exposition", "Volume"), service_rows)
    )

    volume_rows: list[tuple[str, ...]] = []
    if postgres is not None:
        volume_rows.append(("`postgres-data`", "données PostgreSQL"))
    for application in config.applications:
        if application.type == "php":
            volume_rows.append(
                (
                    f"`php-{application.name}-vendor`",
                    f"dépendances de `{application.name}`",
                )
            )
        else:
            volume_rows.append(
                (
                    f"`node-{application.name}-modules`",
                    f"dépendances de `{application.name}`",
                )
            )

    lines.extend(
        [
            "",
            "## Ports et hostnames",
            "",
            *_table(
                ("Composant", "Hostname", "Port", "Port hôte"),
                (
                    (
                        f"`{application.name}`",
                        f"`{application.web.hostname}`",
                        (
                            f"`{application.web.port}`"
                            if application.web.port is not None
                            else "PHP-FPM"
                        ),
                        "`80` via Apache",
                    )
                    for application in web_applications
                    if application.web is not None
                ),
            ),
            "",
            "## Volumes persistants",
            "",
            *_table(("Volume logique", "Usage"), volume_rows),
            "",
            "## Dépendances d'infrastructure",
            "",
            (
                "- Apache route les applications web vers leur runtime privé."
                if web_applications
                else "- Aucune dépendance de reverse proxy."
            ),
            (
                "- PostgreSQL est disponible sur le réseau Docker privé sous le nom `postgres`."
                if postgres is not None
                else "- Aucun service PostgreSQL déclaré."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _managed_agents_section() -> str:
    try:
        fragment = template_path("documentation", "AGENTS.fragment.md").read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le fragment AGENTS.md de Yia ne peut pas être lu.",
            {"error_type": type(exc).__name__},
        ) from exc
    return (
        f"{AGENTS_START_MARKER}\n"
        f"{fragment.strip()}\n"
        f"{AGENTS_END_MARKER}\n"
    )


def _merge_agents(project_root: Path) -> str:
    path = project_root / AGENTS_PATH
    _ensure_safe_path(project_root, path)
    try:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "AGENTS.md ne peut pas être lu.",
            {"path": str(path), "error_type": type(exc).__name__},
        ) from exc

    start_count = current.count(AGENTS_START_MARKER)
    end_count = current.count(AGENTS_END_MARKER)
    if start_count != end_count or start_count > 1:
        raise YiaError(
            ErrorCode.GENERIC,
            "La section documentaire gérée dans AGENTS.md est ambiguë.",
            {
                "path": str(path),
                "start_markers": start_count,
                "end_markers": end_count,
            },
        )
    if (
        start_count == 1
        and current.index(AGENTS_END_MARKER) < current.index(AGENTS_START_MARKER)
    ):
        raise YiaError(
            ErrorCode.GENERIC,
            "La section documentaire gérée dans AGENTS.md est ambiguë.",
            {
                "path": str(path),
                "constraint": "ordered_markers",
            },
        )

    section = _managed_agents_section()
    if start_count == 1:
        start = current.index(AGENTS_START_MARKER)
        end = current.index(AGENTS_END_MARKER, start) + len(AGENTS_END_MARKER)
        merged = current[:start] + section.rstrip("\n") + current[end:]
        if current.endswith("\n") and not merged.endswith("\n"):
            merged += "\n"
    elif current:
        merged = current.rstrip() + "\n\n" + section
    else:
        merged = "# Instructions du projet\n\n" + section
    return _write_if_changed(project_root, path, merged)


def sync_documentation(config: NormalizedConfig) -> DocumentationResult:
    project_root = config.project_root.resolve()
    created: list[str] = []
    updated: list[str] = []
    preserved: list[str] = []
    unchanged: list[str] = []
    buckets = {
        "created": created,
        "updated": updated,
        "preserved": preserved,
        "unchanged": unchanged,
    }

    for relative_directory in _DIRECTORIES:
        directory = project_root / relative_directory
        _ensure_safe_path(project_root, directory)
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise YiaError(
                ErrorCode.GENERIC,
                "La structure documentaire ne peut pas être créée.",
                {"path": str(directory), "error_type": type(exc).__name__},
            ) from exc

    for template_name, relative_target in _HUMAN_TEMPLATES:
        target = project_root / relative_target
        outcome = _install_if_missing(
            project_root,
            template_path(*template_name.split("/")),
            target,
        )
        buckets[outcome].append(_display_path(project_root, target))

    derived_path = project_root / DEVELOPMENT_ENVIRONMENT_PATH
    derived_outcome = _write_if_changed(
        project_root,
        derived_path,
        render_development_environment(config),
    )
    buckets[derived_outcome].append(_display_path(project_root, derived_path))

    agents_outcome = _merge_agents(project_root)
    buckets[agents_outcome].append(AGENTS_PATH.as_posix())

    return DocumentationResult(
        schema_version=DOCUMENTATION_SCHEMA_VERSION,
        created=tuple(sorted(created)),
        updated=tuple(sorted(updated)),
        preserved=tuple(sorted(preserved)),
        unchanged=tuple(sorted(unchanged)),
    )


def install_documentation(config: NormalizedConfig) -> DocumentationResult:
    return sync_documentation(config)


def update_documentation(config: NormalizedConfig) -> DocumentationResult:
    return sync_documentation(config)


def validate_documentation(config: NormalizedConfig) -> None:
    project_root = config.project_root.resolve()
    missing: list[str] = []
    for relative_directory in _DIRECTORIES:
        if not (project_root / relative_directory).is_dir():
            missing.append(relative_directory.as_posix() + "/")
    for _, relative_file in _HUMAN_TEMPLATES:
        if not (project_root / relative_file).is_file():
            missing.append(relative_file.as_posix())
    if not (project_root / AGENTS_PATH).is_file():
        missing.append(AGENTS_PATH.as_posix())

    errors: list[dict[str, object]] = []
    if missing:
        errors.append({"constraint": "required_paths", "paths": sorted(missing)})

    agents_path = project_root / AGENTS_PATH
    if agents_path.is_file():
        try:
            agents = agents_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                {
                    "constraint": "readable_agents_file",
                    "path": AGENTS_PATH.as_posix(),
                    "error_type": type(exc).__name__,
                }
            )
        else:
            if (
                agents.count(AGENTS_START_MARKER) != 1
                or agents.count(AGENTS_END_MARKER) != 1
            ):
                errors.append(
                    {
                        "constraint": "single_managed_agents_section",
                        "path": AGENTS_PATH.as_posix(),
                    }
                )
            elif _managed_agents_section().rstrip("\n") not in agents:
                errors.append(
                    {
                        "constraint": "managed_agents_rules_current",
                        "path": AGENTS_PATH.as_posix(),
                    }
                )

    derived_path = project_root / DEVELOPMENT_ENVIRONMENT_PATH
    expected = render_development_environment(config)
    try:
        derived_is_current = (
            derived_path.is_file()
            and derived_path.read_text(encoding="utf-8") == expected
        )
        if not derived_is_current:
            errors.append(
                {
                    "constraint": "derived_document_current",
                    "path": DEVELOPMENT_ENVIRONMENT_PATH.as_posix(),
                }
            )
    except (OSError, UnicodeError) as exc:
        errors.append(
            {
                "constraint": "readable_derived_document",
                "path": DEVELOPMENT_ENVIRONMENT_PATH.as_posix(),
                "error_type": type(exc).__name__,
            }
        )

    state = read_state(project_root)
    if (
        state is not None
        and state.documentation_schema_version != DOCUMENTATION_SCHEMA_VERSION
    ):
        errors.append(
            {
                "constraint": "documentation_schema_version",
                "current_version": state.documentation_schema_version,
                "expected_version": DOCUMENTATION_SCHEMA_VERSION,
            }
        )

    if (project_root / ".yia/.agents/docs").exists():
        errors.append(
            {
                "constraint": "no_project_documentation_in_yia",
                "path": ".yia/.agents/docs",
            }
        )

    if errors:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le système documentaire du projet est invalide.",
            {"validation_errors": errors},
        )
