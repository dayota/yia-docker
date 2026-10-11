from __future__ import annotations

import re
from typing import Any


def traefik_errors(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate exposure without echoing arbitrary label keys or values."""
    traefik = config.get("traefik")
    if not isinstance(traefik, dict):
        return []
    errors: list[dict[str, Any]] = []

    def error(path: str, message: str) -> None:
        errors.append({"path": path, "message": message, "constraint": "traefik_contract"})

    network = traefik["network"]
    if network == config["project"]["name"] + "_yia":
        error("traefik.network", "external network must differ from the private project network")
    available: set[str] = set()
    infrastructure: set[str] = set()
    for name, service in config.get("services", {}).items():
        if service.get("enabled", True):
            available.add(name)
            infrastructure.add(name)
    web = False
    for name, app in config["applications"].items():
        kind = app["type"]
        version = app["runtime"][kind]
        available.add(f"{kind}-{version}" if kind == "php" else f"{kind}-{version}-{name}")
        web = web or "web" in app
    if web:
        available.add("apache")
    targets = traefik.get("containers", {})
    if web and not targets.get("apache", {}).get("expose", False):
        error("traefik.containers.apache.expose", "web applications require explicit Apache exposure")
    for name, target in sorted(targets.items()):
        path = f"traefik.containers.{name}"
        if name not in available:
            error(path, "target must be an enabled generated Compose service")
        expose = target.get("expose", False)
        if expose and name != "apache" and name not in infrastructure:
            error(path + ".expose", "application HTTP routing must remain through Apache")
        for key, value in target.get("labels", {}).items():
            label_path = path + ".labels"
            if key == "traefik.enable" and value != str(expose).lower():
                error(label_path, "traefik.enable must match the explicit expose decision")
            if key == "traefik.docker.network" and (not expose or value != network):
                error(label_path, "traefik.docker.network must match the authorized external network")
            if not expose and re.match(r"traefik\.(http|tcp|udp)\.(routers|services)\.", key):
                error(label_path, "routing labels require explicit expose: true")
            if re.search(
                r"(?:^|\.)(?:users|password|token|secret|credentials|cert|key|"
                r"authorization|proxyauthorization|x-api-key|x-auth-token|"
                r"apikey|clientsecret|signingsecret|signingkey|privatekey)(?:\.|$)", key,
            ):
                error(label_path, "inline credentials or certificates are forbidden; use external references")
    return errors
