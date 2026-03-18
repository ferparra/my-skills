#!/usr/bin/env bash

set -euo pipefail

BASE_REF="${1:-origin/master}"

if ! git rev-parse --verify "${BASE_REF}" >/dev/null 2>&1; then
  echo "Base ref not found: ${BASE_REF}" >&2
  exit 2
fi

diff_lines="$(git diff --no-color --unified=0 "${BASE_REF}...HEAD" -- .)"
added_lines="$(printf '%s\n' "${diff_lines}" | grep '^+' | grep -v '^+++' || true)"

if [ -z "${added_lines}" ]; then
  echo "No added lines to scan against ${BASE_REF}."
  exit 0
fi

patterns=(
  '/Users/'
  '/home/'
  '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
  'BEGIN [A-Z ]*PRIVATE KEY'
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36,}'
  'github_pat_[A-Za-z0-9_]{20,}'
  'sk-[A-Za-z0-9]{20,}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
)

failed=0

for pattern in "${patterns[@]}"; do
  if printf '%s\n' "${added_lines}" | grep -En "${pattern}" >/dev/null; then
    echo "Potential public-repo safety violation for pattern: ${pattern}" >&2
    printf '%s\n' "${added_lines}" | grep -En "${pattern}" >&2 || true
    failed=1
  fi
done

if [ "${failed}" -ne 0 ]; then
  exit 1
fi

echo "Public-repo guardrail scan passed against ${BASE_REF}."
