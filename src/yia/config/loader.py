from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode

from yia.errors import ErrorCode, YiaError


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""

    def construct_mapping(
        self,
        node: MappingNode,
        deep: bool = False,
    ) -> dict[Any, Any]:
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}

        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found an unhashable key",
                    key_node.start_mark,
                ) from exc

            if duplicate:
                raise ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )

            mapping[key] = self.construct_object(value_node, deep=deep)

        return mapping


def _yaml_error_details(path: Path, error: yaml.YAMLError) -> dict[str, Any]:
    details: dict[str, Any] = {"path": str(path)}
    problem = getattr(error, "problem", None)
    if problem:
        details["reason"] = problem

    mark = getattr(error, "problem_mark", None)
    if mark is not None:
        details["line"] = mark.line + 1
        details["column"] = mark.column + 1

    return details


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            f"Configuration introuvable : {path}",
            {"path": str(path)},
        )

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le fichier yia.yml ne peut pas être lu.",
            {"path": str(path), "reason": str(exc)},
        ) from exc

    try:
        data = yaml.load(content, Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "Le fichier yia.yml n'est pas un YAML valide.",
            _yaml_error_details(path, exc),
        ) from exc

    if not isinstance(data, dict):
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "La racine de yia.yml doit être un objet YAML.",
            {
                "path": str(path),
                "received_type": type(data).__name__,
                "expected": "object",
            },
        )

    return data
