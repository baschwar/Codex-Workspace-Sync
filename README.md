# Codex Workspace Sync

Codex Workspace Sync is a Codex plugin for syncing Codex workspaces between
computers through GitHub.

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
  --target "/path/to/project"
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
