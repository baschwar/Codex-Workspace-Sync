---
name: codex-workspace-sync
description: Sync Codex workspaces across computers using one GitHub remote with multiple local repos, or snapshot folders when Git is not appropriate.
---

# Codex Workspace Sync

Use this skill when the user wants to sync, copy, move, back up, restore, compare,
or inspect Codex workspaces across computers.

Prefer the GitHub workflow when the workspace can be a Git repository. Use the
snapshot workflow only when the user wants archive-style backups or the folder is
not suitable for Git.

## GitHub Workflow

The standard model is one remote repository and two or more local clones:

```text
Local A -> commit -> push -> Remote
Local B <- pull/merge <- Remote
Local B -> commit -> pull/merge -> push -> Remote
Local A <- pull/merge <- Remote
```

1. Identify the local workspace path.
   - Prefer the current working directory when the user says "this workspace".
   - If the user names a folder, use that folder.
2. Identify the GitHub remote.
   - Use SSH or HTTPS URLs, for example `git@github.com:OWNER/REPO.git`.
   - Do not ask for tokens. The helper uses the user's normal Git credentials.
3. Use `scripts/codex_workspace_sync.py`.
   - `git-setup` initializes or configures a local repo and remote.
   - `git-clone` creates another local copy from the remote.
   - `git-publish` stages, commits, and pushes local changes.
   - `git-pull` pulls and merges remote changes into the local workspace.
   - `git-sync` commits local changes, pulls/merges remote changes, then pushes.
   - `git-status` shows local branch, remote, and short Git status.
4. Keep the user safe.
   - Run `git-status` before publishing or pulling when the current state is unclear.
   - If `git-pull` reports local changes, commit first or use `--autostash` only
     when the user explicitly wants that behavior.
   - If a merge conflict occurs, stop and report the conflicted files.

## Git Commands

From the plugin root:

```bash
python3 scripts/codex_workspace_sync.py git-setup --workspace <path> --url <github-url> --branch main
python3 scripts/codex_workspace_sync.py git-clone --url <github-url> --target <path> --branch main
python3 scripts/codex_workspace_sync.py git-status --workspace <path>
python3 scripts/codex_workspace_sync.py git-pull --workspace <path>
python3 scripts/codex_workspace_sync.py git-publish --workspace <path> --message <message>
python3 scripts/codex_workspace_sync.py git-sync --workspace <path> --message <message>
```

Useful options:

- `--remote <name>` defaults to `origin`.
- `--branch <name>` defaults to the current branch after setup.
- `--set-upstream` is useful on the first publish.
- `--rebase` rebases instead of creating a merge commit.
- `--autostash` on `git-pull` temporarily stashes uncommitted local changes.

## Snapshot Workflow

1. Identify the local workspace path.
   - Prefer the current working directory when the user says "this workspace".
   - If the user names a folder, use that folder.
2. Identify the sync root.
   - A sync root is any folder visible on multiple computers, such as iCloud
     Drive, Dropbox, Syncthing, a network share, or an external disk.
   - If the user has not chosen one, ask for the shared folder path before
     creating or restoring snapshots.
3. Use `scripts/codex_workspace_sync.py` from this plugin.
   - `snapshot` creates a timestamped archive plus manifest.
   - `list` shows available workspace snapshots.
   - `status` compares the current workspace with the latest synced manifest.
   - `restore` restores a selected or latest snapshot into a target folder.
4. Keep the user safe.
   - Do not overwrite a non-empty restore target unless the user explicitly asks.
   - When using `restore --force`, the script creates a backup snapshot first.
   - Prefer `--dry-run` for status-like checks or when the user is deciding.

## Snapshot Commands

From the plugin root:

```bash
python3 scripts/codex_workspace_sync.py snapshot --workspace <path> --sync-root <path>
python3 scripts/codex_workspace_sync.py list --sync-root <path>
python3 scripts/codex_workspace_sync.py status --workspace <path> --sync-root <path>
python3 scripts/codex_workspace_sync.py restore --name <workspace-name> --sync-root <path> --target <path>
```

Useful options:

- `--name <name>` gives the workspace a stable sync name.
- `--include-heavy` includes generated dependency/build folders in snapshots.
- `--snapshot <archive-name-or-path>` restores a specific archive.
- `--force` allows restore into a non-empty target after creating a backup.

## Default Excludes

Snapshots skip common generated folders and local clutter by default:

```text
.DS_Store
.codex-workspace-sync
.next
.npm
.pnpm-store
.pytest_cache
.ruff_cache
.turbo
.venv
__pycache__
build
coverage
dist
node_modules
venv
```

Use `--include-heavy` only when the generated folders themselves matter.
