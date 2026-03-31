#!/usr/bin/env python3
"""
PII Scanner Module for Repo Security Review.

Scans cloned repositories for personally identifiable information (PII)
including API keys, tokens, phone numbers, email addresses, and other
sensitive personal information.
"""

import re
import os
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict

from repo_security_config import (
    PII_PATTERNS,
    SCANNABLE_EXTENSIONS,
    SCANNABLE_FILENAMES,
    SKIP_DIRECTORIES,
    MAX_FILE_SIZE_BYTES,
    REDACT_MAX_LENGTH,
    CONTEXT_LINES,
)


@dataclass
class PIIFinding:
    """Represents a PII finding in a repository."""
    type: str           # e.g., "github_token", "aws_key", "phone", "email"
    severity: str        # HIGH, MEDIUM, LOW
    file_path: str      # Path to file containing the finding
    line_number: int    # Line number where finding was detected
    matched_text: str   # The actual matched text (redacted for reporting)
    context: str        # Surrounding context (redacted)




def should_scan_file(file_path: Path) -> bool:
    """Determine if a file should be scanned for PII."""
    # Skip if in excluded directory
    path_parts = file_path.parts
    for part in path_parts:
        if part in SKIP_DIRECTORIES or part.startswith('.'):
            return False
    
    # Check extension
    if file_path.suffix.lower() in SCANNABLE_EXTENSIONS:
        return True
    
    # Check if filename suggests it's a config/secrets file
    if file_path.name in SCANNABLE_FILENAMES:
        return True
    
    return False


