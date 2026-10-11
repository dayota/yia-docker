from pathlib import Path


def process_errors(config, project_root):
    errors = []

    def error(path, constraint):
        errors.append({"path": path, "constraint": constraint, "message": "invalid PHP process or proxy route"})

    apps = config["applications"]
    services = {name for name, service in config.get("services", {}).items() if service.get("enabled", True)}
    graph = {name: set() for name in services}
    pools = {}
    for name, app in apps.items():
        kind = app["type"]
        runtime = f"{kind}-{app['runtime'][kind]}"
        service = runtime if kind == "php" else f"{runtime}-{name}"
        services.add(service)
        graph.setdefault(service, set())
        if kind == "php": pools[runtime] = pools.get(runtime, 0) + 1
    if any("web" in app for app in apps.values()):
        services.add("apache")
        graph["apache"] = {f"php-{app['runtime']['php']}" if app["type"] == "php" else f"{app['type']}-{app['runtime'][app['type']]}-{name}"
                           for name, app in apps.items() if "web" in app}
    used_ports = {runtime: set(range(9000, 9000 + count)) for runtime, count in pools.items()}
    for name, app in apps.items():
        if app["type"] != "php": continue
        runtime = f"php-{app['runtime']['php']}"
        for process_name, process in app.get("processes", {}).items():
            key = f"applications.{name}.processes.{process_name}"
            port = process.get("port")
            if port is not None:
                if port in used_ports[runtime]: error(key + ".port", "unique_runtime_port")
                used_ports[runtime].add(port)
            for dependency in process.get("depends_on", []):
                if dependency not in services or dependency == runtime:
                    error(key + ".depends_on", "enabled_distinct_dependency")
                else: graph[runtime].add(dependency)
            cwd = Path(process.get("working_directory", "."))
            if cwd.is_absolute(): error(key + ".working_directory", "application_relative_directory")
            if project_root is not None:
                root = (project_root / app["path"]).resolve()
                destination = (root / cwd).resolve()
                managed_absent = app.get("source", {}).get("type") == "managed" and not root.exists()
                if not destination.is_relative_to(root) or (not managed_absent and not destination.is_dir()):
                    error(key + ".working_directory", "existing_contained_directory")
        prefixes = []
        for index, route in enumerate(app.get("web", {}).get("proxy_routes", [])):
            key = f"applications.{name}.web.proxy_routes.{index}"
            backend = app.get("processes", {}).get(route["process"])
            if backend is None or backend.get("port") is None: error(key + ".process", "process_with_port")
            prefix = route["path"]
            if any(prefix.startswith(other) or other.startswith(prefix) for other in prefixes):
                error(key + ".path", "non_overlapping_routes")
            prefixes.append(prefix)
    visiting, visited = set(), set()

    def visit(name):
        if name in visiting: return True
        if name in visited: return False
        visiting.add(name)
        for dependency in graph.get(name, ()):
            if visit(dependency): return True
        visiting.remove(name)
        visited.add(name)
        return False

    if any(visit(name) for name in graph): error("applications", "acyclic_dependencies")
    return errors
