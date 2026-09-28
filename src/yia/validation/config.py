from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from yia.errors import ErrorCode, YiaError


HOSTNAME_PATTERN = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
)


def _file_error(
    value: str,
    *,
    root: Path,
    key: str,
    allow_missing: bool = False,
) -> dict[str, Any] | None:
    relative = Path(value)
    resolved = (root / relative).resolve()
    if relative.is_absolute() or not resolved.is_relative_to(root):
        return {
            "path": key,
            "message": "initialization file must be relative and contained in its source root",
            "received": value,
            "constraint": "contained_file",
            "expected": "a relative file inside the project or application",
        }
    if not allow_missing and not resolved.is_file():
        return {
            "path": key,
            "message": "initialization file does not exist",
            "received": value,
            "constraint": "existing_file",
            "expected": "an existing regular file",
        }
    return None


def _format_path(parts: Any) -> str:
    return ".".join(str(part) for part in parts) or "$"


def _received_value(error: ValidationError) -> Any:
    if error.validator == "required":
        return None
    if error.validator == "additionalProperties" and isinstance(error.instance, dict):
        allowed = set(error.schema.get("properties", {}))
        return sorted(str(key) for key in error.instance if key not in allowed)
    if isinstance(error.instance, (str, int, float, bool)) or error.instance is None:
        return error.instance
    return {"type": type(error.instance).__name__}


def _expected_constraint(error: ValidationError) -> Any:
    if error.validator == "additionalProperties":
        return "no additional properties"
    return error.validator_value


def _format_schema_error(error: ValidationError) -> dict[str, Any]:
    return {
        "path": _format_path(error.absolute_path),
        "message": error.message,
        "received": _received_value(error),
        "constraint": error.validator,
        "expected": _expected_constraint(error),
    }


