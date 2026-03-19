# my-skills

`my-skills` is the public, canonical repository for reusable AI skills across Codex, Claude, Cursor, and related agent workflows.

Repository URL: [https://github.com/ferparra/my-skills](https://github.com/ferparra/my-skills)

## Purpose

- Hold portable skills that should be reused across multiple AI workloads.
- Separate cross-workload skills from vault-local or environment-local experiments.
- Give both humans and agents a stable registry for discovering and maintaining the skill set.

## Local checkout convention

Clone this repository to `~/my-skills` on every local machine. Use the same path across installations so agent tooling can rely on one stable local location.

## Install for Codex

Install the repo's marketplace skills into Codex user-level skills with:

```bash
python3 scripts/install_codex_user_skills.py
```

The installer reads `.claude-plugin/marketplace.json`, walks each plugin's `.claude-plugin/plugin.json`, and installs every discovered `skills/<skill-name>/` directory into `$CODEX_HOME/skills` or `~/.codex/skills`.

- Default mode is `symlink`, so the checkout remains the canonical source of truth.
- Existing user-level skills with the same name are moved into `~/.codex/skill-backups/<timestamp>/` before replacement.
- Pass skill names to install only a subset, for example `python3 scripts/install_codex_user_skills.py qmd jira-sprint-sync`.
- Use `--mode copy` if you want detached copies instead of symlinks.
- Restart Codex after installing so it reloads the user-level skill catalog.

The installer does not modify the marketplace layout or the packaged `.skill` artifacts, so the same repo structure remains usable for Anthropic Claude plugin distribution.

## Release notes

Current marketplace release: `0.2.1`

Release history lives in [CHANGELOG.md](CHANGELOG.md).

## Repository contract

- One top-level directory per skill.
- Each skill uses `SKILL.md` as its primary contract.
- Supporting material lives beside the skill in optional `scripts/`, `references/`, and `assets/` directories.
- Keep the matching `<skill>.skill` artifact in sync when the source skill changes.
- Keep instructions portable and public-safe. Avoid machine-local absolute paths in reusable skill content.
- Treat every contribution as public by default. Review changed lines for unintended PII, secrets, email addresses, or machine-local filesystem paths before opening a PR.
- Use the pull request template and leave a PR comment summarizing validation plus the public-safety review.

## Validation

Use `uv` for repository validation and dependency management:

```bash
uv sync --extra dev
uv run pytest
uv run mypy
scripts/check_public_repo_guardrails.sh origin/master
```

The CI typecheck workflow also uses `uv` and `mypy`, so local validation should match the repository gate.

## Relationship to vault-local skills

Vault-local or experimental skills can live in a workspace-specific `.skills/` directory.

Promote a skill into `my-skills` once it should be reused across multiple AI workloads, machines, or agent surfaces.
