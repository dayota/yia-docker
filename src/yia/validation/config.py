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
    resolved_root = project_root.resolve() if project_root is not None else None

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
        if relative_path.is_absolute():
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
        if not resolved_path.is_relative_to(resolved_root):
            errors.append(
                {
                    "path": path_key,
                    "message": "application path resolves outside the project root",
                    "received": configured_path,
                    "constraint": "project_relative_path",
                    "expected": "a relative path contained in the project",
                }
            )
        elif not resolved_path.is_dir():
            errors.append(
                {
                    "path": path_key,
                    "message": "application directory does not exist",
                    "received": configured_path,
                    "constraint": "existing_directory",
                    "expected": "an existing directory contained in the project",
                }
            )

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
        elif not resolved_public_path.is_dir():
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
