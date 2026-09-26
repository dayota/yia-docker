from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from yia.config.model import NormalizedConfig
from yia.versions import (
    DOCUMENTATION_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    YIA_VERSION,
)


@dataclass(frozen=True, slots=True)
class YiaState:
    state_schema_version: int
    yia_version: str
    configuration_schema_version: int
    documentation_schema_version: int
    configuration_hash: str

    @classmethod
    def from_config(
        cls,
        config: NormalizedConfig,
        *,
        yia_version: str = YIA_VERSION,
        documentation_schema_version: int = DOCUMENTATION_SCHEMA_VERSION,
    ) -> "YiaState":
        return cls(
            state_schema_version=STATE_SCHEMA_VERSION,
            yia_version=yia_version,
            configuration_schema_version=config.schema_version,
            documentation_schema_version=documentation_schema_version,
            configuration_hash=config.configuration_hash,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "YiaState":
        return cls(
            state_schema_version=int(payload["state_schema_version"]),
            yia_version=str(payload["yia_version"]),
            configuration_schema_version=int(
                payload["configuration_schema_version"]
            ),
            documentation_schema_version=int(payload["documentation_schema_version"]),
            configuration_hash=str(payload["configuration_hash"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
