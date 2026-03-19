# Changelog

All notable marketplace and repository-tooling changes are recorded here.

## 0.2.1 - 2026-03-19

### Changed

- Bumped the Claude marketplace and both plugin manifests to `0.2.1` so upstream agents can pick up the QMD and Obsidian vault-search guidance update.
- Updated the `qmd` and `obsidian-cli` skills to require a search-then-read workflow instead of stopping at result lists.
- Added an explicit fallback path for QMD note lookup when local model initialization fails, using `qmd search` and `obsidian search` plus direct note reads.

### Documentation

- Corrected the QMD MCP query reference to use the live `searches` array shape and documented the required note-read follow-up sequence.

## 0.2.0 - 2026-03-19

### Added

- Added `uv`-managed Python project metadata and lockfile for repository tooling.
- Added `scripts/install_codex_user_skills.py` to install Codex user-level skills directly from the Claude marketplace layout without modifying packaged `.skill` artifacts.
- Added a GitHub Actions typecheck workflow that installs dependencies with `uv` and runs `mypy`.

### Changed

- Bumped the Claude marketplace, plugin manifests, and project metadata to `0.2.0`.
- Switched strict Python type checking to `mypy` and refreshed the affected repository configuration.
- Updated the touched skill scripts, tests, and packaged `.skill` artifacts to satisfy the stricter type-checking workflow across the Obsidian and productivity plugin surfaces.

### Documentation

- Documented the current release and the repository validation workflow in [README.md](README.md).
- Captured the public-repo validation flow around `scripts/check_public_repo_guardrails.sh` as part of the release notes for this version.