def redact_secret(text: str, max_length: int = REDACT_MAX_LENGTH) -> str:
    """Redact a secret for safe display."""
    if len(text) <= max_length:
        return "*" * len(text)
    return text[:max_length // 2] + "*" * (len(text) - max_length // 2)


def get_line_context(content: str, line_num: int, context_lines: int = CONTEXT_LINES) -> str:
    """Get surrounding context for a line number."""
    lines = content.split('\n')
    start = max(0, line_num - context_lines)
    end = min(len(lines), line_num + context_lines + 1)
    return '\n'.join(lines[start:end])


def scan_file(file_path: Path) -> list[PIIFinding]:
    """
    Scan a single file for PII.

    Args:
        file_path: Path to the file to scan

    Returns:
        List of PIIFinding objects
    """
    findings: list[PIIFinding] = []
    
    if not file_path.exists() or not file_path.is_file():
        return findings
    
    try:
        # Skip binary files
        try:
            content = file_path.read_text(encoding='utf-8', errors='strict')
        except (UnicodeDecodeError, PermissionError):
            return findings
        
        # Skip very large files
        if len(content) > MAX_FILE_SIZE_BYTES:
            return findings
        
    except Exception:
        return findings
    
    for finding_type, config in PII_PATTERNS.items():
        pattern = config.pattern
        severity = config.severity
        exclude_domains = config.exclude_domains
        
        try:
            regex = re.compile(pattern, re.IGNORECASE if pattern.startswith('(?i)') else 0)
        except re.error:
            continue
        
        for match in regex.finditer(content):
            matched_text = match.group(0)
            
            # For email, check if it's an excluded domain
            if exclude_domains and finding_type == "email_personal":
                email_domain = matched_text.split('@')[-1] if '@' in matched_text else ''
                if any(excluded in email_domain.lower() for excluded in exclude_domains):
                    continue
            
            # Calculate line number
            line_num = content[:match.start()].count('\n') + 1
            
            # Get context
            context = get_line_context(content, line_num)
            
            # Redact the matched text for display
            redacted_match = redact_secret(matched_text)
            context = context.replace(matched_text, redacted_match)
            
            finding = PIIFinding(
                type=finding_type,
                severity=severity,
                file_path=str(file_path),
                line_number=line_num,
                matched_text=redacted_match,
                context=context[:200],  # Limit context length
            )
            findings.append(finding)
    
    return findings


def scan_git_history(clone_path: Path) -> list[PIIFinding]:
    """
    Scan git commit messages for PII.

    Args:
        clone_path: Path to the cloned repository

    Returns:
        List of PIIFinding objects
    """
    findings: list[PIIFinding] = []
    
    try:
        # Get commit messages
        result = subprocess.run(
            ['git', 'log', '--all', '--format=%B', '-100'],
            cwd=clone_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            return findings
        
        commit_messages = result.stdout
        
        # Look for email patterns in commit messages
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        exclude_domains = ["github.com", "users.noreply.github.com"]
        
        for line_num, line in enumerate(commit_messages.split('\n'), 1):
            for match in re.finditer(email_pattern, line):
                email = match.group(0)
                domain = email.split('@')[-1].lower()
                if any(excl in domain for excl in exclude_domains):
                    continue
                
                finding = PIIFinding(
                    type="pii_in_commit",
                    severity="MEDIUM",
                    file_path=".git/COMMIT_EDITMSG",
                    line_number=line_num,
                    matched_text=email,
                    context=line[:200],
                )
                findings.append(finding)
                
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return findings


def scan_github_issues_and_prs(owner: str, repo: str) -> list[PIIFinding]:
    """
    Scan GitHub Issues and PRs for PII.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        List of PIIFinding objects
    """
    findings: list[PIIFinding] = []
    
    try:
        # Get issues
        issues_result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/issues', '--paginate', 
             '--limit', '100', '--jq', '.[] | {title, body, comments}'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if issues_result.returncode == 0:
            # Parse and scan for sensitive data
            import json
            try:
                items = json.loads(issues_result.stdout)
                for item in items[:50]:  # Limit to 50 items
                    title = item.get('title', '') or ''
                    body = item.get('body', '') or ''
                    
                    combined = f"{title} {body}"
                    
                    # Look for API keys/tokens in issues
                    token_pattern = r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['\"]?[A-Za-z0-9]{16,64}['\"]?"
                    for match in re.finditer(token_pattern, combined):
                        finding = PIIFinding(
                            type="secret_in_github_issue",
                            severity="HIGH",
                            file_path=f"GitHub Issue: {item.get('title', 'N/A')[:50]}",
                            line_number=0,
                            matched_text=redact_secret(match.group(0)),
                            context="Found in GitHub Issue/PR description",
                        )
                        findings.append(finding)
            except json.JSONDecodeError:
                pass
                
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return findings


def scan_repo_clone(clone_path: Path, owner: str, repo: str,
                    has_wiki: bool = False) -> list[PIIFinding]:
    """
    Scan a cloned repository for PII.

    Args:
        clone_path: Path to the cloned repository
        owner: Repository owner
        repo: Repository name
        has_wiki: Whether the repo has a wiki enabled

    Returns:
        List of PIIFinding objects
    """
    all_findings: list[PIIFinding] = []
    
    # Scan all files
    for root, dirs, files in os.walk(clone_path):
        # Modify dirs in place to skip directories
        dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES and not d.startswith('.')]
        
        for file_name in files:
            file_path = Path(root) / file_name
            
            if should_scan_file(file_path):
                file_findings = scan_file(file_path)
                all_findings.extend(file_findings)
    
    # Scan git history
    git_findings = scan_git_history(clone_path)
    all_findings.extend(git_findings)
    
    # Scan GitHub Issues and PRs
    issue_findings = scan_github_issues_and_prs(owner, repo)
    all_findings.extend(issue_findings)
    
    return all_findings


def format_findings_summary(findings: list[PIIFinding]) -> str:
    """Format a list of findings into a human-readable summary."""
    if not findings:
        return "No PII detected"

    by_type: dict[str, list[PIIFinding]] = {}
    for f in findings:
        if f.type not in by_type:
            by_type[f.type] = []
        by_type[f.type].append(f)

    lines: list[str] = []
    for pii_type, type_findings in sorted(by_type.items(), key=lambda x: -len(x[1])):
        severity = type_findings[0].severity
        count = len(type_findings)
        lines.append(f"  [{severity}] {pii_type}: {count} occurrence(s)")

    return '\n'.join(lines)


if __name__ == '__main__':
    # Test module
    import tempfile
    
    # Create a test file with sample secrets
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write('''
# Test file with PII
GITHUB_TOKEN = "gho_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
password = "super_secret_password_123"
email = "john.doe@personal.com"
phone = "0412345678"
''')
        test_file = f.name
    
    findings = scan_file(Path(test_file))
    print(f"Found {len(findings)} findings:")
    for f in findings:
        print(f"  {f.type}: {f.matched_text} in {f.file_path}:{f.line_number}")
    
    # Cleanup
    os.unlink(test_file)
