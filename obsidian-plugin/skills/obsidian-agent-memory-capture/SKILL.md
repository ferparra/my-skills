---
name: obsidian-agent-memory-capture
version: 1.0.0
description: Audit and capture reusable agent memory patterns from this personal Obsidian vault as zettels. Use when daily or weekly execution surfaces insight, friction, or patterns that must satisfy zettel tracking fields, lifecycle tags, and concept/context linking requirements.
metadata:
  openclaw:
    os: [macos]
    requires:
      bins: [obsidian, qmd, uvx]
---

# Obsidian Agent Memory Capture

Use this skill to convert execution residue into durable memory notes.

## Workflow

1. Target a candidate note in `00 Inbox`, `10 Notes`, or `20 Resources`.
2. Run `uvx --from python python scripts/memory_capture_audit.py --path "<note-path>"`.
3. Resolve missing lifecycle fields and link requirements.
4. Keep one core idea per note.
5. Re-run audit and stop only when compliance passes.

## Output Contract

`uvx --from python python scripts/memory_capture_audit.py ...` returns JSON with:
- lifecycle compliance
- required field checks
- concept/context link checks
- remediation actions

## Memory Capture Rules

- Maintain `connection_strength` semantics when present.
- Maintain `potential_links` as YAML list where expected.
- Preserve temporal and PIT fields unless explicitly requested otherwise.

## Dependency Policy

Fail fast when `obsidian`, `qmd`, or `uvx` is missing.
Do not promote notes to durable memory state when dependency checks fail.

## References

- Use `references/zettel-standard.md` for required memory fields.
- Use `references/memory-lifecycle.md` for state transitions.
