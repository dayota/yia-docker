import json
from dataclasses import replace
from pathlib import Path

import pytest

from yia.config import normalize_config
from yia.errors import ErrorCode, YiaError
from yia.state import (
    YiaState,
    assert_state_compatible,
    read_state,
    state_path,
    write_state,
)


def _normalized_config(project_root: Path):
    return normalize_config(
        {
            "version": 1,
            "project": {"name": "demo"},
            "environment": {"domain": "demo.localhost"},
            "applications": {},
        },
        project_root=project_root,
    )


def _state(project_root: Path, *, configuration_hash: str | None = None) -> YiaState:
    state = YiaState.from_config(_normalized_config(project_root))
    if configuration_hash is not None:
        state = replace(state, configuration_hash=configuration_hash)
    return state


def test_state_contains_only_reconstructible_metadata(tmp_path: Path) -> None:
    normalized = _normalized_config(tmp_path)

    state = YiaState.from_config(normalized)

    assert state.to_dict() == {
        "state_schema_version": 1,
        "yia_version": "0.1.0",
        "configuration_schema_version": 1,
        "documentation_schema_version": 1,
        "configuration_hash": normalized.configuration_hash,
    }
    assert set(state.to_dict()) == {
        "state_schema_version",
        "yia_version",
        "configuration_schema_version",
        "documentation_schema_version",
        "configuration_hash",
    }


def test_state_round_trip_uses_the_contract_path(tmp_path: Path) -> None:
    state = _state(tmp_path)

    changed = write_state(tmp_path, state)

    path = tmp_path / ".yia-runtime" / "state" / "yia-state.json"
    assert changed is True
    assert state_path(tmp_path) == path
    assert read_state(tmp_path) == state
    assert json.loads(path.read_text(encoding="utf-8")) == state.to_dict()
    assert path.read_bytes().endswith(b"\n")


def test_identical_state_write_is_idempotent(tmp_path: Path) -> None:
    state = _state(tmp_path)

    assert write_state(tmp_path, state) is True
    first_bytes = state_path(tmp_path).read_bytes()
    assert write_state(tmp_path, state) is False

    assert state_path(tmp_path).read_bytes() == first_bytes


def test_atomic_write_preserves_previous_state_on_replace_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original = _state(tmp_path, configuration_hash="a" * 64)
    replacement = _state(tmp_path, configuration_hash="b" * 64)
    write_state(tmp_path, original)
    path = state_path(tmp_path)
    original_bytes = path.read_bytes()

    def fail_replace(_source: object, _destination: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr("yia.state.store.os.replace", fail_replace)

    with pytest.raises(YiaError) as caught:
        write_state(tmp_path, replacement)

    assert caught.value.code is ErrorCode.GENERIC
    assert path.read_bytes() == original_bytes
    assert sorted(item.name for item in path.parent.iterdir()) == ["yia-state.json"]


def test_missing_state_is_not_an_error_and_can_be_reconstructed(
    tmp_path: Path,
) -> None:
    expected = _state(tmp_path)

    assert read_state(tmp_path) is None
    write_state(tmp_path, expected)
    state_path(tmp_path).unlink()
    assert read_state(tmp_path) is None

    reconstructed = _state(tmp_path)
    assert reconstructed == expected


def test_malformed_state_is_a_structured_error(tmp_path: Path) -> None:
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        read_state(tmp_path)

    assert caught.value.code is ErrorCode.GENERIC
    assert caught.value.details["path"] == str(path)


def test_state_that_does_not_match_schema_is_rejected(tmp_path: Path) -> None:
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True)
    payload = _state(tmp_path).to_dict()
    payload["configuration_hash"] = "not-a-sha256"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        read_state(tmp_path)

    assert caught.value.code is ErrorCode.GENERIC
    assert caught.value.details["validation_errors"]
    assert "not-a-sha256" not in json.dumps(caught.value.to_dict())


def test_unknown_state_schema_requires_migration(tmp_path: Path) -> None:
    path = state_path(tmp_path)
    path.parent.mkdir(parents=True)
    payload = _state(tmp_path).to_dict()
    payload["state_schema_version"] = 2
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        read_state(tmp_path)

    assert caught.value.code is ErrorCode.MIGRATION_REQUIRED
    assert caught.value.exit_code == 6
    assert caught.value.details == {
        "path": str(path),
        "component": "state",
        "current_version": 2,
        "expected_version": 1,
    }


def test_configuration_or_documentation_schema_change_requires_migration(
    tmp_path: Path,
) -> None:
    state = _state(tmp_path)

    with pytest.raises(YiaError) as caught:
        assert_state_compatible(
            state,
            configuration_schema_version=2,
            documentation_schema_version=3,
        )

    assert caught.value.code is ErrorCode.MIGRATION_REQUIRED
    assert caught.value.details["migrations"] == [
        {
            "component": "configuration",
            "current_version": 1,
            "expected_version": 2,
        },
        {
            "component": "documentation",
            "current_version": 1,
            "expected_version": 3,
        },
    ]


def test_compatible_state_does_not_require_migration(tmp_path: Path) -> None:
    assert_state_compatible(_state(tmp_path))
