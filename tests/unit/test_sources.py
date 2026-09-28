from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from yia.config import load_normalized_config
from yia.errors import YiaError
from yia.initialization import initialize_project
from yia.project import load_project
from yia.sources import synchronize_sources
from yia.updating import update_project


SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "yia.schema.json"


def _config(root: Path, *, source_type: str = "managed", path: str = "apps/api") -> Path:
    source = (
        "source:\n      type: managed\n      git:\n"
        "        ssh: git@example.test:repo\n        branch: main\n        version: v1.0.0\n"
        if source_type == "managed"
        else "source:\n      type: linked\n"
    )
    config = root / "yia.yml"
    config.write_text(
        "version: 2\nproject:\n  name: demo\nenvironment:\n"
        "  domain: demo.localhost\napplications:\n  api:\n"
        f"    type: php\n    path: {path}\n    runtime:\n      php: '8.2'\n    {source}",
        encoding="utf-8",
    )
    return config


def _git(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_managed_tag_clone_and_idempotence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git("init", "-b", "main", cwd=upstream)
    _git("config", "user.email", "test@example.test", cwd=upstream)
    _git("config", "user.name", "Test", cwd=upstream)
    (upstream / "index.php").write_text("v1", encoding="utf-8")
    _git("add", ".", cwd=upstream)
    _git("commit", "-m", "initial", cwd=upstream)
    _git("tag", "v1.0.0", cwd=upstream)
    bare = tmp_path / "repo.git"
    _git("clone", "--bare", str(upstream), str(bare))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.file://" + str(bare) + ".insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "git@example.test:repo")

    root = tmp_path / "consumer"
    root.mkdir()
    config = load_normalized_config(_config(root), SCHEMA)
    synchronize_sources(config)
    destination = root / "apps" / "api"
    assert (destination / "index.php").read_text(encoding="utf-8") == "v1"
    synchronize_sources(config)
    assert (destination / "index.php").read_text(encoding="utf-8") == "v1"

    (destination / "index.php").write_text("modified", encoding="utf-8")
    with pytest.raises(YiaError, match="changements locaux"):
        synchronize_sources(config)
    assert (destination / "index.php").read_text(encoding="utf-8") == "modified"


def test_linked_external_path_is_untouched(tmp_path: Path) -> None:
    root = tmp_path / "consumer"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (external / "index.php").write_text("local", encoding="utf-8")
    config = load_normalized_config(_config(root, source_type="linked", path="../external"), SCHEMA)
    synchronize_sources(config)
    assert config.applications[0].path == external
    assert (external / "index.php").read_text(encoding="utf-8") == "local"


def test_managed_requires_git_fields(tmp_path: Path) -> None:
    path = _config(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("        version: v1.0.0\n", ""), encoding="utf-8")
    with pytest.raises(YiaError):
        load_normalized_config(path, SCHEMA)


def test_linked_cannot_claim_apps_path(tmp_path: Path) -> None:
    (tmp_path / "apps" / "api").mkdir(parents=True)
    with pytest.raises(YiaError):
        load_normalized_config(_config(tmp_path, source_type="linked"), SCHEMA)


def test_managed_rejects_symlink_destination(tmp_path: Path) -> None:
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "other").mkdir()
    (apps / "api").symlink_to(apps / "other", target_is_directory=True)
    with pytest.raises(YiaError):
        load_normalized_config(_config(tmp_path), SCHEMA)


def test_init_and_update_acquire_managed_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    _git("init", "-b", "main", cwd=upstream)
    _git("config", "user.email", "test@example.test", cwd=upstream)
    _git("config", "user.name", "Test", cwd=upstream)
    (upstream / "index.php").write_text("v1", encoding="utf-8")
    _git("add", ".", cwd=upstream)
    _git("commit", "-m", "initial", cwd=upstream)
    _git("tag", "v1.0.0", cwd=upstream)
    bare = tmp_path / "repo.git"
    _git("clone", "--bare", str(upstream), str(bare))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.file://" + str(bare) + ".insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "git@example.test:repo")

    root = tmp_path / "consumer"
    root.mkdir()
    (root / ".yia").symlink_to(SCHEMA.parents[1], target_is_directory=True)
    path = _config(root)
    initialize_project(path, yia_root=SCHEMA.parents[1])
    assert (root / "apps/api/index.php").read_text(encoding="utf-8") == "v1"

    class Compose:
        def converge(self) -> None:
            pass

        def force_recreate_services(self, _services: object) -> None:
            pass

    monkeypatch.setattr("yia.updating.compose_for_project", lambda **_kwargs: Compose())
    first = update_project(load_project(path, require_dependencies=False))
    second = update_project(load_project(path, require_dependencies=False))
    assert first.generation_changed is False
    assert second.generation_changed is False

    (upstream / "index.php").write_text("v2", encoding="utf-8")
    _git("add", ".", cwd=upstream)
    _git("commit", "-m", "second", cwd=upstream)
    _git("tag", "v2.0.0", cwd=upstream)
    _git("push", str(bare), "main", "v2.0.0", cwd=upstream)
    path.write_text(
        path.read_text(encoding="utf-8").replace("version: v1.0.0", "version: v2.0.0"),
        encoding="utf-8",
    )
    update_project(load_project(path, require_dependencies=False))
    assert (root / "apps/api/index.php").read_text(encoding="utf-8") == "v2"

    _git("checkout", "-b", "feature", cwd=upstream)
    (upstream / "index.php").write_text("feature", encoding="utf-8")
    _git("add", ".", cwd=upstream)
    _git("commit", "-m", "feature", cwd=upstream)
    _git("tag", "v3.0.0", cwd=upstream)
    _git("push", str(bare), "feature", "v3.0.0", cwd=upstream)
    path.write_text(
        path.read_text(encoding="utf-8").replace("version: v2.0.0", "version: v3.0.0"),
        encoding="utf-8",
    )
    with pytest.raises(YiaError):
        update_project(load_project(path, require_dependencies=False))
    assert (root / "apps/api/index.php").read_text(encoding="utf-8") == "v2"
