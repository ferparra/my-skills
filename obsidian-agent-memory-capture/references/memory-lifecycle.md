# Memory Lifecycle

## States

- `#status/processing`: note is being integrated
- `#status/processed`: note is integrated and linked
- `#status/review-needed`: note needs follow-up or correction

## Transition Rules

1. Capture raw insight quickly.
2. Add required links and fields.
3. Validate against zettel checks.
4. Promote to durable state when checks pass.
