import json

from yia.docker.secrets import PHP_APPLICATIONS_PATH
from yia.errors import YiaError


def process_status(config, compose):
    result = {}
    for runtime in sorted({app.runtime.name for app in config.applications if app.processes}):
        try:
            response = compose.run(
                ["exec", "-T", runtime, "php", "/usr/local/lib/yia/php-supervisor.php", "status", PHP_APPLICATIONS_PATH],
                capture_output=True, operation="php-process-status",
            )
            payload = json.loads(response.stdout)
        except (YiaError, ValueError, TypeError):
            payload = {}
        if not isinstance(payload, dict): payload = {}
        for app in config.applications:
            if app.runtime.name != runtime: continue
            for process in app.processes:
                id = app.name + "/" + process.name
                status = payload.get(id, {})
                if not isinstance(status, dict): status = {}
                state = status.get("state")
                exit_code = status.get("exit_code")
                result[id] = {"service": runtime, "state": state if state in {"running", "exited"} else "unavailable",
                              "exit_code": exit_code if type(exit_code) is int else None}
    return result
