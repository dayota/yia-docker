from __future__ import annotations

from yia.config import ApplicationConfig


NODE_BUILD_CONTEXT = "../../.yia/docker/node"
NODE_HEALTHCHECK_CONTAINER_PATH = "/usr/local/lib/yia/node-healthcheck.js"
SUPPORTED_NODE_VERSIONS = ("22", "24")


def node_service_name(application: ApplicationConfig) -> str:
    if application.type != "node":
        raise ValueError(
            f"application {application.name!r} is not a Node application"
        )
    if application.runtime.version not in SUPPORTED_NODE_VERSIONS:
        raise ValueError(
            f"unsupported Node version {application.runtime.version!r}"
        )
    return f"{application.runtime.name}-{application.name}"
