from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from yia import __version__
from yia.docker.runner import (
    compose_for_project,
    down_project_environment,
    project_container_names,
    project_containers,
    project_networks,
    project_volumes,
    remove_project_environment,
    remove_project_volumes,
    resolve_service,
)
from yia.doctor import run_checks
from yia.errors import ErrorCode, YiaError
from yia.initialization import initialize_project
from yia.project import (
    Project,
    generate_project,
    generation_is_current,
    load_project,
    require_current_generation,
    runtime_project_identity,
)
from yia.resources import schema_path
from yia.system import (
    APT_PACKAGES,
    install_dependencies,
    installation_checks,
    tool_versions,
)
from yia.updating import update_project
from yia.versions import CONFIGURATION_SCHEMA_VERSION, DOCUMENTATION_SCHEMA_VERSION


SCHEMA_VERSION = CONFIGURATION_SCHEMA_VERSION
YIA_ROOT = Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return Path.cwd()


def default_schema_path() -> Path:
    return schema_path("yia.schema.json")


def emit(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return

    status = payload.get("status", "ok").upper()
    print(f"[{status}]")
    if "message" in payload:
        print(payload["message"])
    if "checks" in payload:
        for check in payload["checks"]:
            print(
                f"- {check['name']}: {check['status']} "
                f"({check.get('details', '')})"
            )
    for key in ("project", "configuration", "generation", "environment"):
        if key in payload:
            print(f"- {key}: {payload[key]}")
    for key in ("applications", "runtimes", "urls"):
        if key in payload:
            values = payload[key]
            print(f"- {key}: {', '.join(values) if values else 'aucun'}")
    if "services" in payload:
        for service in payload["services"]:
            health = f", {service['health']}" if service.get("health") else ""
            print(f"- {service['service']}: {service['state']}{health}")


def _project(args: argparse.Namespace, *, require_environment: bool = True) -> Project:
    return load_project(args.config, require_environment=require_environment)


def _compose(project: Project):
    return compose_for_project(
        project_root=project.root,
        project_name=project.config.project.compose_name,
        compose_path=project.compose_path,
        dotenv_path=project.dotenv_path,
    )


def _remove_runtime(project_root_path: Path) -> bool:
    runtime = project_root_path.resolve() / ".yia-runtime"
    if runtime.is_symlink() or runtime.is_file():
        runtime.unlink(missing_ok=True)
        return True
    if runtime.is_dir():
        shutil.rmtree(runtime)
        return True
    return False


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(YIA_ROOT), "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def cmd_version(args: argparse.Namespace) -> int:
    tools = tool_versions()
    payload = {
        "status": "ok",
        "yia_version": __version__,
        "git_commit": _git_commit(),
        "schema_version": SCHEMA_VERSION,
        "documentation_schema": DOCUMENTATION_SCHEMA_VERSION,
        "tools": tools,
    }
    if args.json:
        emit(payload, as_json=True)
    else:
        print(f"Yia {__version__}")
        print(f"commit {payload['git_commit'] or 'indisponible'}")
        print(f"schema {SCHEMA_VERSION}")
        print(f"documentation schema {DOCUMENTATION_SCHEMA_VERSION}")
        print("outils détectés")
        for name, version in tools.items():
            print(f"- {name}: {version or 'indisponible'}")
    return 0


def cmd_install(_args: argparse.Namespace) -> int:
    print("Paquets APT à installer :")
    for package in APT_PACKAGES:
        print(f"- {package}")
    install_dependencies()
    print("Dépendances Yia installées.")
    return 0


def cmd_check_install(args: argparse.Namespace) -> int:
    checks = installation_checks(
        project_root=Path(args.project_root),
        yia_root=YIA_ROOT,
    )
    status = (
        "error"
        if any(check["status"] == "error" for check in checks)
        else "ok"
    )
    emit({"status": status, "checks": checks}, as_json=False)
    if status == "ok":
        return 0
    daemon = next(check for check in checks if check["name"] == "docker-daemon")
    dependencies = [
        check
        for check in checks
        if check["name"] != "docker-daemon" and check["status"] == "error"
    ]
    return 5 if daemon["status"] == "error" and not dependencies else 3


def cmd_validate(args: argparse.Namespace) -> int:
    project = _project(args)
    emit(
        {
            "status": "ok",
            "message": "Configuration et environnement valides.",
            "config": str(project.config_path),
        },
        as_json=args.json,
    )
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    project = _project(args, require_environment=False)
    print(
        json.dumps(
            project.config.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    project = _project(args)
    result = generate_project(project)
    emit(
        {
            "status": "ok",
            "message": (
                "Artefacts Yia générés."
                if result.changed
                else "Artefacts Yia déjà à jour."
            ),
        },
        as_json=False,
    )
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    result = initialize_project(args.config, yia_root=YIA_ROOT)
    print("[OK]")
    print("Projet Yia initialisé.")
    print(f"- projet : {result.project}")
    print(f"- configuration : {result.config_path}")
    print(
        "- fichiers projet créés : "
        + (", ".join(result.created_project_files) or "aucun")
    )
    print(
        "- fichiers projet préservés : "
        + (", ".join(result.preserved_project_files) or "aucun")
    )
    print(
        "- génération : "
        + ("mise à jour" if result.generation_changed else "déjà à jour")
    )
    print(
        "- documentation : "
        + ("mise à jour" if result.documentation.changed else "déjà à jour")
    )
    print(
        "- applications : " + (", ".join(result.applications) or "aucune")
    )
    print("- runtimes : " + (", ".join(result.runtimes) or "aucun"))
    print("- services : " + (", ".join(result.services) or "aucun"))
    print("- URLs : " + (", ".join(result.urls) or "aucune"))
    print("- prochaine commande : make up")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    project = _project(args)
    result = update_project(project)
    print("[OK]")
    print("Projet Yia synchronisé avec yia.yml.")
    print(f"- projet : {result.project}")
    print(
        "- génération : "
        + ("mise à jour" if result.generation_changed else "déjà à jour")
    )
    print(
        "- documentation : "
        + ("mise à jour" if result.documentation.changed else "déjà à jour")
    )
    print(
        "- Docker : "
        + (
            "services convergés et healthchecks validés"
            if result.compose_applied
            else "aucun service déclaré"
        )
    )
    if result.forced_services:
        print("- services recréés : " + ", ".join(result.forced_services))
    print("- données persistantes : préservées")
    return 0


def cmd_up(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    _compose(project).up()
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    root, project_name = runtime_project_identity(args.config)
    down_project_environment(root, project_name)
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    _compose(project).restart()
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    _compose(project).build()
    return 0


def cmd_rebuild(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    compose = _compose(project)
    compose.build(no_cache=True)
    compose.recreate()
    return 0


def _services_payload(project: Project) -> list[dict[str, str | None]]:
    return [
        container.to_dict()
        for container in project_containers(
            project.root,
            project.config.project.compose_name,
        )
    ]


def cmd_ps(args: argparse.Namespace) -> int:
    project = _project(args, require_environment=False)
    services = _services_payload(project)
    emit(
        {
            "status": "ok",
            "project": project.config.project.name,
            "services": services,
        },
        as_json=args.json,
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project = _project(args)
    current = generation_is_current(project)
    services = _services_payload(project)
    if not services:
        environment = "stopped"
        status = "warning"
    elif any(
        service["state"] != "running"
        or service["health"] not in {None, "healthy"}
        for service in services
    ):
        environment = "degraded"
        status = "error"
    else:
        environment = "running"
        status = "ok" if current else "warning"

    payload = {
        "status": status,
        "configuration": "valid",
        "generation": "current" if current else "stale",
        "environment": environment,
        "project": project.config.project.name,
        "applications": [
            application.name for application in project.config.applications
        ],
        "runtimes": list(project.config.runtime_names),
        "versions": {
            "yia": __version__,
            "schema": project.config.schema_version,
            "postgres": (
                project.config.services.postgres.version
                if project.config.services.postgres is not None
                else None
            ),
        },
        "urls": sorted(
            f"http://{application.web.hostname}"
            for application in project.config.applications
            if application.web is not None
        ),
        "services": services,
    }
    emit(payload, as_json=args.json)
    return 1 if status == "error" else 0


def cmd_doctor(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    project = _project(args) if config_path.is_file() else None
    payload = run_checks(project, yia_root=YIA_ROOT)
    emit(payload, as_json=args.json)
    return 0 if payload["status"] != "error" else 1


def cmd_logs(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    service = (
        resolve_service(project.config, args.service)
        if args.service is not None
        else None
    )
    _compose(project).logs(service, follow=args.follow)
    return 0


def cmd_shell(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    service = resolve_service(project.config, args.service)
    _compose(project).shell(service)
    return 0


def cmd_exec(args: argparse.Namespace) -> int:
    project = _project(args)
    require_current_generation(project)
    service = resolve_service(project.config, args.service)
    command = shlex.split(args.command)
    if not command:
        raise YiaError(
            ErrorCode.GENERIC,
            "CMD doit contenir une commande non vide.",
        )
    _compose(project).execute(service, command)
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    root = Path(args.config).resolve().parent
    changed = _remove_runtime(root)
    emit(
        {
            "status": "ok",
            "message": (
                "Artefacts .yia-runtime supprimés."
                if changed
                else "Aucun artefact .yia-runtime à supprimer."
            ),
        },
        as_json=False,
    )
    return 0


def cmd_reset(args: argparse.Namespace) -> int:
    project = _project(args)
    if project.compose_path.is_file():
        root, project_name = runtime_project_identity(args.config)
        down_project_environment(root, project_name)
    _remove_runtime(project.root)
    generate_project(project)
    compose = _compose(project)
    compose.build()
    compose.up()
    return 0


def cmd_destroy(args: argparse.Namespace) -> int:
    root, project_name = runtime_project_identity(args.config)
    containers = project_container_names(root, project_name)
    networks = project_networks(root, project_name)
    print("Ressources Docker Yia à supprimer :")
    print(f"- containers : {', '.join(containers) if containers else 'aucun'}")
    print(f"- réseaux : {', '.join(networks) if networks else 'aucun'}")
    print("- volumes persistants : conservés")
    remove_project_environment(root, project_name)
    _remove_runtime(root)
    return 0


def cmd_destroy_data(args: argparse.Namespace) -> int:
    root, project_name = runtime_project_identity(args.config)
    volumes = project_volumes(root, project_name)
    print("Données persistantes Yia à supprimer :")
    print(f"- volumes : {', '.join(volumes) if volumes else 'aucun'}")
    if not args.yes:
        try:
            confirmation = input(f"Saisir {project_name!r} pour confirmer : ")
        except EOFError as exc:
            raise YiaError(
                ErrorCode.GENERIC,
                "La suppression des données nécessite une confirmation "
                "interactive ou YES=1.",
            ) from exc
        if confirmation != project_name:
            raise YiaError(
                ErrorCode.GENERIC,
                "Suppression des données annulée.",
            )
    remove_project_environment(root, project_name)
    remove_project_volumes(root, volumes)
    _remove_runtime(root)
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    if root == YIA_ROOT:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=YIA_ROOT,
            check=False,
        )
        return result.returncode
    _project(args)
    emit(
        {"status": "ok", "message": "Validation Yia du projet réussie."},
        as_json=False,
    )
    return 0


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="yia.yml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yia")
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="Afficher les versions Yia et schémas.")
    p_version.add_argument("--json", action="store_true")
    p_version.set_defaults(func=cmd_version)

    p_install = sub.add_parser("install", help="Installer les dépendances via APT.")
    p_install.set_defaults(func=cmd_install)

    p_check = sub.add_parser("check-install", help="Vérifier les prérequis système.")
    p_check.add_argument("--project-root", default=".")
    p_check.set_defaults(func=cmd_check_install)

    p_validate = sub.add_parser("validate", help="Valider yia.yml et .env.")
    _add_config_argument(p_validate)
    p_validate.add_argument("--json", action="store_true")
    p_validate.set_defaults(func=cmd_validate)

    p_config = sub.add_parser("config", help="Afficher la configuration normalisée.")
    _add_config_argument(p_config)
    p_config.set_defaults(func=cmd_config)

    p_generate = sub.add_parser("generate", help="Générer .yia-runtime.")
    _add_config_argument(p_generate)
    p_generate.set_defaults(func=cmd_generate)

    for name, handler in (
        ("up", cmd_up),
        ("down", cmd_down),
        ("restart", cmd_restart),
        ("build", cmd_build),
        ("rebuild", cmd_rebuild),
        ("reset", cmd_reset),
        ("destroy", cmd_destroy),
        ("clean", cmd_clean),
    ):
        command = sub.add_parser(name)
        _add_config_argument(command)
        command.set_defaults(func=handler)

    p_ps = sub.add_parser("ps", help="Afficher les containers du projet.")
    _add_config_argument(p_ps)
    p_ps.add_argument("--json", action="store_true")
    p_ps.set_defaults(func=cmd_ps)

    p_status = sub.add_parser("status", help="Afficher l'état fonctionnel du projet.")
    _add_config_argument(p_status)
    p_status.add_argument("--json", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_doctor = sub.add_parser("doctor", help="Diagnostiquer l'environnement.")
    _add_config_argument(p_doctor)
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    p_logs = sub.add_parser("logs", help="Afficher les logs sans suivi par défaut.")
    _add_config_argument(p_logs)
    p_logs.add_argument("--service")
    p_logs.add_argument("--follow", action="store_true")
    p_logs.set_defaults(func=cmd_logs)

    p_shell = sub.add_parser("shell", help="Ouvrir un shell dans un service.")
    _add_config_argument(p_shell)
    p_shell.add_argument("--service", required=True)
    p_shell.set_defaults(func=cmd_shell)

    p_exec = sub.add_parser("exec", help="Exécuter une commande dans un service.")
    _add_config_argument(p_exec)
    p_exec.add_argument("--service", required=True)
    p_exec.add_argument("--command", required=True)
    p_exec.set_defaults(func=cmd_exec)

    p_destroy_data = sub.add_parser(
        "destroy-data",
        help="Supprimer explicitement les volumes persistants.",
    )
    _add_config_argument(p_destroy_data)
    p_destroy_data.add_argument("--yes", action="store_true")
    p_destroy_data.set_defaults(func=cmd_destroy_data)

    p_test = sub.add_parser("test", help="Exécuter les tests ou validations Yia.")
    _add_config_argument(p_test)
    p_test.add_argument("--project-root", default=".")
    p_test.set_defaults(func=cmd_test)

    p_init = sub.add_parser("init", help="Initialiser un projet consommateur.")
    _add_config_argument(p_init)
    p_init.set_defaults(func=cmd_init)

    p_update = sub.add_parser(
        "update",
        help="Faire converger le projet vers yia.yml.",
    )
    _add_config_argument(p_update)
    p_update.set_defaults(func=cmd_update)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return int(args.func(args))
    except YiaError as exc:
        if getattr(args, "json", False):
            print(json.dumps(exc.to_dict(), ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR [{exc.code.value}] {exc.message}", file=sys.stderr)
            if exc.details:
                print(json.dumps(exc.details, ensure_ascii=False, indent=2), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
