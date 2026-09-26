from __future__ import annotations

import re


POSTGRES_CONTAINER_PORT = 5432
POSTGRES_DATA_VOLUME = "postgres-data"
POSTGRES_DEFAULT_DATABASE = "postgres"
POSTGRES_DEFAULT_USER = "postgres"
POSTGRES_SERVICE_NAME = "postgres"


def postgres_data_path(version: str) -> str:
    major_match = re.match(r"[0-9]+", version)
    if major_match is None:
        raise ValueError("PostgreSQL version must begin with its major number")
    if int(major_match.group()) >= 18:
        return "/var/lib/postgresql"
    return "/var/lib/postgresql/data"


def postgres_environment() -> dict[str, str]:
    return {
        "POSTGRES_DB": (
            f"${{POSTGRES_DB:-{POSTGRES_DEFAULT_DATABASE}}}"
        ),
        "POSTGRES_PASSWORD": (
            "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set in .env}"
        ),
        "POSTGRES_USER": f"${{POSTGRES_USER:-{POSTGRES_DEFAULT_USER}}}",
    }
