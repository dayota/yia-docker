import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from yia.config import normalize_config
from yia.errors import ErrorCode, YiaError
from yia.generators import GeneratedFile, GenerationContext, GenerationEngine
from yia.state import read_state


@dataclass(frozen=True)
class FixtureGenerator:
    name: str
    files: tuple[GeneratedFile, ...]

    def generate(self, _context: GenerationContext):
        return self.files


@dataclass(frozen=True)
class FailingGenerator:
    name: str = "failing"

    def generate(self, _context: GenerationContext):
        raise RuntimeError("a value that must not leak")


def _config(project_root: Path, *, domain: str = "demo.localhost"):
    return normalize_config(
        {
            "version": 1,
            "project": {"name": "demo"},
            "environment": {"domain": domain},
            "applications": {},
        },
        project_root=project_root,
    )


def _runtime_snapshot(project_root: Path) -> dict[str, tuple[bytes, int]]:
    runtime = project_root / ".yia-runtime"
    return {
        path.relative_to(runtime).as_posix(): (
            path.read_bytes(),
            path.stat().st_mode & 0o777,
        )
        for path in sorted(runtime.rglob("*"))
        if path.is_file()
    }


def test_generation_writes_files_state_and_manifest(tmp_path: Path) -> None:
    generator = FixtureGenerator(
        name="fixture",
        files=(
            GeneratedFile.text("example/b.txt", "second\n"),
            GeneratedFile.text("example/a.txt", "first\n", mode=0o755),
        ),
    )

    result = GenerationEngine([generator]).generate(_config(tmp_path))

    runtime = tmp_path / ".yia-runtime"
    assert result.changed is True
    assert result.runtime_path == runtime
    assert (runtime / "example" / "a.txt").read_text() == "first\n"
    assert (runtime / "example" / "a.txt").stat().st_mode & 0o777 == 0o755
    assert read_state(tmp_path) is not None

    manifest_path = runtime / "state" / "generation-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 1
    assert manifest["generators"] == ["fixture"]
    assert [entry["path"] for entry in manifest["files"]] == [
        "example/a.txt",
        "example/b.txt",
        "state/yia-state.json",
    ]
    assert "state/generation-manifest.json" not in {
        entry["path"] for entry in manifest["files"]
    }


def test_two_identical_generations_produce_exactly_the_same_result(
    tmp_path: Path,
) -> None:
    engine = GenerationEngine(
        [
            FixtureGenerator(
                name="fixture",
                files=(GeneratedFile.text("artifact.txt", "stable\n"),),
            )
        ]
    )
    config = _config(tmp_path)

    first = engine.generate(config)
    first_snapshot = _runtime_snapshot(tmp_path)
    runtime = tmp_path / ".yia-runtime"
    runtime_identity = (runtime.stat().st_ino, runtime.stat().st_mtime_ns)
    artifact = runtime / "artifact.txt"
    artifact_identity = (artifact.stat().st_ino, artifact.stat().st_mtime_ns)
    second = engine.generate(config)

    assert first.changed is True
    assert first.changed_paths
    assert second.changed is False
    assert second.changed_paths == ()
    assert _runtime_snapshot(tmp_path) == first_snapshot
    assert (runtime.stat().st_ino, runtime.stat().st_mtime_ns) == runtime_identity
    assert (artifact.stat().st_ino, artifact.stat().st_mtime_ns) == artifact_identity
    assert not [
        path
        for path in tmp_path.iterdir()
        if path.name.startswith(".yia-runtime.")
    ]


def test_generator_and_file_order_do_not_change_the_result(tmp_path: Path) -> None:
    first_engine = GenerationEngine(
        [
            FixtureGenerator(
                name="zeta",
                files=(GeneratedFile.text("z.txt", "z"),),
            ),
            FixtureGenerator(
                name="alpha",
                files=(GeneratedFile.text("a.txt", "a"),),
            ),
        ]
    )
    second_engine = GenerationEngine(
        [
            FixtureGenerator(
                name="alpha",
                files=(GeneratedFile.text("a.txt", "a"),),
            ),
            FixtureGenerator(
                name="zeta",
                files=(GeneratedFile.text("z.txt", "z"),),
            ),
        ]
    )
    config = _config(tmp_path)

    first_engine.generate(config)
    snapshot = _runtime_snapshot(tmp_path)

    assert second_engine.generate(config).changed is False
    assert _runtime_snapshot(tmp_path) == snapshot


def test_configuration_change_is_detected(tmp_path: Path) -> None:
    engine = GenerationEngine([])

    first = engine.generate(_config(tmp_path))
    first_state = read_state(tmp_path)
    second = engine.generate(_config(tmp_path, domain="changed.localhost"))
    second_state = read_state(tmp_path)

    assert first.changed is True
    assert second.changed is True
    assert first_state is not None
    assert second_state is not None
    assert first_state.configuration_hash != second_state.configuration_hash


