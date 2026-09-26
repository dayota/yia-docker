from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Iterable

from yia.config import NormalizedConfig
from yia.errors import ErrorCode, YiaError
from yia.state import YiaState, serialize_state

from .manifest import MANIFEST_PATH, GenerationManifest, validate_manifest
from .model import GeneratedFile, GenerationContext, GenerationResult, Generator


RUNTIME_DIRECTORY = ".yia-runtime"
STATE_PATH = "state/yia-state.json"
RESERVED_PATHS = {MANIFEST_PATH, STATE_PATH}
ALLOWED_MODES = {0o644, 0o755}


def _generation_error(
    message: str,
    details: dict[str, object] | None = None,
) -> YiaError:
    return YiaError(ErrorCode.GENERATION_FAILED, message, details or {})


def _normalize_generated_file(generated_file: GeneratedFile) -> GeneratedFile:
    if not isinstance(generated_file, GeneratedFile):
        raise _generation_error(
            "Un générateur a retourné un artefact invalide.",
            {"received_type": type(generated_file).__name__},
        )
    if not isinstance(generated_file.content, bytes):
        raise _generation_error(
            "Le contenu d'un artefact généré doit être binaire.",
            {"path": str(generated_file.path)},
        )
    if generated_file.mode not in ALLOWED_MODES:
        raise _generation_error(
            "Le mode d'un artefact généré n'est pas autorisé.",
            {"path": generated_file.path, "mode": generated_file.mode},
        )
    if not isinstance(generated_file.path, str) or "\x00" in generated_file.path:
        raise _generation_error("Le chemin d'un artefact généré est invalide.")

    path = PurePosixPath(generated_file.path)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise _generation_error(
            "Un artefact généré doit rester dans .yia-runtime/.",
            {"path": generated_file.path},
        )

    normalized_path = path.as_posix()
    if normalized_path in RESERVED_PATHS:
        raise _generation_error(
            "Un générateur a utilisé un chemin réservé par Yia.",
            {"path": normalized_path},
        )

    return GeneratedFile(
        path=normalized_path,
        content=generated_file.content,
        mode=generated_file.mode,
    )


def _has_path_collision(path: PurePosixPath, other: PurePosixPath) -> bool:
    return path == other or path in other.parents or other in path.parents


def _collect_files(
    generators: tuple[Generator, ...],
    context: GenerationContext,
) -> dict[str, GeneratedFile]:
    files: dict[str, GeneratedFile] = {}
    paths = {PurePosixPath(path) for path in RESERVED_PATHS}

    for generator in generators:
        try:
            generated_files = generator.generate(context)
            for raw_file in generated_files:
                generated_file = _normalize_generated_file(raw_file)
                path = PurePosixPath(generated_file.path)
                collision = next(
                    (existing for existing in paths if _has_path_collision(path, existing)),
                    None,
                )
                if collision is not None:
                    raise _generation_error(
                        "Plusieurs artefacts générés utilisent des chemins incompatibles.",
                        {
                            "path": path.as_posix(),
                            "conflicting_path": collision.as_posix(),
                        },
                    )
                files[generated_file.path] = generated_file
                paths.add(path)
        except YiaError:
            raise
        except Exception as exc:
            raise _generation_error(
                "Un générateur Yia a échoué.",
                {
                    "generator": generator.name,
                    "error_type": type(exc).__name__,
                },
            ) from exc

    return files


def _snapshot_matches(
    runtime_path: Path,
    expected_files: dict[str, GeneratedFile],
) -> bool:
    if runtime_path.is_symlink() or not runtime_path.is_dir():
        return False

    actual_files: dict[str, Path] = {}
    try:
        for path in runtime_path.rglob("*"):
            if path.is_symlink():
                return False
            if path.is_file():
                actual_files[path.relative_to(runtime_path).as_posix()] = path
            elif not path.is_dir():
                return False

        if set(actual_files) != set(expected_files):
            return False

        for relative_path, expected in expected_files.items():
            actual = actual_files[relative_path]
            if actual.read_bytes() != expected.content:
                return False
            if actual.stat().st_mode & 0o777 != expected.mode:
                return False
    except OSError:
        return False

    return True


