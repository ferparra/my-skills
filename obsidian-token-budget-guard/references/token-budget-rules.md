# Token Budget Rules

## Hard Gates

- Candidate files must be <= 5.
- Total candidate chars must be <= 22000.
- Retrieval snippets must be <= 12.

## Decision Rule

- Any gate violation returns non-zero and blocks broad reads.
- Resolve violations before opening additional notes.

## Rationale

- Preserve context capacity for high-signal instructions and user intent.
- Prevent lost-in-middle degradation caused by oversized prompt payloads.
