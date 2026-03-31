---
name: obsidian-repo-security-review
version: 1.0.0
dependencies: []
pipeline: {}
description: >
  Monthly repository security review skill for Fernando's GitHub account (ferparra).
  Performs comprehensive security audits across all 14 public and private repositories,
  checking for supply chain vulnerabilities, PII/doxxing exposure, and unauthorized
  contributors. Generates structured JSON reports and delivers Telegram summaries.
metadata:
  openclaw:
    os:
      - darwin
    requires:
      bins:
        - gh
        - git
        - python3
---

# Monthly Repo Security Review

Performs a comprehensive monthly security review of all GitHub repositories owned by
Fernando (ferparra). This skill runs automatically on the last day of each month and
delivers a security report directly to Fernando's Telegram.

## What This Skill Checks

| Phase | Check | Description |
|-------|-------|-------------|
| 1 | Repository Enumeration | Lists all public and private repos with metadata |
| 2 | Supply Chain Scan | Checks for CVE vulnerabilities, known malicious packages, and missing lockfiles |
| 3 | PII/Doxxing Scan | Scans for exposed secrets, personal information, and sensitive data |
| 4 | Contributor Audit | Verifies only allowed contributors have push access |
| 5 | Report Generation | Produces JSON report and Telegram summary |

## Repository List

This skill monitors these 14 repositories:

- My-Readwise
- Presentaci-n-Lean-Startup-Barcamp-2010
- data-engineering-zoomcamp
- gatsby-starter-netlify-cms
- graph-rag-mcp-server
- maybe
- my-chess-tutor
- my-skills
- next-blog-firestore
- nexus
- nexus-prisma-nextjs
- pds_docs
- pollenizer-startup-links
- study-hall-vite

## Workflow

### Phase 1: Enumerate All Repositories

```bash
gh api /users/ferparra/repos --paginate
```

Collects for each repo:
- `name` - repository name
- `private` - boolean, true if private
- `language` - primary language
- `default_branch` - main branch name
- `has_wiki` - boolean, true if wiki enabled

### Phase 2: Supply Chain Vulnerability Scan

For each repository, the skill checks:

**Dependency Graph Summary:**
```bash
gh api repos/{owner}/{repo}/dependency-graph/summary
```

**Python Repositories:**
- Check GitHub Security Advisories via `gh api repos/{owner}/{repo}/advisories`
- Scan for known vulnerable packages

**JavaScript/TypeScript Repositories:**
- Check dependency graph for known vulnerabilities
- Flag packages with supply chain attack history

**Go Repositories:**
- Check `go.mod verify` status
- Scan advisories

**Vulnerability Severity Levels:**
- CRITICAL - Immediate action required
- HIGH - Fix within 24-48 hours
- MEDIUM - Fix within 2 weeks
- LOW - Monitor and fix as needed

**Known Malicious Packages to Flag:**
- event-stream (2018 compromise)
- ua-parser-js (multiple supply chain attacks)
- flatmap-stream
- coa
- rc
- These are flagged regardless of version

**Lockfile Verification:**
- Python: `requirements.txt`, `Pipfile.lock`, `poetry.lock`
- JavaScript: `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`
- Go: `go.sum`
- Missing lockfiles in non-test/non-example code are flagged as WARN

### Phase 3: PII / Doxxing Scan

For each PUBLIC repository, the skill:

1. **Clones the repo** with `--depth 1` to save bandwidth
2. **Scans all files** for sensitive patterns:
   - API keys and tokens (AWS keys, GitHub tokens, Stripe keys, etc.)
   - Phone numbers (Australian format: 04xxxxxxxx, International: +1-xxx-xxx-xxxx)
   - Email addresses (personal emails not ending in @github.com)
   - Physical addresses (street addresses, zip codes)
   - AWS access keys (AKIA...)
   - GitHub tokens (gho_, ghp_, github_pat_)
   - Private keys (RSA, DSA, EC, PGP private keys)
   - Personal names combined with sensitive context

3. **Scans commit messages** for:
   - Personal names
   - Personal email addresses

4. **Scans GitHub Issues and PRs** for:
   - PII in descriptions
   - PII in comments

5. **Scans Wiki pages** if `has_wiki=true`

**Regex Patterns Used:**

