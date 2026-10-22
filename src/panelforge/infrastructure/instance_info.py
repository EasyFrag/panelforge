"""Local identity captured once when the application is constructed."""

from datetime import UTC, datetime
import hashlib
import os
from pathlib import Path
import subprocess

from panelforge import __version__


def _git(root, *args):
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-C", str(root), *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=3, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _source_digest(root):
    digest = hashlib.sha256()
    try:
        paths = [root / "pyproject.toml"]
        for directory in (root / "src" / "panelforge", root / "scripts"):
            paths.extend(p for p in directory.rglob("*") if p.suffix in {".py", ".js", ".css", ".html"})
        for path in sorted(paths):
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                return None
            content = path.read_bytes().replace(b"\r\n", b"\n")
            digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            digest.update(str(len(content)).encode("ascii") + b"\0" + content)
    except OSError:
        return None
    return digest.hexdigest()


def capture_instance_info(source_root, workspace):
    root = Path(source_root).resolve()
    started_at = datetime.now(UTC).isoformat()
    status = _git(root, "status", "--porcelain", "--untracked-files=all", "--",
                  "src/panelforge", "scripts", "workflows", "pyproject.toml")
    return {
        "version": __version__,
        "started_at": started_at,
        "pid": os.getpid(),
        "source_root": str(root),
        "workspace": str(Path(workspace).resolve()),
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_branch": _git(root, "symbolic-ref", "--short", "HEAD"),
        "git_modified": bool(status) if status is not None else None,
        "source_sha256": _source_digest(root),
    }
