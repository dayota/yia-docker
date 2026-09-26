from __future__ import annotations

import argparse
import json
import sys
import sysconfig
from pathlib import Path

from yia import __version__
from yia.config import load_config
from yia.doctor import run_checks
from yia.errors import ErrorCode, YiaError
from yia.validation import validate_config

SCHEMA_VERSION = 1
DOCUMENTATION_SCHEMA_VERSION = 1


def project_root() -> Path:
    return Path.cwd()


def default_schema_path() -> Path:
    candidates = (
        Path(__file__).resolve().parents[2] / "schemas" / "yia.schema.json",
        Path(sysconfig.get_path("data"))
        / "share"
        / "yia"
        / "schemas"
        / "yia.schema.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise YiaError(
        ErrorCode.GENERIC,
        "Le schéma de configuration Yia est introuvable.",
        {"searched_paths": [str(candidate) for candidate in candidates]},
    )


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
            print(f"- {check['name']}: {check['status']} ({check.get('details', '')})")


def cmd_version(args: argparse.Namespace) -> int:
    payload = {
        "status": "ok",
        "yia_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "documentation_schema": DOCUMENTATION_SCHEMA_VERSION,
    }
    if args.json:
        emit(payload, as_json=True)
    else:
        print(f"Yia {__version__}")
        print(f"schema {SCHEMA_VERSION}")
        print(f"documentation schema {DOCUMENTATION_SCHEMA_VERSION}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    root = project_root()
    config_path = (root / args.config).resolve()
    config = load_config(config_path)
    validate_config(config, default_schema_path(), project_root=config_path.parent)
    emit(
        {
            "status": "ok",
            "message": "Configuration valide.",
            "config": str(config_path),
        },
        as_json=args.json,
    )
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    payload = run_checks()
    emit(payload, as_json=args.json)
    return 0 if payload["status"] != "error" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yia")
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="Afficher les versions Yia et schémas.")
    p_version.add_argument("--json", action="store_true")
    p_version.set_defaults(func=cmd_version)

    p_validate = sub.add_parser("validate", help="Valider yia.yml.")
    p_validate.add_argument("--config", default="yia.yml")
    p_validate.add_argument("--json", action="store_true")
    p_validate.set_defaults(func=cmd_validate)

    p_doctor = sub.add_parser("doctor", help="Diagnostiquer les dépendances de base.")
    p_doctor.add_argument("--json", action="store_true")
    p_doctor.set_defaults(func=cmd_doctor)

    # Reserved internal CLI commands for future implementation.
    for name in ("init", "update"):
        p = sub.add_parser(name, help=f"Commande {name} (réservée, non implémentée).")
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=lambda _args, n=name: (
            print(f"{n}: non implémenté dans le squelette initial") or 1
        ))

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
