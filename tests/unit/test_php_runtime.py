import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[2]
PHP = shutil.which("php")
pytestmark = pytest.mark.skipif(PHP is None, reason="PHP local requis pour les tests runtime sans Docker")
SECRETS = ROOT / "docker/php/php-secrets.php"
SUPERVISOR = ROOT / "docker/php/php-supervisor.php"


@pytest.mark.parametrize("value,valid", [(b"password\n\n", True), ("é space \n".encode(), True),
                                       (b"internal\nline\n", True), (b" ", True), (b"", False),
                                       (b"\n", False), (b"secret\x00", False), (b"\xff", False),
                                       (b"\xed\xa0\x80", False), (b"\xf4\x90\x80\x80", False)])
def test_php_and_shell_readers_agree_without_logging_values(tmp_path, value, valid):
    secret = tmp_path / "secret"
    secret.write_bytes(value)
    expected = value.rstrip(b"\n")
    code = 'require $argv[1]; try { $value=yia_secret($argv[2]); exit(hash("sha256",$value)===$argv[3] ? 0 : 3); } catch(Throwable $e) {exit(2);}'
    import hashlib
    php = subprocess.run([PHP, "-r", code, str(SECRETS), str(secret), hashlib.sha256(expected).hexdigest()], capture_output=True)
    shell_code = '. "$1"; value=$(yia_read_secret "$2") || exit 2; printf %s "$value" | sha256sum'
    shell = subprocess.run(["sh", "-c", shell_code, "sh", str(ROOT / "docker/redis/read-secret.sh"), str(secret)], capture_output=True)
    assert php.returncode == (0 if valid else 2)
    assert shell.returncode == (0 if valid else 2)
    assert b"secret" not in php.stdout + php.stderr
    if value.strip():
        assert value not in shell.stdout + shell.stderr
    if valid: assert shell.stdout.split()[0].decode() == hashlib.sha256(expected).hexdigest()


def test_pool_injection_namespaces_each_application(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.write_text("first-synthetic\n")
    second.write_text("second-synthetic\n")
    manifest = {"api": {"secret_files": {"DB_PASSWORD": str(first)}}, "backoffice": {"secret_files": {"DB_PASSWORD": str(second)}}}
    code = 'require $argv[1]; $apps=json_decode($argv[2],true); yia_fpm_environment($apps); assert(getenv("YIA_SECRET_617069_DB_PASSWORD")==="first-synthetic"); assert(getenv("YIA_SECRET_6261636b6f6666696365_DB_PASSWORD")==="second-synthetic"); assert(getenv("DB_PASSWORD")==="");'
    result = subprocess.run([PHP, "-d", "zend.assertions=1", "-d", "assert.exception=1", "-r", code, str(SECRETS), json.dumps(manifest)], capture_output=True, env={**os.environ, "DB_PASSWORD": ""})
    # No unnamespaced value is introduced; an existing empty value stays empty.
    assert result.returncode == 0, result.stderr.decode()


def wait_for_state(path, predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            state = json.loads(path.read_text())
            if predicate(state): return state
        except (OSError, ValueError): pass
        time.sleep(.02)
    pytest.fail("supervisor did not reach expected state")


def test_supervisor_records_exit_does_not_restart_and_stops_gracefully(tmp_path):
    manifest = tmp_path / "apps.json"
    marker = tmp_path / "launches"
    stubborn_ready = tmp_path / "stubborn-ready"
    app = {"secret_files": {}, "processes": {
        "exit": {"command": [PHP, "-r", 'file_put_contents($argv[1],"launch\\n",FILE_APPEND); exit(7);', str(marker)], "working_directory": str(tmp_path), "stop_grace_seconds": .2},
        "live": {"command": [PHP, "-r", 'pcntl_async_signals(true);pcntl_signal(SIGTERM,function(){exit(0);});while(true){usleep(100000);}'], "working_directory": str(tmp_path), "stop_grace_seconds": .5},
        "stubborn": {"command": [PHP, "-r", 'pcntl_signal(SIGTERM,SIG_IGN);file_put_contents($argv[1],"ready");while(true){usleep(100000);}', str(stubborn_ready)], "working_directory": str(tmp_path), "stop_grace_seconds": .2},
    }}
    manifest.write_text(json.dumps({"api": app}))
    fpm = [PHP, "-r", 'pcntl_async_signals(true);pcntl_signal(SIGQUIT,function(){exit(0);});while(true){usleep(100000);}']
    code = 'require $argv[1];try {exit(yia_supervise(yia_manifest($argv[2]),json_decode($argv[3],true),$argv[4],false));} catch(Throwable $e) {yia_runtime_error();}'
    state_dir = tmp_path / "state"
    process = subprocess.Popen([PHP, "-r", code, str(SUPERVISOR), str(manifest), json.dumps(fpm), str(state_dir)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        state = wait_for_state(state_dir / "state.json", lambda state: state["processes"]["api/exit"]["state"] == "exited")
        assert state["processes"]["api/exit"]["exit_code"] == 7
        assert state["processes"]["api/live"]["state"] == "running"
        assert process.poll() is None
        health = subprocess.run([PHP, "-r", 'require $argv[1];exit(yia_health(yia_manifest($argv[2]),$argv[3],false)?0:1);', str(SUPERVISOR), str(manifest), str(state_dir)], capture_output=True)
        assert health.returncode == 1
        assert marker.read_text() == "launch\n"
        assert stubborn_ready.is_file()
        duplicate = subprocess.run([PHP, "-r", code, str(SUPERVISOR), str(manifest), json.dumps(fpm), str(state_dir)], capture_output=True)
        assert duplicate.returncode == 2
        assert b"YIA_CONFIG_INVALID" in duplicate.stderr
        assert marker.read_text() == "launch\n"
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=3) == 0
        state = json.loads((state_dir / "state.json").read_text())
        assert all(child["state"] == "exited" for child in state["processes"].values())
        assert state["processes"]["api/stubborn"]["exit_code"] == 128 + signal.SIGKILL
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=3)


def test_custom_healthchecks_success_failure_timeout_and_redaction(tmp_path):
    code = 'require $argv[1];$command=json_decode($argv[2],true);exit(yia_check_command($command,[], $argv[3],.1,false)?0:1);'
    for command, expected in [([PHP, "-r", 'echo "synthetic-do-not-log"; exit(0);'], 0),
                              ([PHP, "-r", 'fwrite(STDERR,"synthetic-do-not-log");exit(3);'], 1),
                              ([PHP, "-r", 'sleep(5);'], 1)]:
        result = subprocess.run([PHP, "-r", code, str(SUPERVISOR), json.dumps(command), str(tmp_path)], capture_output=True, timeout=2)
        assert result.returncode == expected
        assert result.stdout == result.stderr == b""
