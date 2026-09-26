from __future__ import annotations

from typing import Any

from yia.errors import ErrorCode, YiaError
from yia.versions import (
    CONFIGURATION_SCHEMA_VERSION,
    DOCUMENTATION_SCHEMA_VERSION,
)

from .model import YiaState


def state_migrations(
    state: YiaState,
    *,
    configuration_schema_version: int = CONFIGURATION_SCHEMA_VERSION,
    documentation_schema_version: int = DOCUMENTATION_SCHEMA_VERSION,
) -> tuple[dict[str, Any], ...]:
    migrations: list[dict[str, Any]] = []
    versions = (
        (
            "configuration",
            state.configuration_schema_version,
            configuration_schema_version,
        ),
        (
            "documentation",
            state.documentation_schema_version,
            documentation_schema_version,
        ),
    )

    for component, current_version, expected_version in versions:
        if current_version != expected_version:
            migrations.append(
                {
                    "component": component,
                    "current_version": current_version,
                    "expected_version": expected_version,
                }
            )

    return tuple(migrations)


def assert_state_compatible(
    state: YiaState,
    *,
    configuration_schema_version: int = CONFIGURATION_SCHEMA_VERSION,
    documentation_schema_version: int = DOCUMENTATION_SCHEMA_VERSION,
) -> None:
    migrations = state_migrations(
        state,
        configuration_schema_version=configuration_schema_version,
        documentation_schema_version=documentation_schema_version,
    )
    if migrations:
        raise YiaError(
            ErrorCode.MIGRATION_REQUIRED,
            "L'état interne Yia nécessite une migration.",
            {"migrations": list(migrations)},
        )
