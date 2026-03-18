# AGENTS.md

## Mission
Maintain this repository as the canonical public registry of reusable AI skills across agent workflows.

## Scope
This repository holds cross-workload skills, not workspace-specific notes or private operating context.

## Workflow
1. Inspect the target skill directory and its matching `.skill` artifact before editing.
2. Make the smallest change that improves portability, clarity, or reuse.
3. Preserve the standard skill layout: `SKILL.md` plus optional `scripts/`, `references/`, and `assets/`.
4. If a source skill changes, keep the matching `<skill>.skill` artifact aligned.
5. For public-repo safety, run `scripts/check_public_repo_guardrails.sh <base-ref>` against the target diff before opening or updating a PR.
6. Open or update PRs with `gh pr create` or `gh pr edit` using a substantive title and body from the repo template.
7. Add a PR comment with `gh pr comment` summarizing validation and the public-safety review.
8. Commit and push changes through git.

## Guardrails
- MUST keep reusable skill content portable.
- MUST avoid machine-local absolute paths in skill instructions unless the task is explicitly about a fixed local convention such as `~/my-skills`.
- MUST keep the repository safe to publish publicly.
- MUST review changed lines for unintended PII, secrets, email addresses, local filesystem paths, or private note references before requesting review.
- MUST preserve existing files unless a cleanup is explicitly requested.
- MUST NOT perform destructive renames or deletions without approval.

## Done when
- The edited skill or document is internally consistent.
- Any matching `.skill` artifact is aligned with the source change.
- The PR body is complete and a follow-up PR comment records validation plus the public-safety check.
- Git history is clean except for the intended change.
