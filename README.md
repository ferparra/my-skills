# my-skills

`my-skills` is the public, canonical repository for reusable AI skills across Codex, Claude, Cursor, and related agent workflows.

Repository URL: [https://github.com/ferparra/my-skills](https://github.com/ferparra/my-skills)

## Purpose

- Hold portable skills that should be reused across multiple AI workloads.
- Separate cross-workload skills from vault-local or environment-local experiments.
- Give both humans and agents a stable registry for discovering and maintaining the skill set.

## Local checkout convention

Clone this repository to `~/my-skills` on every local machine. Use the same path across installations so agent tooling can rely on one stable local location.

## Install with `npx skills` (any agent)

Install all skills into any supported AI coding agent (Claude Code, Cursor, Codex, Cline, OpenCode, and 40+ others) using the [Vercel skills CLI](https://github.com/vercel-labs/skills):

```bash
# Install all skills globally
npx skills add ferparra/my-skills -g

# Install a single skill
npx skills add https://github.com/ferparra/my-skills/tree/main/skills/qmd -g

# List installed skills
npx skills list
```

Skills are discovered from the top-level `skills/` directory, which contains relative symlinks to each plugin's skill directories. The `skills/` layout makes this repo compatible with the Vercel skills standard (`skills/<name>/SKILL.md`).

## Install for Claude Code (marketplace)

Both plugins ship as an Anthropic Claude Code marketplace. Install from within Claude Code:

```
/plugin install obsidian-plugin@my-skills-marketplace
/plugin install productivity-plugin@my-skills-marketplace
```

The marketplace index lives at `.claude-plugin/marketplace.json`. Skills are grouped into two plugins:

- **obsidian-plugin** — 13 skills for Obsidian vault management
- **productivity-plugin** — 2 skills for Jira and QMD search

## Install for OpenClaw

Point `extraDirs` at each plugin's `skills/` directory in `~/.openclaw/openclaw.json`. OpenClaw expects each entry to be a directory whose immediate subdirectories are skills — do not point at the repo root, as its symlink security check will block symlinks that resolve outside that root:

```json
{
  "skills": {
    "load": {
      "extraDirs": [
        "~/my-skills/obsidian-plugin/skills",
        "~/my-skills/productivity-plugin/skills"
      ]
    }
  }
}
```

Or via the CLI:

```bash
openclaw config set skills.load.extraDirs '[ "~/my-skills/obsidian-plugin/skills", "~/my-skills/productivity-plugin/skills" ]'
```

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

Current marketplace release: `0.3.0`

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
