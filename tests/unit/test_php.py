from pathlib import Path

from yia.config import NormalizedConfig, load_normalized_config, normalize_config
from yia.docker import ApacheGenerator, PhpGenerator
from yia.generators import GenerationContext, GenerationEngine
from yia.state import YiaState


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "yia.schema.json"


def _fixture_config(name: str) -> NormalizedConfig:
    project_root = ROOT / "tests" / "projects" / name
    return load_normalized_config(project_root / "yia.yml", SCHEMA)


def _context(config: NormalizedConfig) -> GenerationContext:
    return GenerationContext(config=config, state=YiaState.from_config(config))


def _php_files(config: NormalizedConfig):
    return tuple(PhpGenerator().generate(_context(config)))


def test_php_is_not_generated_without_php_application() -> None:
    assert _php_files(_fixture_config("minimal")) == ()
    assert _php_files(_fixture_config("node-only")) == ()


def test_php_generates_one_deterministic_configuration_per_runtime() -> None:
    config = _fixture_config("multi-php")

    first = _php_files(config)
    second = _php_files(config)

    assert first == second
    assert tuple(file.path for file in first) == (
        "php/8.2/fpm-pools.conf",
        "php/8.4/fpm-pools.conf",
    )
    assert all(file.mode == 0o644 for file in first)
    assert "[legacy]" in first[0].content.decode("utf-8")
    assert "[api]" in first[1].content.decode("utf-8")


def test_shared_runtime_isolates_pools_ports_and_xdebug(tmp_path: Path) -> None:
    for name in ("api", "worker"):
        (tmp_path / "apps" / name).mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "shared-php"},
            "environment": {"domain": "shared-php.localhost"},
            "applications": {
                "worker": {
                    "type": "php",
                    "path": "apps/worker",
                    "runtime": {"php": "8.4"},
                },
                "api": {
                    "type": "php",
                    "path": "apps/api",
                    "runtime": {"php": "8.4", "xdebug": True},
                },
            },
        },
        project_root=tmp_path,
    )

    content = _php_files(config)[0].content.decode("utf-8")

    assert content.index("[api]") < content.index("[worker]")
    assert "[api]\nuser = yia\ngroup = yia\nlisten = 0.0.0.0:9000" in content
    assert "chdir = /workspace/api" in content
    assert "php_admin_value[xdebug.start_with_request] = trigger" in content
    assert "[worker]\nuser = yia\ngroup = yia\nlisten = 0.0.0.0:9001" in content
    assert "chdir = /workspace/worker" in content
    assert "php_admin_value[xdebug.start_with_request] = no" in content


def test_apache_routes_each_php_application_to_its_pool(tmp_path: Path) -> None:
    for name in ("api", "backoffice"):
        (tmp_path / "apps" / name / "public").mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "shared-php"},
            "environment": {"domain": "shared-php.localhost"},
            "applications": {
                name: {
                    "type": "php",
                    "path": f"apps/{name}",
                    "runtime": {"php": "8.4"},
                    "web": {
                        "hostname": f"{name}.shared-php.localhost",
                        "public_directory": "public",
                    },
                }
                for name in ("api", "backoffice")
            },
        },
        project_root=tmp_path,
    )

    content = tuple(ApacheGenerator().generate(_context(config)))[0].content.decode()

    assert 'SetHandler "proxy:fcgi://php-8.4:9000"' in content
    assert 'SetHandler "proxy:fcgi://php-8.4:9001"' in content


def test_php_generator_integrates_with_idempotent_engine(tmp_path: Path) -> None:
    (tmp_path / "apps" / "api").mkdir(parents=True)
    config = normalize_config(
        {
            "version": 1,
            "project": {"name": "php-runtime"},
            "environment": {"domain": "php-runtime.localhost"},
            "applications": {
                "api": {
                    "type": "php",
                    "path": "apps/api",
                    "runtime": {"php": "8.4"},
                }
            },
        },
        project_root=tmp_path,
    )
    engine = GenerationEngine([PhpGenerator()])

    first = engine.generate(config)
    content = (tmp_path / ".yia-runtime/php/8.4/fpm-pools.conf").read_bytes()
    second = engine.generate(config)

    assert first.changed is True
    assert second.changed is False
    assert (
        tmp_path / ".yia-runtime/php/8.4/fpm-pools.conf"
    ).read_bytes() == content
    assert second.manifest.generators == ("php-fpm",)


def test_php_images_are_pinned_and_define_required_runtime_tools() -> None:
    expected_bases = {
        "8.2": "php:8.2.33-fpm-alpine3.24",
        "8.4": "php:8.4.25-fpm-alpine3.24",
    }
    for version, base in expected_bases.items():
        dockerfile = (ROOT / "docker" / "php" / version / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert f"FROM {base}\n" in dockerfile
        assert "FROM composer:2.10.3" in dockerfile
        for extension in (
            "bcmath",
            "intl",
            "mbstring",
            "opcache",
            "pcntl",
            "pdo_mysql",
            "pdo_pgsql",
            "zip",
        ):
            assert extension in dockerfile
        assert "xdebug-3.5.3" in dockerfile

    xdebug = (ROOT / "docker" / "php" / "xdebug.ini").read_text(
        encoding="utf-8"
    )
    assert "xdebug.mode=debug" in xdebug
    assert "xdebug.start_with_request=no" in xdebug
    assert "xdebug.client_host=host.docker.internal" in xdebug

    entrypoint = (ROOT / "docker" / "php" / "entrypoint.sh").read_text(
        encoding="utf-8"
    )
    assert "su-exec yia" in entrypoint
    assert "chown yia:yia \"$vendor_directory\"" in entrypoint
    assert "chown -R" not in entrypoint