def _semantic_errors(
    config: dict[str, Any],
    project_root: Path | None,
) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    applications = config.get("applications", {})
    if not isinstance(applications, dict):
        return errors

    hostnames: dict[str, str] = {}
    managed_paths: dict[Path, str] = {}
    resolved_root = project_root.resolve() if project_root is not None else None

    if resolved_root is not None and config.get("version") == 2:
        services = config.get("services", {})
        postgres = services.get("postgres") if isinstance(services, dict) else None
        initialization = postgres.get("initialization") if isinstance(postgres, dict) else None
        if isinstance(initialization, dict):
            for field, value in (
                ("sql", initialization.get("sql")),
                (
                    "once.script",
                    initialization.get("once", {}).get("script")
                    if isinstance(initialization.get("once"), dict)
                    else None,
                ),
            ):
                if isinstance(value, str):
                    key = f"services.postgres.initialization.{field}"
                    error = _file_error(value, root=resolved_root, key=key)
                    if error is not None:
                        errors.append(error)
                    if field == "sql" and not value.endswith(".sql"):
                        errors.append({
                            "path": key, "message": "only plain .sql files are supported",
                            "received": value, "constraint": "sql_extension",
                            "expected": "a .sql text file",
                        })
                    elif field == "sql" and error is None:
                        try:
                            with (resolved_root / value).open("rb") as sql_file:
                                signature = sql_file.read(5)
                        except OSError as exc:
                            errors.append({
                                "path": key,
                                "message": "SQL initialization file cannot be read",
                                "received": value,
                                "constraint": "readable_file",
                                "expected": "a readable plain-text SQL file",
                                "error_type": type(exc).__name__,
                            })
                            signature = b""
                        if signature == b"PGDMP":
                            errors.append({
                                "path": key,
                                "message": "custom pg_dump archives require pg_restore",
                                "received": value,
                                "constraint": "plain_sql_file",
                                "expected": "a plain-text SQL dump or script",
                            })
            if postgres.get("enabled", True) is False:
                errors.append({
                    "path": "services.postgres.initialization",
                    "message": "initialization requires an enabled PostgreSQL service",
                    "received": "disabled", "constraint": "enabled_service",
                    "expected": "postgres.enabled: true",
                })

    environment = config.get("environment", {})
    domain = environment.get("domain") if isinstance(environment, dict) else None
    if isinstance(domain, str) and (
        len(domain) > 253 or HOSTNAME_PATTERN.fullmatch(domain) is None
    ):
        errors.append(
            {
                "path": "environment.domain",
                "message": "domain must be a lowercase ASCII DNS hostname",
                "received": domain,
                "constraint": "hostname",
                "expected": "a valid lowercase ASCII DNS hostname",
            }
        )

    for name in sorted(applications):
        application = applications[name]
        if not isinstance(application, dict):
            continue

        web = application.get("web")
        if isinstance(web, dict):
            hostname = web.get("hostname")
            if isinstance(hostname, str):
                if (
                    len(hostname) > 253
                    or HOSTNAME_PATTERN.fullmatch(hostname) is None
                ):
                    errors.append(
                        {
                            "path": f"applications.{name}.web.hostname",
                            "message": (
                                "hostname must be a lowercase ASCII DNS hostname"
                            ),
                            "received": hostname,
                            "constraint": "hostname",
                            "expected": "a valid lowercase ASCII DNS hostname",
                        }
                    )
                else:
                    hostname_key = hostname.casefold()
                    if hostname_key in hostnames:
                        errors.append(
                            {
                                "path": f"applications.{name}.web.hostname",
                                "message": (
                                    "hostname already used by application "
                                    f"{hostnames[hostname_key]!r}"
                                ),
                                "received": hostname,
                                "constraint": "unique",
                                "expected": "a hostname unique within the project",
                            }
                        )
                    else:
                        hostnames[hostname_key] = name

        if resolved_root is None:
            continue

        configured_path = application.get("path")
        if not isinstance(configured_path, str):
            continue

        relative_path = Path(configured_path)
        path_key = f"applications.{name}.path"
        source = application.get("source") if config.get("version") == 2 else None
        source_type = source.get("type") if isinstance(source, dict) else None
        if config.get("version") == 1 and relative_path.is_absolute():
            errors.append(
                {
                    "path": path_key,
                    "message": "application path must be relative to the project root",
                    "received": configured_path,
                    "constraint": "project_relative_path",
                    "expected": "a relative path contained in the project",
                }
            )
            continue

        resolved_path = (resolved_root / relative_path).resolve()
        apps_root = resolved_root / "apps"
        lexical_path = resolved_root / relative_path
        managed = source_type == "managed"
        if managed and (
            relative_path.is_absolute()
            or len(relative_path.parts) != 2
            or relative_path.parts[0] != "apps"
            or not resolved_path.is_relative_to(apps_root)
            or apps_root.is_symlink()
            or lexical_path.is_symlink()
        ):
            errors.append(
                {
                    "path": path_key,
                    "message": "managed application path must be a safe child of apps",
                    "received": configured_path,
                    "constraint": "managed_apps_path",
                    "expected": "a relative, non-symlink path inside apps/",
                }
            )
            continue
        if managed:
            previous = managed_paths.get(resolved_path)
            if previous is not None:
                errors.append(
                    {
                        "path": path_key,
                        "message": f"managed path is already used by application {previous!r}",
                        "received": configured_path,
                        "constraint": "unique_managed_path",
                        "expected": "a destination unique for each managed application",
                    }
                )
                continue
            managed_paths[resolved_path] = name
        if source_type == "linked" and (
            resolved_path.is_relative_to(apps_root)
            or (not relative_path.is_absolute() and relative_path.parts[0] == "apps")
        ):
            errors.append(
                {
                    "path": path_key,
                    "message": "linked application path must be outside apps",
                    "received": configured_path,
                    "constraint": "linked_path",
                    "expected": "an existing directory outside apps/",
                }
            )
            continue
        if config.get("version") == 1 and not resolved_path.is_relative_to(resolved_root):
            errors.append(
                {
                    "path": path_key,
                    "message": "application path resolves outside the project root",
                    "received": configured_path,
                    "constraint": "project_relative_path",
                    "expected": "a relative path contained in the project",
                }
            )
        elif not resolved_path.is_dir() and not managed:
            errors.append(
                {
                    "path": path_key,
                    "message": "application directory does not exist",
                    "received": configured_path,
                    "constraint": "existing_directory",
                    "expected": "an existing application directory",
                }
            )

        initialization = application.get("initialization")
        if isinstance(initialization, dict):
            once = initialization.get("once")
            script = once.get("script") if isinstance(once, dict) else None
            if isinstance(script, str):
                error = _file_error(
                    script,
                    root=resolved_path,
                    key=f"applications.{name}.initialization.once.script",
                    allow_missing=managed and not resolved_path.is_dir(),
                )
                if error is not None:
                    errors.append(error)

        if application.get("type") != "php" or not isinstance(web, dict):
            continue

        public_directory = web.get("public_directory")
        if not isinstance(public_directory, str):
            continue

        public_path = Path(public_directory)
        resolved_public_path = (resolved_path / public_path).resolve()
        if public_path.is_absolute() or not resolved_public_path.is_relative_to(
            resolved_path
        ):
            errors.append(
                {
                    "path": f"applications.{name}.web.public_directory",
                    "message": (
                        "public directory must resolve inside the application path"
                    ),
                    "received": public_directory,
                    "constraint": "application_relative_path",
                    "expected": "a relative path contained in the application",
                }
            )
        elif not resolved_public_path.is_dir() and (not managed or resolved_path.is_dir()):
            errors.append(
                {
                    "path": f"applications.{name}.web.public_directory",
                    "message": "public directory does not exist",
                    "received": public_directory,
                    "constraint": "existing_directory",
                    "expected": "an existing directory inside the application",
                }
            )

    return errors


def validate_config(
    config: dict[str, Any],
    schema_path: Path,
    *,
    project_root: Path | None = None,
) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    schema_errors = sorted(
        validator.iter_errors(config),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.validator,
            error.message,
        ),
    )
    errors = [_format_schema_error(error) for error in schema_errors]

    if not schema_errors:
        errors.extend(_semantic_errors(config, project_root))

    if not errors:
        return

    raise YiaError(
        ErrorCode.CONFIG_INVALID,
        "La configuration yia.yml est invalide.",
        {
            "expected_schema_version": schema["properties"]["version"]["const"],
            "validation_errors": errors,
        },
    )
