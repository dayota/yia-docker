from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    GENERIC = "YIA_GENERIC_ERROR"
    CONFIG_INVALID = "YIA_CONFIG_INVALID"
    DEPENDENCY_MISSING = "YIA_DEPENDENCY_MISSING"
    GENERATION_FAILED = "YIA_GENERATION_FAILED"
    DOCKER_UNAVAILABLE = "YIA_DOCKER_UNAVAILABLE"
    MIGRATION_REQUIRED = "YIA_MIGRATION_REQUIRED"


EXIT_CODES = {
    ErrorCode.GENERIC: 1,
    ErrorCode.CONFIG_INVALID: 2,
    ErrorCode.DEPENDENCY_MISSING: 3,
    ErrorCode.GENERATION_FAILED: 4,
    ErrorCode.DOCKER_UNAVAILABLE: 5,
    ErrorCode.MIGRATION_REQUIRED: 6,
}


@dataclass(slots=True)
class YiaError(Exception):
    code: ErrorCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.code]

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "status": "error",
            "error": {
                "code": self.code.value,
                "message": self.message,
            },
        }
        if self.details:
            result["error"]["details"] = self.details
        return result
