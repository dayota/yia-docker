from yia.config.model import SecretFiles


PHP_APPLICATIONS_PATH = "/yia/php-applications.json"
PHP_BOOTSTRAP = "/usr/local/lib/yia/php-secrets.php"


def secret_target(owner: str, variable: str) -> str:
    return f"/run/yia-secrets/{owner}/{variable}"


def secret_mounts(owner: str, files: SecretFiles) -> list[dict[str, object]]:
    return [
        {"type": "bind", "source": str(path), "target": secret_target(owner, variable),
         "read_only": True, "bind": {"create_host_path": False}}
        for variable, path in files
    ]


def pool_secret_variable(application: str, variable: str) -> str:
    # Hex encoding is injective, including numeric IDs and repeated dashes.
    return f"YIA_SECRET_{application.encode('ascii').hex()}_{variable}"


def application_command(application: str, command: list[str]) -> list[str]:
    return ["php", PHP_BOOTSTRAP, "exec", PHP_APPLICATIONS_PATH, application, *command]
