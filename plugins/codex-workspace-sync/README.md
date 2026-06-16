# Codex Workspace Sync

Codex Workspace Sync is a local Codex plugin for moving workspaces between
computers. The preferred workflow uses one GitHub remote repository with two or
more local clones. A secondary snapshot workflow is still available for folders
that should not be Git repositories.

Current version: `0.1.1`.

## Plugin Installation

This repository includes a local marketplace entry:

```text
.agents/plugins/marketplace.json
```

That entry points Codex at:

```text
plugins/codex-workspace-sync/
```

The plugin metadata lives in:

```text
plugins/codex-workspace-sync/.codex-plugin/plugin.json
```

## GitHub Workflow

The GitHub model is:

```text
Local A -> commit -> push -> GitHub remote
Local B <- pull/merge <- GitHub remote
Local B -> commit -> pull/merge -> push -> GitHub remote
Local A <- pull/merge <- GitHub remote
```

This gives you one shared source of truth while each computer keeps its own local
working copy.

### First Computer

Create an empty GitHub repository first, then connect the workspace:

```bash
python3 scripts/codex_workspace_sync.py git-setup \
  --workspace "/Users/baschie/Documents/My Workspace" \
  --url git@github.com:OWNER/REPO.git \
  --branch main

python3 scripts/codex_workspace_sync.py git-publish \
  --workspace "/Users/baschie/Documents/My Workspace" \
  --message "Initial workspace sync" \
  --set-upstream
```

### Second Computer

Clone the same remote into a local workspace:

```bash
python3 scripts/codex_workspace_sync.py git-clone \
  --url git@github.com:OWNER/REPO.git \
  --target "/Users/baschie/Documents/My Workspace" \
  --branch main
```

### Daily Use

Before starting work on a computer:

```bash
python3 scripts/codex_workspace_sync.py git-pull \
  --workspace "/Users/baschie/Documents/My Workspace"
```

After making changes:

```bash
python3 scripts/codex_workspace_sync.py git-publish \
  --workspace "/Users/baschie/Documents/My Workspace" \
  --message "Sync workspace changes"
```

Or do a full local-to-remote-to-local cycle:

```bash
python3 scripts/codex_workspace_sync.py git-sync \
  --workspace "/Users/baschie/Documents/My Workspace" \
  --message "Sync workspace changes"
```

`git-sync` commits local changes, pulls/merges remote changes, then pushes the
combined result. If Git reports a merge conflict, resolve it in the workspace and
run `git-sync` again.

### Status

```bash
python3 scripts/codex_workspace_sync.py git-status \
  --workspace "/Users/baschie/Documents/My Workspace"
```

The Git commands use your normal Git credentials, so SSH keys, GitHub CLI auth,
credential manager, private repos, and organization permissions all keep working
the way they already do.

## Snapshot Fallback

Snapshots are useful for folders that should not be Git repositories. They store
timestamped `.tar.gz` archives in a shared folder you already control, such as
iCloud Drive, Dropbox, Syncthing, a network share, or an external disk.

### Layout

```text
<sync-root>/
  codex-workspace-sync/
    workspaces/
      <workspace-name>/
        latest.json
        snapshots/
          <workspace-name>-20260615T180000Z.tar.gz
          <workspace-name>-20260615T180000Z.manifest.json
        restores/
          backup-before-restore-20260615T190000Z.tar.gz
```

### Script

The helper script lives at:

```text
plugins/codex-workspace-sync/scripts/codex_workspace_sync.py
```

Examples:

```bash
python3 scripts/codex_workspace_sync.py snapshot \
  --workspace "/Users/baschie/Documents/Codex Sync" \
  --sync-root "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Codex Workspace Sync"

python3 scripts/codex_workspace_sync.py list \
  --sync-root "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Codex Workspace Sync"

python3 scripts/codex_workspace_sync.py restore \
  --name codex-sync \
  --sync-root "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Codex Workspace Sync" \
  --target "/Users/baschie/Documents/Codex Sync Restored"
```

By default the script skips bulky generated folders such as `node_modules`,
`.venv`, `.next`, `dist`, and `build`. Use `--include-heavy` with `snapshot` if
you want a fuller archive.

## Current Status

- GitHub-backed setup, clone, pull, publish, sync, and status commands are
  implemented.
- Snapshot, list, status, and restore fallback commands are implemented.
- Top-level GitHub README, local marketplace metadata, and branch-explicit clone
  examples are in place.
