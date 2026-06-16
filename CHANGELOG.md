# Changelog

All notable changes to Codex Workspace Sync will be documented in this file.

This project follows semantic versioning for release tags.

## [Unreleased]

## [0.1.1] - 2026-06-16

### Changed

- Updated README documentation to reflect the current GitHub sync workflow.
- Documented the workspace-local marketplace entry and plugin metadata paths.
- Made `git-clone --branch main` explicit in quick-start examples to avoid
  fresh-remote branch ambiguity.

### Verified

- Published the local workspace back to GitHub through the sync workflow.
- Merged the existing GitHub baseline with the local plugin updates.

## [0.1.0] - 2026-06-15

### Added

- Created the Codex Workspace Sync plugin scaffold.
- Added a GitHub-backed workspace sync workflow:
  - `git-setup` to initialize or connect a workspace to a remote.
  - `git-clone` to create a local workspace from a remote.
  - `git-status` to inspect branch, remote, and local state.
  - `git-pull` to pull and merge remote changes.
  - `git-publish` to commit and push local changes.
  - `git-sync` to commit local changes, pull/merge remote changes, then push.
- Added a snapshot fallback workflow for non-Git folders:
  - `snapshot`
  - `list`
  - `status`
  - `restore`
- Added plugin skill instructions for Codex.
- Added a workspace-local marketplace entry.

### Verified

- Simulated a two-local-repo workflow using a local bare Git remote.
- Verified snapshot, status, restore, and file comparison behavior.
- Confirmed plugin metadata and marketplace entry shape with lightweight checks.
