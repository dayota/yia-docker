from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path

from yia.config.model import ApplicationConfig, NormalizedConfig, OnceHookConfig
from yia.docker.node import node_service_name
from yia.docker.python import python_service_name
from yia.errors import ErrorCode, YiaError


def check_postgres_sql(config: NormalizedConfig, compose: object) -> None:
    postgres = config.services.postgres
    if postgres is None or postgres.init_sql is None:
        return
    try:
        expected = hashlib.sha256(postgres.init_sql.read_bytes()).hexdigest()
    except OSError as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le fichier SQL d'initialisation ne peut pas être lu.",
            {"path": str(postgres.init_sql), "error_type": type(exc).__name__},
        ) from exc
    try:
        result = compose.run(
            [
                "exec", "-T", "postgres", "sh", "-c",
                'cat "$PGDATA/.yia-init-sql.sha256"',
            ],
            capture_output=True,
            operation="postgres-init-sql-status",
        )
    except YiaError as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le volume PostgreSQL n'a pas confirmé l'exécution du SQL initial. "
            "Ne pas réinitialiser le volume sans décision explicite.",
            {"path": str(postgres.init_sql), "constraint": "sql_initialization_marker"},
        ) from exc
    if result.stdout.strip() != expected:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le fichier SQL diffère de celui exécuté lors de la création du volume.",
            {"path": str(postgres.init_sql), "constraint": "sql_initialization_immutable"},
        )


def _application_service(application: ApplicationConfig) -> str:
    if application.type == "php":
        return application.runtime.name
    if application.type == "node":
        return node_service_name(application)
    return python_service_name(application)


def _once(
    config: NormalizedConfig,
    compose: object,
    *,
    scope: str,
    service: str,
    hook: OnceHookConfig,
    script_in_container: str,
    working_directory: str | None = None,
) -> None:
    marker_root = config.project_root / ".yia-data" / "once"
    if marker_root.is_symlink() or marker_root.parent.is_symlink():
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le répertoire des marqueurs d'initialisation ne peut pas être un lien symbolique.",
            {"path": str(marker_root)},
        )
    try:
        marker_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Impossible de préparer les marqueurs d'initialisation.",
            {"path": str(marker_root), "error_type": type(exc).__name__},
        ) from exc
    key = hashlib.sha256(f"{scope}\0{hook.id}".encode("utf-8")).hexdigest()
    marker = marker_root / f"{key}.done"
    lock = marker_root / f"{key}.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(lock, flags, 0o600)
        with os.fdopen(descriptor, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            if marker.is_symlink():
                raise YiaError(
                    ErrorCode.CONFIG_INVALID,
                    "Le marqueur d'initialisation est un lien symbolique.",
                    {"path": str(marker)},
                )
            if marker.exists():
                return
            arguments = ["exec", "-T"]
            if working_directory is not None:
                arguments.extend(["--workdir", working_directory])
            arguments.extend([service, "sh", script_in_container])
            try:
                compose.run(
                    arguments,
                    capture_output=True,
                    operation="initialization-once",
                )
            except YiaError as exc:
                raise YiaError(
                    ErrorCode.GENERATION_FAILED,
                    "Le script d'initialisation a échoué ; il pourra être relancé. "
                    "Vérifier ses éventuels effets partiels avant de réessayer.",
                    {"scope": scope, "id": hook.id, "service": service},
                ) from exc
            temporary = marker_root / f"{key}.tmp-{os.getpid()}"
            try:
                with temporary.open("x", encoding="utf-8") as handle:
                    handle.write(f"{scope}:{hook.id}\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(marker)
            finally:
                temporary.unlink(missing_ok=True)
    except OSError as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Impossible d'enregistrer l'initialisation du service ou de l'application.",
            {"scope": scope, "id": hook.id, "error_type": type(exc).__name__},
        ) from exc


def run_initialization_hooks(config: NormalizedConfig, compose: object) -> None:
    """Run after Compose has made services healthy; never during make init."""
    check_postgres_sql(config, compose)
    postgres = config.services.postgres
    if postgres is not None and postgres.once is not None:
        _once(
            config, compose, scope="service:postgres", service="postgres",
            hook=postgres.once, script_in_container="/yia-init/once.sh",
        )
    for application in config.applications:
        if application.once is None:
            continue
        script = application.once.script.relative_to(application.path).as_posix()
        _once(
            config, compose, scope=f"application:{application.name}",
            service=_application_service(application), hook=application.once,
            script_in_container=script,
            working_directory=f"/workspace/{application.name}",
        )
