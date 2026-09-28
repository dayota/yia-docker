from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from yia.config.model import ApplicationConfig, NormalizedConfig
from yia.errors import ErrorCode, YiaError


def _git(application: ApplicationConfig, *args: str, cwd: Path | None = None) -> str:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise YiaError(
            ErrorCode.DEPENDENCY_MISSING,
            "L'opération Git applicative a échoué.",
            {"application": application.name, "operation": args[0], "error_type": type(exc).__name__},
        ) from exc
    if result.returncode:
        raise YiaError(
            ErrorCode.CONFIG_INVALID,
            "La source Git applicative ne correspond pas à yia.yml ou n'est pas accessible.",
            {"application": application.name, "operation": args[0], "exit_code": result.returncode},
        )
    return result.stdout.strip()


def _checkout(application: ApplicationConfig, path: Path, *, force: bool = False) -> None:
    assert application.source is not None and application.source.git is not None
    git = application.source.git
    _git(application, "fetch", "origin", f"+refs/heads/{git.branch}:refs/remotes/origin/{git.branch}", f"refs/tags/{git.version}:refs/tags/{git.version}", cwd=path)
    commit = _git(application, "rev-parse", f"refs/tags/{git.version}^{{commit}}", cwd=path)
    _git(application, "merge-base", "--is-ancestor", commit, f"refs/remotes/origin/{git.branch}", cwd=path)
    if (
        force
        or _git(application, "rev-parse", "HEAD", cwd=path) != commit
        or _git(application, "rev-parse", "--abbrev-ref", "HEAD", cwd=path) != "HEAD"
    ):
        _git(application, "checkout", "--no-overwrite-ignore", "--detach", commit, cwd=path)


def synchronize_sources(config: NormalizedConfig) -> None:
    """Acquire pinned application tags without touching linked sources or dirty trees."""
    for application in config.applications:
        source = application.source
        if source is None or source.type != "managed":
            continue
        assert source.git is not None
        _git(application, "check-ref-format", "--branch", source.git.branch)
        _git(application, "check-ref-format", f"refs/tags/{source.git.version}")
        destination = application.path
        apps = config.project_root / "apps"
        if destination.parent != apps or apps.is_symlink() or destination.is_symlink():
            raise YiaError(
                ErrorCode.CONFIG_INVALID,
                "Le chemin managed doit être un dossier direct et sûr de apps/.",
                {"application": application.name, "path": str(destination)},
            )
        if destination.exists():
            if not destination.is_dir():
                raise YiaError(ErrorCode.CONFIG_INVALID, "La destination Git est occupée.", {"application": application.name, "path": str(destination)})
            top = _git(application, "rev-parse", "--show-toplevel", cwd=destination)
            remote = _git(application, "config", "--get", "remote.origin.url", cwd=destination)
            if Path(top).resolve() != destination or remote != source.git.ssh:
                raise YiaError(ErrorCode.CONFIG_INVALID, "Le dépôt existant ne correspond pas à la source déclarée.", {"application": application.name, "path": str(destination)})
            if _git(application, "status", "--porcelain", "--untracked-files=all", cwd=destination):
                raise YiaError(ErrorCode.CONFIG_INVALID, "Le dépôt applicatif comporte des changements locaux.", {"application": application.name, "path": str(destination)})
            _checkout(application, destination)
            continue
        try:
            apps.mkdir(exist_ok=True)
        except OSError as exc:
            raise YiaError(
                ErrorCode.CONFIG_INVALID,
                "Le répertoire apps/ ne peut pas être créé.",
                {"path": str(apps), "error_type": type(exc).__name__},
            ) from exc
        with tempfile.TemporaryDirectory(prefix=".yia-clone-", dir=apps) as temporary:
            checkout = Path(temporary) / "checkout"
            _git(application, "clone", "--no-checkout", "--", source.git.ssh, str(checkout))
            _checkout(application, checkout, force=True)
            if destination.exists() or destination.is_symlink():
                raise YiaError(ErrorCode.CONFIG_INVALID, "La destination Git est occupée.", {"application": application.name, "path": str(destination)})
            checkout.rename(destination)
