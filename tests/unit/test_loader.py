from pathlib import Path

import pytest

from yia.config import load_config
from yia.errors import ErrorCode, YiaError


@pytest.mark.parametrize("content", ["", "- item\n", "plain text\n"])
def test_configuration_root_must_be_a_mapping(
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "yia.yml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        load_config(path)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.exit_code == 2
    assert caught.value.details["expected"] == "object"


def test_duplicate_yaml_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "yia.yml"
    path.write_text(
        "version: 1\nversion: 1\n",
        encoding="utf-8",
    )

    with pytest.raises(YiaError) as caught:
        load_config(path)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.details["line"] == 2
    assert "duplicate key" in caught.value.details["reason"]


def test_malformed_yaml_is_rejected_without_raw_parser_context(tmp_path: Path) -> None:
    path = tmp_path / "yia.yml"
    path.write_text("project: [\n", encoding="utf-8")

    with pytest.raises(YiaError) as caught:
        load_config(path)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.details["path"] == str(path)
    assert caught.value.details["line"] == 2


def test_missing_configuration_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "yia.yml"

    with pytest.raises(YiaError) as caught:
        load_config(path)

    assert caught.value.code is ErrorCode.CONFIG_INVALID
    assert caught.value.exit_code == 2
