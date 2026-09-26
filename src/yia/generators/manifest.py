from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from yia.config import NormalizedConfig
from yia.errors import ErrorCode, YiaError
from yia.resources import schema_path
from yia.state import YiaState
from yia.versions import GENERATION_MANIFEST_VERSION

from .model import GeneratedFile


MANIFEST_PATH = "state/generation-manifest.json"


@dataclass(frozen=True, slots=True)
class ManifestFile:
    path: str
    sha256: str
    size: int
    mode: int

    @classmethod
    def from_generated_file(cls, generated_file: GeneratedFile) -> "ManifestFile":
        return cls(
            path=generated_file.path,
            sha256=hashlib.sha256(generated_file.content).hexdigest(),
            size=len(generated_file.content),
            mode=generated_file.mode,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "mode": self.mode,
        }


@dataclass(frozen=True, slots=True)
class GenerationManifest:
    manifest_version: int
    yia_version: str
    configuration_schema_version: int
    configuration_hash: str
    generators: tuple[str, ...]
    files: tuple[ManifestFile, ...]

    @classmethod
    def create(
        cls,
        config: NormalizedConfig,
        state: YiaState,
        *,
        generator_names: Iterable[str],
        files: Iterable[GeneratedFile],
    ) -> "GenerationManifest":
        return cls(
            manifest_version=GENERATION_MANIFEST_VERSION,
            yia_version=state.yia_version,
            configuration_schema_version=config.schema_version,
            configuration_hash=config.configuration_hash,
            generators=tuple(sorted(generator_names)),
            files=tuple(
                ManifestFile.from_generated_file(generated_file)
                for generated_file in sorted(files, key=lambda item: item.path)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "yia_version": self.yia_version,
            "configuration_schema_version": self.configuration_schema_version,
            "configuration_hash": self.configuration_hash,
            "generators": list(self.generators),
            "files": [file.to_dict() for file in self.files],
        }

    def to_bytes(self) -> bytes:
        return (
            json.dumps(
                self.to_dict(),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")


def default_manifest_schema_path() -> Path:
    return schema_path("yia-generation-manifest.schema.json")


def validate_manifest(
    manifest: GenerationManifest,
    *,
    schema_file: Path | None = None,
) -> None:
    path = schema_file or default_manifest_schema_path()
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, UnicodeError, json.JSONDecodeError, SchemaError) as exc:
        raise YiaError(
            ErrorCode.GENERATION_FAILED,
            "Le schéma du manifeste de génération est invalide ou illisible.",
            {"path": str(path), "error_type": type(exc).__name__},
        ) from exc

    errors = sorted(
        Draft202012Validator(schema).iter_errors(manifest.to_dict()),
        key=lambda error: (
            tuple(str(part) for part in error.absolute_path),
            error.validator,
            error.message,
        ),
    )
    if errors:
        raise YiaError(
            ErrorCode.GENERATION_FAILED,
            "Le manifeste de génération produit est invalide.",
            {
                "validation_errors": [
                    {
                        "path": (
                            ".".join(str(part) for part in error.absolute_path)
                            or "$"
                        ),
                        "constraint": error.validator,
                    }
                    for error in errors
                ]
            },
        )
