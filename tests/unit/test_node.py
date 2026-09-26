from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_node_images_are_pinned_and_define_required_runtime_tools() -> None:
    expected_bases = {
        "22": "node:22.23.3-bookworm",
        "24": "node:24.21.0-bookworm",
    }

    for version, base in expected_bases.items():
        dockerfile = (ROOT / "docker" / "node" / version / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert dockerfile.startswith(f"FROM {base}\n")
        assert "gosu" in dockerfile
        assert "git" in dockerfile
        assert "openssh-client" in dockerfile
        assert "pnpm@11.27.1" in dockerfile
        assert "yarn --version" in dockerfile


def test_node_entrypoint_preserves_sources_and_drops_privileges() -> None:
    entrypoint = (ROOT / "docker" / "node" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )

    assert 'chown node:node "$modules_directory"' in entrypoint
    assert "chown -R" not in entrypoint
    assert "gosu node" in entrypoint
    assert "YIA_UID and YIA_GID must be greater than zero" in entrypoint


def test_node_development_command_is_lockfile_safe_and_hmr_ready() -> None:
    develop = (ROOT / "docker" / "node" / "develop.sh").read_text(
        encoding="utf-8"
    )

    assert "--frozen-lockfile" in develop
    assert "--no-lockfile" in develop
    assert "--store-dir /home/node/.local/share/pnpm/store" in develop
    assert "PNPM_CONFIG_VERIFY_DEPS_BEFORE_RUN=false" in develop
    assert "npm ci" in develop
    assert "npm install --no-package-lock" in develop
    assert "yarn install --frozen-lockfile" in develop
    assert "yarn install --no-lockfile" in develop
    assert '--host 0.0.0.0 --port "$node_port"' in develop
    assert "run dev" in develop


def test_node_healthcheck_checks_the_declared_port() -> None:
    healthcheck = (
        ROOT / "docker" / "node" / "node-healthcheck.js"
    ).read_text(encoding="utf-8")

    assert "YIA_NODE_PORT" in healthcheck
    assert 'host: "127.0.0.1"' in healthcheck
    assert "process.kill(1, 0)" in healthcheck