def _write_staging_snapshot(
    staging_path: Path,
    files: dict[str, GeneratedFile],
) -> None:
    try:
        for relative_path in sorted(files):
            generated_file = files[relative_path]
            destination = staging_path / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(generated_file.content)
                output.flush()
                os.fsync(output.fileno())
            destination.chmod(generated_file.mode)
    except (OSError, ValueError) as exc:
        raise _generation_error(
            "Le snapshot de génération ne peut pas être écrit.",
            {"path": str(staging_path), "error_type": type(exc).__name__},
        ) from exc

    if not _snapshot_matches(staging_path, files):
        raise _generation_error(
            "Le snapshot de génération ne correspond pas au manifeste attendu.",
            {"path": str(staging_path)},
        )


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def _publish_snapshot(staging_path: Path, runtime_path: Path) -> None:
    backup_path = runtime_path.parent / (
        f"{RUNTIME_DIRECTORY}.backup-{uuid.uuid4().hex}"
    )
    previous_runtime_moved = False

    try:
        if os.path.lexists(runtime_path):
            os.replace(runtime_path, backup_path)
            previous_runtime_moved = True

        try:
            os.replace(staging_path, runtime_path)
        except OSError as publish_error:
            recovery_error: OSError | None = None
            if previous_runtime_moved:
                try:
                    os.replace(backup_path, runtime_path)
                except OSError as exc:
                    recovery_error = exc

            details: dict[str, object] = {
                "path": str(runtime_path),
                "error_type": type(publish_error).__name__,
            }
            if recovery_error is not None:
                details["recovery_error_type"] = type(recovery_error).__name__
                details["recoverable_backup"] = str(backup_path)
            raise _generation_error(
                "La publication du runtime généré a échoué.",
                details,
            ) from publish_error

        if previous_runtime_moved:
            try:
                _remove_path(backup_path)
            except OSError as exc:
                raise _generation_error(
                    "L'ancien runtime généré ne peut pas être nettoyé.",
                    {
                        "path": str(backup_path),
                        "error_type": type(exc).__name__,
                    },
                ) from exc
    except YiaError:
        raise
    except OSError as exc:
        raise _generation_error(
            "Le runtime généré ne peut pas être remplacé.",
            {"path": str(runtime_path), "error_type": type(exc).__name__},
        ) from exc


class GenerationEngine:
    def __init__(self, generators: Iterable[Generator]) -> None:
        candidates = tuple(generators)
        try:
            names = [generator.name for generator in candidates]
        except Exception as exc:
            raise _generation_error(
                "Un générateur ne déclare pas de nom valide.",
                {"generator_type": type(exc).__name__},
            ) from None
        if any(not isinstance(name, str) or not name for name in names):
            raise _generation_error("Chaque générateur doit posséder un nom stable.")
        if len(names) != len(set(names)):
            raise _generation_error(
                "Les noms des générateurs doivent être uniques.",
                {"generators": sorted(names)},
            )
        self.generators = tuple(
            generator
            for _, generator in sorted(
                zip(names, candidates, strict=True),
                key=lambda item: item[0],
            )
        )

    def _expected_snapshot(
        self,
        config: NormalizedConfig,
    ) -> tuple[dict[str, GeneratedFile], GenerationManifest]:
        state = YiaState.from_config(config)
        context = GenerationContext(config=config, state=state)
        generated_files = _collect_files(self.generators, context)
        generated_files[STATE_PATH] = GeneratedFile(
            path=STATE_PATH,
            content=serialize_state(state),
        )

        manifest = GenerationManifest.create(
            config,
            state,
            generator_names=(generator.name for generator in self.generators),
            files=generated_files.values(),
        )
        validate_manifest(manifest)

        all_files = dict(generated_files)
        all_files[MANIFEST_PATH] = GeneratedFile(
            path=MANIFEST_PATH,
            content=manifest.to_bytes(),
        )
        return all_files, manifest

    def is_current(self, config: NormalizedConfig) -> bool:
        expected_files, _ = self._expected_snapshot(config)
        runtime_path = config.project_root / RUNTIME_DIRECTORY
        return _snapshot_matches(runtime_path, expected_files)

    def generate(self, config: NormalizedConfig) -> GenerationResult:
        all_files, manifest = self._expected_snapshot(config)
        runtime_path = config.project_root / RUNTIME_DIRECTORY
        if _snapshot_matches(runtime_path, all_files):
            return GenerationResult(False, runtime_path, manifest)

        try:
            staging_path = Path(
                tempfile.mkdtemp(
                    dir=config.project_root,
                    prefix=f"{RUNTIME_DIRECTORY}.staging-",
                )
            )
        except OSError as exc:
            raise _generation_error(
                "Le répertoire de staging ne peut pas être créé.",
                {
                    "path": str(config.project_root),
                    "error_type": type(exc).__name__,
                },
            ) from exc

        try:
            _write_staging_snapshot(staging_path, all_files)
            _publish_snapshot(staging_path, runtime_path)
        finally:
            try:
                _remove_path(staging_path)
            except OSError:
                pass

        return GenerationResult(True, runtime_path, manifest)
