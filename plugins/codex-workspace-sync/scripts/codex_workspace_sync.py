#!/usr/bin/env python3
"""Sync Codex workspaces through Git remotes or portable snapshots."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


STORE_DIR = "codex-workspace-sync"
DEFAULT_EXCLUDES = {
    ".DS_Store",
    ".codex-workspace-sync",
    ".next",
    ".npm",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}

DEFAULT_GITIGNORE = [
    ".DS_Store",
    ".codex-workspace-sync/",
    ".env",
    ".env.*",
    ".next/",
    ".npm/",
    ".pnpm-store/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".turbo/",
    ".venv/",
    "__pycache__/",
    "build/",
    "coverage/",
    "dist/",
    "node_modules/",
    "venv/",
]


@dataclass(frozen=True)
class FileRecord:
    path: str
    size: int
    sha256: str


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    result = []
    previous_dash = False
    for char in lowered:
        if char.isalnum():
            result.append(char)
            previous_dash = False
        elif not previous_dash:
            result.append("-")
            previous_dash = True
    return "".join(result).strip("-") or "workspace"


def workspace_name(workspace: Path, explicit_name: str | None) -> str:
    return slugify(explicit_name or workspace.name)


def store_root(sync_root: Path) -> Path:
    return sync_root.expanduser().resolve() / STORE_DIR


def workspace_store(sync_root: Path, name: str) -> Path:
    return store_root(sync_root) / "workspaces" / name


def is_excluded(relative_path: Path, include_heavy: bool, extra_excludes: Iterable[str]) -> bool:
    if include_heavy:
        excludes = {".DS_Store", ".codex-workspace-sync", *extra_excludes}
    else:
        excludes = {*DEFAULT_EXCLUDES, *extra_excludes}

    parts = relative_path.parts
    for part in parts:
        if part in excludes:
            return True
    rel = relative_path.as_posix()
    return any(fnmatch.fnmatch(rel, pattern) for pattern in excludes)


def iter_files(workspace: Path, include_heavy: bool, extra_excludes: Iterable[str]) -> Iterable[Path]:
    for root, dirs, files in os.walk(workspace):
        root_path = Path(root)
        relative_root = root_path.relative_to(workspace)
        dirs[:] = [
            directory
            for directory in dirs
            if not is_excluded(relative_root / directory, include_heavy, extra_excludes)
        ]
        for filename in files:
            relative_file = relative_root / filename
            if not is_excluded(relative_file, include_heavy, extra_excludes):
                yield root_path / filename


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    workspace: Path,
    sync_name: str,
    archive_name: str,
    include_heavy: bool,
    extra_excludes: list[str],
) -> dict:
    records = []
    for file_path in sorted(iter_files(workspace, include_heavy, extra_excludes)):
        relative = file_path.relative_to(workspace).as_posix()
        stat = file_path.stat()
        records.append(
            FileRecord(path=relative, size=stat.st_size, sha256=sha256_file(file_path)).__dict__
        )
    return {
        "schemaVersion": 1,
        "workspaceName": sync_name,
        "sourcePath": str(workspace),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "archive": archive_name,
        "fileCount": len(records),
        "totalBytes": sum(record["size"] for record in records),
        "includeHeavy": include_heavy,
        "extraExcludes": extra_excludes,
        "files": records,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_git(workspace: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_git_stream(workspace: Path, args: list[str]) -> None:
    try:
        subprocess.run(["git", *args], cwd=workspace, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


def ensure_workspace(path: str) -> Path:
    workspace = Path(path).expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist or is not a directory: {workspace}")
    return workspace


def ensure_git_repo(workspace: Path) -> None:
    result = run_git(workspace, ["rev-parse", "--is-inside-work-tree"], check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise SystemExit(f"Workspace is not a Git repository: {workspace}")


def current_branch(workspace: Path) -> str:
    result = run_git(workspace, ["branch", "--show-current"])
    branch = result.stdout.strip()
    if not branch:
        raise SystemExit("Detached HEAD is not supported for workspace sync.")
    return branch


def git_has_changes(workspace: Path) -> bool:
    result = run_git(workspace, ["status", "--porcelain"])
    return bool(result.stdout.strip())


def git_has_staged_changes(workspace: Path) -> bool:
    result = run_git(workspace, ["diff", "--cached", "--quiet"], check=False)
    return result.returncode == 1


def ensure_remote(workspace: Path, remote: str) -> None:
    result = run_git(workspace, ["remote", "get-url", remote], check=False)
    if result.returncode != 0:
        raise SystemExit(f"Git remote '{remote}' is not configured.")


def append_default_gitignore(workspace: Path) -> None:
    gitignore = workspace / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    existing_set = set(existing)
    additions = [line for line in DEFAULT_GITIGNORE if line not in existing_set]
    if additions:
        with gitignore.open("a", encoding="utf-8") as handle:
            if existing and existing[-1] != "":
                handle.write("\n")
            handle.write("# Codex Workspace Sync defaults\n")
            for line in additions:
                handle.write(f"{line}\n")


def command_git_setup(args: argparse.Namespace) -> int:
    workspace = ensure_workspace(args.workspace)
    if (workspace / ".git").exists():
        ensure_git_repo(workspace)
    else:
        run_git_stream(workspace, ["init", "-b", args.branch])

    if args.gitignore:
        append_default_gitignore(workspace)

    existing_remote = run_git(workspace, ["remote", "get-url", args.remote], check=False)
    if existing_remote.returncode == 0:
        run_git_stream(workspace, ["remote", "set-url", args.remote, args.url])
    else:
        run_git_stream(workspace, ["remote", "add", args.remote, args.url])

    if args.pull:
        run_git_stream(workspace, ["pull", "--no-rebase", args.remote, args.branch])

    print(f"Git sync configured in {workspace}")
    print(f"Remote: {args.remote} -> {args.url}")
    print(f"Branch: {args.branch}")
    return 0


def command_git_status(args: argparse.Namespace) -> int:
    workspace = ensure_workspace(args.workspace)
    ensure_git_repo(workspace)
    branch = current_branch(workspace)
    ensure_remote(workspace, args.remote)

    print(f"Workspace: {workspace}")
    print(f"Branch: {branch}")
    remote_url = run_git(workspace, ["remote", "get-url", args.remote]).stdout.strip()
    print(f"Remote: {args.remote} -> {remote_url}")
    run_git_stream(workspace, ["status", "--short", "--branch"])
    return 0


def command_git_publish(args: argparse.Namespace) -> int:
    workspace = ensure_workspace(args.workspace)
    ensure_git_repo(workspace)
    branch = args.branch or current_branch(workspace)
    ensure_remote(workspace, args.remote)

    commit_workspace_changes(workspace, args.message)

    push_args = ["push"]
    if args.set_upstream:
        push_args.extend(["-u", args.remote, branch])
    else:
        push_args.extend([args.remote, branch])
    run_git_stream(workspace, push_args)
    print(f"Published {workspace} to {args.remote}/{branch}")
    return 0


def commit_workspace_changes(workspace: Path, message: str | None) -> bool:
    run_git_stream(workspace, ["add", "-A"])
    if not git_has_staged_changes(workspace):
        print("No local changes to commit.")
        return False
    commit_message = message or f"Sync workspace {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    run_git_stream(workspace, ["commit", "-m", commit_message])
    return True


def command_git_pull(args: argparse.Namespace) -> int:
    workspace = ensure_workspace(args.workspace)
    ensure_git_repo(workspace)
    branch = args.branch or current_branch(workspace)
    ensure_remote(workspace, args.remote)

    if git_has_changes(workspace) and not args.autostash:
        raise SystemExit("Local changes are present. Commit first or use --autostash.")

    pull_args = ["pull"]
    if args.rebase:
        pull_args.append("--rebase")
    else:
        pull_args.append("--no-rebase")
    if args.autostash:
        pull_args.append("--autostash")
    pull_args.extend([args.remote, branch])

    run_git_stream(workspace, pull_args)
    print(f"Pulled {args.remote}/{branch} into {workspace}")
    return 0


def command_git_sync(args: argparse.Namespace) -> int:
    workspace = ensure_workspace(args.workspace)
    ensure_git_repo(workspace)
    branch = args.branch or current_branch(workspace)
    ensure_remote(workspace, args.remote)

    commit_workspace_changes(workspace, args.message)

    pull_args = argparse.Namespace(
        workspace=str(workspace),
        remote=args.remote,
        branch=branch,
        rebase=args.rebase,
        autostash=False,
    )
    command_git_pull(pull_args)

    push_args = ["push"]
    if args.set_upstream:
        push_args.extend(["-u", args.remote, branch])
    else:
        push_args.extend([args.remote, branch])
    run_git_stream(workspace, push_args)
    print(f"Synced {workspace} with {args.remote}/{branch}")
    return 0


def command_git_clone(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser().resolve()
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"Clone target is not empty: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    clone_args = ["clone"]
    if args.branch:
        clone_args.extend(["--branch", args.branch])
    clone_args.extend([args.url, str(target)])
    try:
        subprocess.run(["git", *clone_args], check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
    print(f"Cloned {args.url} into {target}")
    return 0


def make_archive(
    workspace: Path,
    archive_path: Path,
    include_heavy: bool,
    extra_excludes: list[str],
) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        for file_path in sorted(iter_files(workspace, include_heavy, extra_excludes)):
            archive.add(file_path, arcname=file_path.relative_to(workspace).as_posix())


def command_snapshot(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist or is not a directory: {workspace}")

    sync_root = Path(args.sync_root).expanduser().resolve()
    name = workspace_name(workspace, args.name)
    stamp = utc_stamp()
    archive_name = f"{name}-{stamp}.tar.gz"
    manifest_name = f"{name}-{stamp}.manifest.json"
    target_store = workspace_store(sync_root, name)
    archive_path = target_store / "snapshots" / archive_name
    manifest_path = target_store / "snapshots" / manifest_name

    extra_excludes = args.exclude or []
    manifest = build_manifest(workspace, name, archive_name, args.include_heavy, extra_excludes)
    if args.dry_run:
        print(f"Would snapshot {workspace}")
        print(f"Workspace name: {name}")
        print(f"Files: {manifest['fileCount']}")
        print(f"Bytes: {manifest['totalBytes']}")
        print(f"Archive: {archive_path}")
        return 0

    make_archive(workspace, archive_path, args.include_heavy, extra_excludes)
    write_json(manifest_path, manifest)
    write_json(target_store / "latest.json", manifest)
    print(f"Snapshot created: {archive_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Files: {manifest['fileCount']}")
    return 0


def latest_manifest(sync_root: Path, name: str) -> Path:
    manifest = workspace_store(sync_root, name) / "latest.json"
    if not manifest.is_file():
        raise SystemExit(f"No latest snapshot found for workspace '{name}'.")
    return manifest


def resolve_snapshot(sync_root: Path, name: str, snapshot: str | None) -> tuple[Path, dict]:
    target_store = workspace_store(sync_root, name)
    if snapshot:
        candidate = Path(snapshot).expanduser()
        archive_path = candidate if candidate.is_absolute() else target_store / "snapshots" / snapshot
        if not archive_path.is_file():
            raise SystemExit(f"Snapshot archive not found: {archive_path}")
        manifest_path = archive_path.with_suffix("").with_suffix(".manifest.json")
        manifest = read_json(manifest_path) if manifest_path.is_file() else {"archive": archive_path.name}
        return archive_path, manifest

    manifest = read_json(latest_manifest(sync_root, name))
    archive_path = target_store / "snapshots" / manifest["archive"]
    if not archive_path.is_file():
        raise SystemExit(f"Latest snapshot archive is missing: {archive_path}")
    return archive_path, manifest


def clear_directory(target: Path) -> None:
    for item in target.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()


def ensure_restore_target(target: Path, force: bool, backup_dir: Path) -> None:
    if not target.exists():
        target.mkdir(parents=True)
        return
    if not target.is_dir():
        raise SystemExit(f"Restore target exists and is not a directory: {target}")
    if any(target.iterdir()):
        if not force:
            raise SystemExit(
                f"Restore target is not empty: {target}. Use --force to create a backup and restore anyway."
            )
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"backup-before-restore-{utc_stamp()}.tar.gz"
        with tarfile.open(backup_path, "w:gz") as archive:
            for item in sorted(target.rglob("*")):
                archive.add(item, arcname=item.relative_to(target).as_posix())
        print(f"Backup created: {backup_path}")
        clear_directory(target)


def safe_extract(archive: tarfile.TarFile, target: Path) -> None:
    target_root = target.resolve()
    for member in archive.getmembers():
        member_path = (target / member.name).resolve()
        if target_root != member_path and target_root not in member_path.parents:
            raise SystemExit(f"Refusing to extract unsafe archive member: {member.name}")
    archive.extractall(target)


def command_restore(args: argparse.Namespace) -> int:
    sync_root = Path(args.sync_root).expanduser().resolve()
    name = slugify(args.name)
    archive_path, manifest = resolve_snapshot(sync_root, name, args.snapshot)
    target = Path(args.target).expanduser().resolve()
    backup_dir = workspace_store(sync_root, name) / "restores"

    if args.dry_run:
        print(f"Would restore: {archive_path}")
        print(f"Target: {target}")
        print(f"Files in manifest: {manifest.get('fileCount', 'unknown')}")
        return 0

    ensure_restore_target(target, args.force, backup_dir)
    with tarfile.open(archive_path, "r:gz") as archive:
        safe_extract(archive, target)
    print(f"Restored {archive_path.name} to {target}")
    return 0


def command_list(args: argparse.Namespace) -> int:
    root = store_root(Path(args.sync_root))
    workspaces_dir = root / "workspaces"
    if not workspaces_dir.is_dir():
        print(f"No synced workspaces found under {root}")
        return 0

    for workspace_dir in sorted(path for path in workspaces_dir.iterdir() if path.is_dir()):
        latest = workspace_dir / "latest.json"
        if latest.is_file():
            payload = read_json(latest)
            created_at = payload.get("createdAt", "unknown time")
            file_count = payload.get("fileCount", "unknown")
            archive = payload.get("archive", "unknown archive")
            print(f"{workspace_dir.name}: {created_at} | {file_count} files | {archive}")
        else:
            print(f"{workspace_dir.name}: no latest.json")
    return 0


def local_records(workspace: Path, include_heavy: bool, extra_excludes: list[str]) -> dict[str, FileRecord]:
    records = {}
    for file_path in iter_files(workspace, include_heavy, extra_excludes):
        relative = file_path.relative_to(workspace).as_posix()
        stat = file_path.stat()
        records[relative] = FileRecord(relative, stat.st_size, sha256_file(file_path))
    return records


def command_status(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    if not workspace.is_dir():
        raise SystemExit(f"Workspace does not exist or is not a directory: {workspace}")

    sync_root = Path(args.sync_root).expanduser().resolve()
    name = workspace_name(workspace, args.name)
    manifest = read_json(latest_manifest(sync_root, name))
    synced = {record["path"]: record for record in manifest.get("files", [])}
    local = local_records(workspace, manifest.get("includeHeavy", False), manifest.get("extraExcludes", []))

    added = sorted(set(local) - set(synced))
    removed = sorted(set(synced) - set(local))
    changed = sorted(
        path
        for path in set(local) & set(synced)
        if local[path].sha256 != synced[path].get("sha256")
    )

    print(f"Workspace name: {name}")
    print(f"Latest snapshot: {manifest.get('archive', 'unknown')}")
    print(f"Added locally: {len(added)}")
    print(f"Removed locally: {len(removed)}")
    print(f"Changed locally: {len(changed)}")
    for label, paths in (("added", added), ("removed", removed), ("changed", changed)):
        for path in paths[: args.limit]:
            print(f"{label}: {path}")
        if len(paths) > args.limit:
            print(f"{label}: ... {len(paths) - args.limit} more")
    return 1 if added or removed or changed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    snapshot = subparsers.add_parser("snapshot", help="Create a synced workspace snapshot")
    snapshot.add_argument("--workspace", required=True, help="Workspace directory to archive")
    snapshot.add_argument("--sync-root", required=True, help="Shared sync folder")
    snapshot.add_argument("--name", help="Stable workspace sync name")
    snapshot.add_argument("--exclude", action="append", help="Additional glob or path name to skip")
    snapshot.add_argument("--include-heavy", action="store_true", help="Include generated dependency/build folders")
    snapshot.add_argument("--dry-run", action="store_true", help="Show what would be created")
    snapshot.set_defaults(func=command_snapshot)

    restore = subparsers.add_parser("restore", help="Restore a workspace snapshot")
    restore.add_argument("--name", required=True, help="Workspace sync name")
    restore.add_argument("--sync-root", required=True, help="Shared sync folder")
    restore.add_argument("--target", required=True, help="Directory to restore into")
    restore.add_argument("--snapshot", help="Archive name or absolute archive path")
    restore.add_argument("--force", action="store_true", help="Back up and restore into a non-empty target")
    restore.add_argument("--dry-run", action="store_true", help="Show what would be restored")
    restore.set_defaults(func=command_restore)

    list_parser = subparsers.add_parser("list", help="List synced workspaces")
    list_parser.add_argument("--sync-root", required=True, help="Shared sync folder")
    list_parser.set_defaults(func=command_list)

    status = subparsers.add_parser("status", help="Compare local workspace to latest snapshot")
    status.add_argument("--workspace", required=True, help="Workspace directory to compare")
    status.add_argument("--sync-root", required=True, help="Shared sync folder")
    status.add_argument("--name", help="Stable workspace sync name")
    status.add_argument("--limit", type=int, default=20, help="Number of changed paths to print per group")
    status.set_defaults(func=command_status)

    git_setup = subparsers.add_parser("git-setup", help="Connect a workspace to a GitHub or Git remote")
    git_setup.add_argument("--workspace", required=True, help="Workspace directory to configure")
    git_setup.add_argument("--url", required=True, help="GitHub or Git remote URL")
    git_setup.add_argument("--remote", default="origin", help="Remote name")
    git_setup.add_argument("--branch", default="main", help="Branch to use")
    git_setup.add_argument("--pull", action="store_true", help="Pull the remote branch after setup")
    git_setup.add_argument("--no-gitignore", dest="gitignore", action="store_false", help="Do not add default generated-folder ignores")
    git_setup.set_defaults(func=command_git_setup, gitignore=True)

    git_status = subparsers.add_parser("git-status", help="Show Git sync status for a workspace")
    git_status.add_argument("--workspace", required=True, help="Workspace directory to inspect")
    git_status.add_argument("--remote", default="origin", help="Remote name")
    git_status.set_defaults(func=command_git_status)

    git_publish = subparsers.add_parser("git-publish", help="Commit local changes and push them to the remote")
    git_publish.add_argument("--workspace", required=True, help="Workspace directory to publish")
    git_publish.add_argument("--remote", default="origin", help="Remote name")
    git_publish.add_argument("--branch", help="Branch to push")
    git_publish.add_argument("--message", help="Commit message")
    git_publish.add_argument("--set-upstream", action="store_true", help="Set upstream while pushing")
    git_publish.set_defaults(func=command_git_publish)

    git_pull = subparsers.add_parser("git-pull", help="Pull and merge remote changes into a workspace")
    git_pull.add_argument("--workspace", required=True, help="Workspace directory to update")
    git_pull.add_argument("--remote", default="origin", help="Remote name")
    git_pull.add_argument("--branch", help="Branch to pull")
    git_pull.add_argument("--rebase", action="store_true", help="Rebase instead of merge")
    git_pull.add_argument("--autostash", action="store_true", help="Temporarily stash uncommitted local changes")
    git_pull.set_defaults(func=command_git_pull)

    git_sync = subparsers.add_parser("git-sync", help="Commit local changes, pull remote changes, then push")
    git_sync.add_argument("--workspace", required=True, help="Workspace directory to sync")
    git_sync.add_argument("--remote", default="origin", help="Remote name")
    git_sync.add_argument("--branch", help="Branch to sync")
    git_sync.add_argument("--message", help="Commit message")
    git_sync.add_argument("--rebase", action="store_true", help="Rebase instead of merge while pulling")
    git_sync.add_argument("--set-upstream", action="store_true", help="Set upstream while pushing")
    git_sync.set_defaults(func=command_git_sync)

    git_clone = subparsers.add_parser("git-clone", help="Clone a GitHub or Git remote into a local workspace")
    git_clone.add_argument("--url", required=True, help="GitHub or Git remote URL")
    git_clone.add_argument("--target", required=True, help="Directory to clone into")
    git_clone.add_argument("--branch", help="Branch to clone")
    git_clone.set_defaults(func=command_git_clone)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