def test_modified_or_unmanaged_files_are_replaced(tmp_path: Path) -> None:
    engine = GenerationEngine(
        [
            FixtureGenerator(
                name="fixture",
                files=(GeneratedFile.text("managed.txt", "expected"),),
            )
        ]
    )
    config = _config(tmp_path)
    engine.generate(config)
    runtime = tmp_path / ".yia-runtime"
    (runtime / "managed.txt").write_text("modified", encoding="utf-8")
    (runtime / "unmanaged.txt").write_text("stale", encoding="utf-8")

    result = engine.generate(config)

    assert result.changed is True
    assert result.changed_paths == ("managed.txt", "unmanaged.txt")
    assert (runtime / "managed.txt").read_text(encoding="utf-8") == "expected"
    assert not (runtime / "unmanaged.txt").exists()


@pytest.mark.parametrize(
    "path",
    ["../outside.txt", "/absolute.txt", "state/yia-state.json", "state/generation-manifest.json"],
)
def test_unsafe_or_reserved_paths_are_rejected(
    tmp_path: Path,
    path: str,
) -> None:
    engine = GenerationEngine(
        [FixtureGenerator("fixture", (GeneratedFile.text(path, "content"),))]
    )

    with pytest.raises(YiaError) as caught:
        engine.generate(_config(tmp_path))

    assert caught.value.code is ErrorCode.GENERATION_FAILED
    assert caught.value.exit_code == 4
    assert not (tmp_path / ".yia-runtime").exists()


def test_duplicate_paths_are_rejected_before_publication(tmp_path: Path) -> None:
    engine = GenerationEngine(
        [
            FixtureGenerator(
                "first",
                (GeneratedFile.text("same.txt", "first"),),
            ),
            FixtureGenerator(
                "second",
                (GeneratedFile.text("same.txt", "second"),),
            ),
        ]
    )

    with pytest.raises(YiaError) as caught:
        engine.generate(_config(tmp_path))

    assert caught.value.code is ErrorCode.GENERATION_FAILED
    assert caught.value.details["path"] == "same.txt"
    assert not (tmp_path / ".yia-runtime").exists()


def test_duplicate_generator_names_are_rejected() -> None:
    generators = [
        FixtureGenerator("duplicate", (GeneratedFile.text("one.txt", "one"),)),
        FixtureGenerator("duplicate", (GeneratedFile.text("two.txt", "two"),)),
    ]

    with pytest.raises(YiaError) as caught:
        GenerationEngine(generators)

    assert caught.value.code is ErrorCode.GENERATION_FAILED
    assert caught.value.details == {"generators": ["duplicate", "duplicate"]}


def test_generator_failure_does_not_leak_details_or_replace_runtime(
    tmp_path: Path,
) -> None:
    stable_engine = GenerationEngine(
        [FixtureGenerator("stable", (GeneratedFile.text("stable.txt", "old"),))]
    )
    stable_engine.generate(_config(tmp_path))
    snapshot = _runtime_snapshot(tmp_path)

    with pytest.raises(YiaError) as caught:
        GenerationEngine([FailingGenerator()]).generate(_config(tmp_path))

    assert caught.value.code is ErrorCode.GENERATION_FAILED
    assert "a value that must not leak" not in json.dumps(caught.value.to_dict())
    assert _runtime_snapshot(tmp_path) == snapshot


def test_publication_failure_restores_previous_runtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first_engine = GenerationEngine(
        [FixtureGenerator("fixture", (GeneratedFile.text("value.txt", "old"),))]
    )
    second_engine = GenerationEngine(
        [FixtureGenerator("fixture", (GeneratedFile.text("value.txt", "new"),))]
    )
    config = _config(tmp_path)
    first_engine.generate(config)
    snapshot = _runtime_snapshot(tmp_path)
    real_replace = os.replace

    def fail_staging_publish(source: object, destination: object) -> None:
        source_path = Path(source)  # type: ignore[arg-type]
        if source_path.name.startswith(".yia-runtime.staging-"):
            raise OSError("simulated publication failure")
        real_replace(source, destination)

    monkeypatch.setattr("yia.generators.engine.os.replace", fail_staging_publish)

    with pytest.raises(YiaError) as caught:
        second_engine.generate(config)

    assert caught.value.code is ErrorCode.GENERATION_FAILED
    assert _runtime_snapshot(tmp_path) == snapshot
    assert not [
        path
        for path in tmp_path.iterdir()
        if path.name.startswith(".yia-runtime.")
    ]
