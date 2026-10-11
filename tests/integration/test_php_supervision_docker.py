"""Opt-in recipe: synthetic PHP backend; no Laravel dependency installation."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import time
import uuid

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(
    os.environ.get("YIA_RUN_DOCKER_INTEGRATION") != "1",
    reason="Docker recette requires explicit YIA_RUN_DOCKER_INTEGRATION=1",
)


def test_file_secrets_supervision_and_apache_protocols(tmp_path):
    root = tmp_path / "project"
    shutil.copytree(ROOT / "tests/projects/php-supervised", root)
    (root / ".yia").symlink_to(ROOT, target_is_directory=True)
    secret = tmp_path / "external-secret"
    sentinel = "synthetic-" + uuid.uuid4().hex
    secret.write_text(sentinel + "\n")
    raw = yaml.safe_load((root / "yia.yml").read_text())
    name = "yia-supervised-" + uuid.uuid4().hex[:8]
    raw["project"]["name"] = name
    raw["applications"]["api"]["secret_files"] = {"DB_PASSWORD": str(secret)}
    raw["services"] = {
        "postgres": {"version": "18", "secret_files": {"POSTGRES_PASSWORD": str(secret)}},
        "redis": {"version": "7.4", "secret_files": {"REDIS_PASSWORD": str(secret)}},
    }
    (root / "yia.yml").write_text(yaml.safe_dump(raw))
    override = root / "recipe.yaml"
    override.write_text("services:\n  apache:\n    ports: !reset []\n")

    def run(arguments, timeout=900, check=True, input_text=None):
        result = subprocess.run(arguments, cwd=root, capture_output=True, text=True, timeout=timeout, input=input_text)
        if check:
            assert result.returncode == 0, result.stderr
        return result

    def make(*arguments, check=True):
        return run(["make", "-f", str(ROOT / "Makefile"), *arguments], check=check)

    def compose(*arguments, check=True):
        return run(["docker", "compose", "-p", name, "-f", str(root / ".yia-runtime/compose/compose.yaml"),
                    "-f", str(override), *arguments], check=check)

    def php(code):
        return make("exec", "SERVICE=api", "CMD=" + shlex.join(["php", "-r", code])).stdout

    def request(path, headers=""):
        # Send through Apache from the private network; never publish a host port.
        payload = f"GET {path} HTTP/1.1\r\nHost: php-supervised.localhost\r\n{headers}\r\n"
        code = '$s=stream_socket_client("tcp://apache:80",$e,$m,5);stream_set_timeout($s,5);fwrite($s,' + json.dumps(payload) + ');echo base64_encode(stream_get_contents($s));'
        return base64.b64decode(php(code)).decode("latin1")

    try:
        make("validate")
        make("generate")
        snapshot = {p: p.read_bytes() for p in (root / ".yia-runtime").rglob("*") if p.is_file()}
        make("generate")
        assert snapshot == {p: p.read_bytes() for p in snapshot}
        assert all(sentinel.encode() not in content for content in snapshot.values())
        make("build")
        compose("up", "-d", "--wait")
        compose("exec", "-T", "apache", "httpd", "-t")
        assert "Apache/2.4.69 " in compose("exec", "-T", "apache", "httpd", "-v").stdout
        expected_hash = hashlib.sha256(sentinel.encode()).hexdigest()
        assert php('echo hash("sha256",getenv("DB_PASSWORD"));') == expected_hash
        assert expected_hash in request("/", "Connection: close\r\n")
        publication = request("/apps/publish", "Connection: close\r\n")
        assert '"path":"\\/apps\\/publish"' in publication
        assert '"host":"php-supervised.localhost"' in publication
        assert '"proto":"http"' in publication
        websocket = "Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        reply = request("/app/test", websocket)
        assert "101 Switching Protocols" in reply
        assert "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=" in reply
        assert "synthetic-event" in reply
        assert "403 Forbidden" in request("/app/test", websocket + "Origin: https://forbidden.invalid\r\n")
        started = time.monotonic()
        slow_reply = request("/apps/slow", "Connection: close\r\n")
        # mod_proxy_http can report a read timeout as 502, not only 504.
        assert slow_reply.startswith(("HTTP/1.1 502 ", "HTTP/1.1 504 "))
        assert time.monotonic() - started < 3  # Backend deliberately sleeps 3s.
        containers = compose("ps", "-q").stdout.split()
        metadata = run(["docker", "inspect", *containers]).stdout
        assert sentinel not in metadata
        assert sentinel not in compose("logs", "--no-color").stdout
        # Runtime tmpfs contains state only, not secret values.
        runtime_state = compose("exec", "-T", "php-8.4", "sh", "-c", "cat /run/yia-php/*.json").stdout
        assert sentinel not in runtime_state
        # Search only this test's data/caches, with the synthetic pattern on
        # stdin rather than exposing a password in command arguments.
        for service, directories in (("postgres", ["/var/lib/postgresql"]),
                                     ("redis", ["/data"]),
                                     ("php-8.4", ["/workspace/api", "/run/yia-php"])):
            container = compose("ps", "-q", service).stdout.strip()
            scanned = run(["docker", "exec", "-i", container, "grep", "-r", "-q", "-F", "-f", "/dev/stdin", *directories],
                          check=False, input_text=sentinel + "\n")
            assert scanned.returncode == 1, "Synthetic secret found, or scan failed: " + service
        status = json.loads(make("status", "FORMAT=json").stdout)
        assert all(item["state"] == "running" for item in status["processes"].values())
        previous_id = compose("ps", "-q", "php-8.4").stdout.strip()
        replacement = tmp_path / "replacement"
        replacement.write_text(sentinel + "-rotated\n")
        replacement.replace(secret)
        make("reload-secrets")
        reloaded_id = compose("ps", "-q", "php-8.4").stdout.strip()
        assert reloaded_id != previous_id
        assert php('echo hash("sha256",getenv("DB_PASSWORD"));') == hashlib.sha256((sentinel + "-rotated").encode()).hexdigest()
        # Killing only the backend must degrade health without restarting FPM/worker.
        compose("exec", "-T", "php-8.4", "php", "-r",
                '$s=json_decode(file_get_contents("/run/yia-php/state.json"),true);posix_kill($s["processes"]["api/backend"]["pid"],SIGTERM);')
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = json.loads(make("status", "FORMAT=json", check=False).stdout)
            runtime = next(service for service in status["services"] if service["service"] == "php-8.4")
            if status["processes"]["api/backend"]["state"] == "exited" and runtime["health"] == "unhealthy":
                break
            time.sleep(.2)
        assert status["environment"] == "degraded"
        assert status["processes"]["api/backend"]["state"] == "exited"
        assert status["processes"]["api/worker"]["state"] == "running"
        assert runtime["state"] == "running" and runtime["health"] == "unhealthy"
        assert compose("ps", "-q", "php-8.4").stdout.strip() == reloaded_id
        assert run(["docker", "inspect", "--format", "{{.RestartCount}}", reloaded_id]).stdout.strip() == "0"
        assert "503" in request("/apps/publish", "Connection: close\r\n")
        compose("stop")
        assert run(["docker", "inspect", "--format", "{{.State.ExitCode}}", reloaded_id]).stdout.strip() == "0"
    finally:
        # Deletes only disposable volumes belonging to this uniquely named test.
        if (root / ".yia-runtime/compose/compose.yaml").is_file():
            compose("down", "--volumes", check=False)
