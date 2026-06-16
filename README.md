# Codex Workspace Sync

Codex Workspace Sync is a Codex plugin for syncing Codex workspaces between
computers through GitHub.

Current version: `0.1.1`.

The main workflow uses one GitHub remote repository with two or more local
working copies:

```text
Local A -> commit -> push -> GitHub
Local B <- pull/merge <- GitHub
Local B -> commit -> pull/merge -> push -> GitHub
Local A <- pull/merge <- GitHub
```

## Plugin

The plugin lives here:

```text
plugins/codex-workspace-sync/
```

Detailed setup and usage docs are in:

```text
plugins/codex-workspace-sync/README.md
```

This repository also includes a workspace-local marketplace entry at
`.agents/plugins/marketplace.json`, so Codex can discover the plugin from this
checkout.

## Quick Start

First computer:

```bash
python3 plugins/codex-workspace-sync/scripts/codex_workspace_sync.py git-setup \
  --workspace "/path/to/project" \
  --url git@github.com:OWNER/REPO.git \
  --branch main

python3 plugins/codex-workspace-sync/scripts/codex_workspace_sync.py git-publish \
  --workspace "/path/to/project" \
  --message "Initial sync" \
  --set-upstream
```

Second computer:

```bash
python3 plugins/codex-workspace-sync/scripts/codex_workspace_sync.py git-clone \
  --url git@github.com:OWNER/REPO.git \
  --target "/path/to/project" \
  --branch main
```

Daily use:

```bash
python3 plugins/codex-workspace-sync/scripts/codex_workspace_sync.py git-pull \
  --workspace "/path/to/project"

python3 plugins/codex-workspace-sync/scripts/codex_workspace_sync.py git-sync \
  --workspace "/path/to/project" \
  --message "Sync workspace changes"
```

The plugin also includes a snapshot fallback for non-Git folders.

## Current Status

- GitHub-backed setup, clone, pull, publish, sync, and status commands are
  implemented.
- Snapshot, list, status, and restore fallback commands are implemented for
  folders that should not be Git repositories.
- Top-level GitHub README, local marketplace metadata, and branch-explicit clone
  examples are in place.
