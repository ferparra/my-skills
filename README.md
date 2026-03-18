# my-skills

`my-skills` is the public, canonical repository for reusable AI skills across Codex, Claude, Cursor, and related agent workflows.

Repository URL: [https://github.com/ferparra/my-skills](https://github.com/ferparra/my-skills)

## Purpose

- Hold portable skills that should be reused across multiple AI workloads.
- Separate cross-workload skills from vault-local or environment-local experiments.
- Give both humans and agents a stable registry for discovering and maintaining the skill set.

## Local checkout convention

Clone this repository to `~/my-skills` on every local machine. Use the same path across installations so agent tooling can rely on one stable local location.

## Repository contract

- One top-level directory per skill.
- Each skill uses `SKILL.md` as its primary contract.
- Supporting material lives beside the skill in optional `scripts/`, `references/`, and `assets/` directories.
- Keep the matching `<skill>.skill` artifact in sync when the source skill changes.
- Keep instructions portable and public-safe. Avoid machine-local absolute paths in reusable skill content.
- Treat every contribution as public by default. Review changed lines for unintended PII, secrets, email addresses, or machine-local filesystem paths before opening a PR.
- Use the pull request template and leave a PR comment summarizing validation plus the public-safety review.

## Relationship to vault-local skills

Vault-local or experimental skills can live in a workspace-specific `.skills/` directory.

Promote a skill into `my-skills` once it should be reused across multiple AI workloads, machines, or agent surfaces.
