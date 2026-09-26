from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Protocol

from yia.config import NormalizedConfig
from yia.state import YiaState

if TYPE_CHECKING:
    from .manifest import GenerationManifest


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    path: str
    content: bytes
    mode: int = 0o644

    @classmethod
    def text(
        cls,
        path: str,
        content: str,
        *,
        mode: int = 0o644,
    ) -> "GeneratedFile":
        return cls(path=path, content=content.encode("utf-8"), mode=mode)


@dataclass(frozen=True, slots=True)
class GenerationContext:
    config: NormalizedConfig
    state: YiaState


class Generator(Protocol):
    name: str

    def generate(self, context: GenerationContext) -> Iterable[GeneratedFile]: ...


@dataclass(frozen=True, slots=True)
class GenerationResult:
    changed: bool
    runtime_path: Path
    manifest: "GenerationManifest"
    changed_paths: tuple[str, ...] = ()