```python
# GitHub Token
r'gho_[A-Za-z0-9]{36}'
r'ghp_[A-Za-z0-9]{36}'
r'github_pat_[A-Za-z0-9_]{22,}'

# AWS Access Key
r'AKIA[A-Z0-9]{16}'

# AWS Secret Key
r'[A-Za-z0-9/+=]{40}'  # When found near AWS context

# Generic API Key
r'[A-Za-z0-9]{32,64}'  # With high-entropy check

# Private Key Header
r'-----BEGIN (RSA |DSA |EC |PGP )?PRIVATE KEY-----'

# Phone - Australian
r'\b04[0-9]{7}\b'

# Phone - International US
r'\b\+?1?-?\(?[0-9]{3}\)?-[0-9]{3}-[0-9]{4}\b'

# Email (not github.com)
r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'  # Excludes @github.com

# Personal Name + Sensitive Context
# Flagged when personal name appears within 100 chars of: password, secret, key, etc.
```

### Phase 4: Contributor Audit

For each repository:

```bash
gh api repos/{owner}/{repo}/contributors --paginate
```

**Allowed Contributors:**
- `ferparra` (Fernando himself)
- `github-actions[bot]` (GitHub Actions)
- Known CI/agent identities matching patterns: `bot@`, `ci@`, `runner@`, `[bot]`

**Flagged as UNKNOWN:**
- Any contributor not in the allowed list
- Foreign collaborators on private repos
- Contributors with commit emails not matching known patterns

### Phase 5: Report Generation

**JSON Report Location:**
```
~/.hermes/repo_security_reviews/repo_security_review_{YYYY-MM-DD}.json
```

**JSON Report Structure:**
```json
{
  "review_date": "2026-03-31",
  "owner": "ferparra",
  "total_repos": 14,
  "public_repos": 11,
  "private_repos": 3,
  "repositories": [
    {
      "name": "example-repo",
      "private": false,
      "language": "Python",
      "default_branch": "main",
      "supply_chain": {
        "status": "CLEAN|WARN|VULN",
        "vulnerabilities": [],
        "warnings": []
      },
      "pii_scan": {
        "status": "CLEAN|RISK|REVIEW",
        "findings": []
      },
      "contributors": {
        "status": "CLEAN|UNKNOWN",
        "unknown_contributors": []
      }
    }
  ],
  "overall_status": "GREEN|YELLOW|RED"
}
```

**Telegram Summary Format:**
```
FERNANDO — MONTHLY REPO SECURITY REVIEW
{Month Year}

OVERVIEW
• 14 repos reviewed
• 11 public, 3 private
• Languages: Python (3), JavaScript/TypeScript (4), Other (7)

SUPPLY CHAIN
• [repo]: VULN — {N} HIGH/CRITICAL CVEs found
  → {cve IDs and descriptions}
• [repo]: WARN — dependency without lockfile
• All other repos: CLEAN

PII / DOXXING EXPOSURE
• [repo]: RISK — {description of PII found}
• [repo]: CLEAN — no PII detected
• [repo]: REVIEW — {flagged items needing manual review}

CONTRIBUTORS
• [repo]: UNKNOWN — {contributor} has push access (not you or known agent)
• All other repos: CLEAN

OVERALL STATUS: {GREEN|YELLOW|RED}
```

**Overall Status Determination:**
- GREEN: No issues found
- YELLOW: Warnings found (e.g., missing lockfiles, clean vulnerabilities)
- RED: High/Critical vulnerabilities, PII risks, or unknown contributors

## Cron Schedule

This skill runs automatically on the last day of each month at 9:00 AM AEDT.

- Schedule expression: `0 22 28-31 * *` (10:00 PM UTC on days 28-31)
- The script checks if it's the actual last day of month and exits cleanly if not

## Execution

**Manual Execution:**
```bash
python3 ~/my-skills/obsidian-plugin/skills/obsidian-repo-security-review/scripts/repo_security_review.py
```

**Automatic Execution:**
- Triggered by cron on the last day of each month
- Telegram delivery to ferparra83

## Output Files

| File | Location |
|------|----------|
| JSON Report | `~/.hermes/repo_security_reviews/repo_security_review_{YYYY-MM-DD}.json` |
| Telegram Summary | Delivered to Telegram:ferparra83 |

## Dependencies

- `gh` CLI for all GitHub API interactions
- `git` for repository cloning (--depth 1)
- Python 3 standard library only (json, re, subprocess, pathlib, datetime, tempfile)

No pip packages required - all code uses Python stdlib only.

## Known Limitations

1. **PII scan on private repos**: Not performed to avoid credential exposure during cloning
2. **Wiki scan**: Only performed on public repos
3. **Issues/PRs scan**: Limited to last 100 items per repo
4. **Rate limiting**: Respects GitHub API rate limits with delays between requests

## Exit Codes

- 0: Review completed successfully (regardless of findings)
- 1: Error occurred during review (e.g., API failure, clone failure)

## References

- `scripts/repo_security_review.py` - Main orchestrator script
- `scripts/scan_pii.py` - PII scanner module
- `scripts/scan_supply_chain.py` - Supply chain vulnerability scanner
