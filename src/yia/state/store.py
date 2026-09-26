from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from yia.errors import ErrorCode, YiaError
from yia.resources import schema_path
from yia.versions import STATE_SCHEMA_VERSION

from .model import YiaState


STATE_RELATIVE_PATH = Path(".yia-runtime") / "state" / "yia-state.json"


def state_path(project_root: Path) -> Path:
    return project_root.resolve() / STATE_RELATIVE_PATH


def default_state_schema_path() -> Path:
    return schema_path("yia-state.schema.json")


def _validation_errors(
    payload: Mapping[str, Any],
    schema_file: Path,
) -> list[dict[str, Any]]:
    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le schéma d'état interne Yia ne peut pas être lu.",
            {"path": str(schema_file), "reason": str(exc)},
        ) from exc

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le schéma d'état interne Yia est invalide.",
            {"path": str(schema_file), "reason": exc.message},
        ) from exc
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.validator,
            error.message,
        ),
    )
    return [
        {
            "path": ".".join(str(part) for part in error.absolute_path) or "$",
            "message": f"state value violates {error.validator!r} constraint",
            "constraint": error.validator,
            "expected": error.validator_value,
        }
        for error in errors
    ]


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    path: Path,
    schema_file: Path,
) -> None:
    version = payload.get("state_schema_version")
    if isinstance(version, int) and version != STATE_SCHEMA_VERSION:
        raise YiaError(
            ErrorCode.MIGRATION_REQUIRED,
            "La version du schéma d'état Yia nécessite une migration.",
            {
                "path": str(path),
                "component": "state",
                "current_version": version,
                "expected_version": STATE_SCHEMA_VERSION,
            },
        )

    errors = _validation_errors(payload, schema_file)
    if errors:
        raise YiaError(
            ErrorCode.GENERIC,
            "L'état interne Yia est invalide.",
            {"path": str(path), "validation_errors": errors},
        )


def serialize_state(state: YiaState) -> bytes:
    return (
        json.dumps(
            state.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def read_state(
    project_root: Path,
    *,
    schema_file: Path | None = None,
) -> YiaState | None:
    path = state_path(project_root)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "L'état interne Yia ne peut pas être lu.",
            {"path": str(path), "reason": str(exc)},
        ) from exc

    if not isinstance(payload, dict):
        raise YiaError(
            ErrorCode.GENERIC,
            "La racine de l'état interne Yia doit être un objet JSON.",
            {"path": str(path), "received_type": type(payload).__name__},
        )

    _validate_payload(
        payload,
        path=path,
        schema_file=schema_file or default_state_schema_path(),
    )
    return YiaState.from_dict(payload)


def write_state(
    project_root: Path,
    state: YiaState,
    *,
    schema_file: Path | None = None,
) -> bool:
    path = state_path(project_root)
    payload = state.to_dict()
    _validate_payload(
        payload,
        path=path,
        schema_file=schema_file or default_state_schema_path(),
    )
    serialized = serialize_state(state)

    try:
        if path.is_file() and path.read_bytes() == serialized:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise YiaError(
            ErrorCode.GENERIC,
            "Le répertoire d'état interne Yia ne peut pas être préparé.",
            {"path": str(path.parent), "reason": str(exc)},
        ) from exc

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=".yia-state.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(serialized)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except OSError as exc:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise YiaError(
            ErrorCode.GENERIC,
            "L'état interne Yia ne peut pas être écrit atomiquement.",
            {"path": str(path), "reason": str(exc)},
        ) from exc

    return True
