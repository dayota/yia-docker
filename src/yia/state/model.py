from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class YiaState:
    yia_version: str
    schema_version: int
    documentation_schema: int
    configuration_hash: str
    generated_at: str

    @classmethod
    def create(
        cls,
        *,
        yia_version: str,
        schema_version: int,
        documentation_schema: int,
        configuration_hash: str,
    ) -> "YiaState":
        return cls(
            yia_version=yia_version,
            schema_version=schema_version,
            documentation_schema=documentation_schema,
            configuration_hash=configuration_hash,
            generated_at=datetime.now(UTC).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
