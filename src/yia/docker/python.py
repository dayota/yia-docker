from __future__ import annotations

from yia.config import ApplicationConfig


PYTHON_BUILD_CONTEXT = "../../.yia/docker/python"
PYTHON_HEALTHCHECK_CONTAINER_PATH = "/usr/local/lib/yia/python-healthcheck.py"
SUPPORTED_PYTHON_VERSIONS = ("3.12",)


def python_service_name(application: ApplicationConfig) -> str:
    if application.type != "python":
        raise ValueError(f"application {application.name!r} is not a Python application")
    if application.runtime.version not in SUPPORTED_PYTHON_VERSIONS:
        raise ValueError(f"unsupported Python version {application.runtime.version!r}")
    return f"{application.runtime.name}-{application.name}"
