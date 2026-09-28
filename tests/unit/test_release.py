import json
import tomllib
from pathlib import Path

from yia.versions import (
    CONFIGURATION_SCHEMA_VERSION,
    DOCUMENTATION_SCHEMA_VERSION,
    GENERATION_MANIFEST_VERSION,
    STATE_SCHEMA_VERSION,
    YIA_VERSION,
)


ROOT = Path(__file__).resolve().parents[2]


def _json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_release_versions_and_executable_schemas_are_coherent() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    configuration = _json("schemas/yia.v2.schema.json")
    state = _json("schemas/yia-state.schema.json")
    manifest = _json("schemas/yia-generation-manifest.schema.json")
    documentation = (ROOT / "docs/documentation.md").read_text(encoding="utf-8")

    assert metadata["project"]["version"] == YIA_VERSION
    assert configuration["properties"]["version"]["const"] == CONFIGURATION_SCHEMA_VERSION
    assert state["properties"]["state_schema_version"]["const"] == STATE_SCHEMA_VERSION
    assert manifest["properties"]["manifest_version"]["const"] == GENERATION_MANIFEST_VERSION
    assert f"**Version :** {DOCUMENTATION_SCHEMA_VERSION}" in documentation


def test_all_declared_release_resources_exist() -> None:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    data_files = metadata["tool"]["setuptools"]["data-files"]

    missing = [
        path
        for paths in data_files.values()
        for path in paths
        if not (ROOT / path).is_file()
    ]

    assert missing == []
