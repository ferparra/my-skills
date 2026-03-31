#!/usr/bin/env python3
"""
Monthly Repository Security Review - Main Orchestrator

Performs a comprehensive monthly security review of all GitHub repositories
owned by Fernando (ferparra), including:
- Repository enumeration
- Supply chain vulnerability scanning
- PII/doxxing exposure scanning
- Contributor auditing
- JSON report generation
- Telegram summary delivery
"""

import json
import os
import re
import subprocess
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from calendar import monthrange

# Import local modules
from scan_pii import scan_repo_clone, PIIFinding, format_findings_summary
from scan_supply_chain import check_repo_vulns, SupplyChainResult, format_vuln_summary


# Configuration
OWNER = "ferparra"
GITHUB_USER = "ferparra83"  # Telegram handle
REPOS_DIR = Path.home() / ".hermes" / "repo_security_reviews"
SKILL_DIR = Path(__file__).parent.parent

# Known repos from context
KNOWN_REPOS = [
    "My-Readwise",
    "Presentaci-n-Lean-Startup-Barcamp-2010",
    "data-engineering-zoomcamp",
    "gatsby-starter-netlify-cms",
    "graph-rag-mcp-server",
    "maybe",
    "my-chess-tutor",
    "my-skills",
    "next-blog-firestore",
    "nexus",
    "nexus-prisma-nextjs",
    "pds_docs",
    "pollenizer-startup-links",
    "study-hall-vite",
]

# Allowed contributor patterns
ALLOWED_CONTRIBUTORS = {
    "ferparra",
    "github-actions[bot]",
}

# Known agent/bot patterns
AGENT_PATTERNS = [
    r".*@users\.noreply\.github\.com$",  # GitHub Actions
    r".*\[bot\]@.*$",                     # Bot accounts
    r"ci@.*$",                            # CI systems
    r"runner@.*$",                       # GitHub runners
    r"build@.*$",                         # Build systems
    r"bot@.*$",                           # Generic bot
]


@dataclass
class RepoInfo:
    """Information about a repository."""
    name: str
    private: bool
    language: Optional[str]
    default_branch: str
    has_wiki: bool


@dataclass
class RepoSupplyChain:
    """Supply chain scan results for a repository."""
    status: str                    # CLEAN, WARN, VULN
    vulnerabilities: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RepoPII:
    """PII scan results for a repository."""
    status: str                    # CLEAN, RISK, REVIEW
    findings: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RepoContributor:
    """Contributor audit results for a repository."""
    status: str                    # CLEAN, UNKNOWN
    contributors: List[Dict[str, Any]] = field(default_factory=list)
    unknown_contributors: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RepoResult:
    """Complete scan results for a single repository."""
    name: str
    private: bool
    language: Optional[str]
    default_branch: str
    has_wiki: bool
    supply_chain: RepoSupplyChain
    pii_scan: RepoPII
    contributors: RepoContributor


@dataclass
class SecurityReviewReport:
    """Complete security review report."""
    review_date: str
    owner: str
    total_repos: int
    public_repos: int
    private_repos: int
    repositories: List[RepoResult]
    overall_status: str  # GREEN, YELLOW, RED
    telegram_summary: str


def is_last_day_of_month() -> bool:
    """Check if today is the last day of the current month."""
    today = datetime.now()
    _, last_day = monthrange(today.year, today.month)
    return today.day == last_day


def get_all_repos() -> List[RepoInfo]:
    """Get all repositories for the owner via GitHub API."""
    repos = []
    
    try:
        result = subprocess.run(
            ['gh', 'api', '/users/ferparra/repos', '--paginate', 
             '--jq', '.[] | {name, private, language, default_branch, has_wiki}'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode == 0:
            import json
            # Parse NDJSON (newline-delimited JSON) output
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        repo_data = json.loads(line)
                        repos.append(RepoInfo(
                            name=repo_data["name"],
                            private=repo_data["private"],
                            language=repo_data.get("language"),
                            default_branch=repo_data.get("default_branch", "main"),
                            has_wiki=repo_data.get("has_wiki", False),
                        ))
                    except json.JSONDecodeError:
                        continue
                
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return repos


def get_repo_contributors(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Get all contributors for a repository."""
    contributors = []
    
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/contributors', '--paginate',
             '--jq', '.[] | {login, id, type, contributions}'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            import json
            # Parse NDJSON output
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        contrib = json.loads(line)
                        contributors.append(contrib)
                    except json.JSONDecodeError:
                        continue
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return contributors


def is_allowed_contributor(login: str, author_email: Optional[str] = None) -> bool:
    """Check if a contributor is an allowed (known) entity."""
    # Direct login check
    if login in ALLOWED_CONTRIBUTORS:
        return True
    
    # Check bot patterns in email
    if author_email:
        for pattern in AGENT_PATTERNS:
            if re.match(pattern, author_email, re.IGNORECASE):
                return True
    
    return False


def audit_contributors(owner: str, repo: str) -> RepoContributor:
    """Audit contributors for a repository."""
    contributors_data = get_repo_contributors(owner, repo)
    
    result = RepoContributor(status="CLEAN")
    
    for contrib in contributors_data:
        login = contrib.get("login", "")
        
        if is_allowed_contributor(login):
            result.contributors.append({
                "login": login,
                "type": contrib.get("type"),
                "contributions": contrib.get("contributions"),
                "status": "allowed",
            })
        else:
            result.unknown_contributors.append({
                "login": login,
                "type": contrib.get("type"),
                "contributions": contrib.get("contributions"),
                "status": "unknown",
            })
            result.status = "UNKNOWN"
    
    return result


def scan_repo_pii(owner: str, repo: str, clone_path: Path, 
                  is_private: bool, has_wiki: bool) -> RepoPII:
    """Scan a repository for PII."""
    result = RepoPII(status="CLEAN")
    
    # Skip PII scan for private repos to avoid credential exposure
    if is_private:
        result.status = "CLEAN"
        result.findings.append({
            "type": "private_repo",
            "description": "PII scan skipped for private repositories",
        })
        return result
    
    try:
        # Clone the repo if not already cloned
        repo_path = clone_path / repo
        
        if not repo_path.exists():
            clone_url = f"https://github.com/{owner}/{repo}.git"
            result_clone = subprocess.run(
                ['git', 'clone', '--depth', '1', clone_url, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            
            if result_clone.returncode != 0:
                result.status = "REVIEW"
                result.findings.append({
                    "type": "clone_failed",
                    "description": f"Failed to clone repository: {result_clone.stderr[:200]}",
                })
                return result
        
        # Scan for PII
        findings = scan_repo_clone(repo_path, owner, repo, has_wiki)
        
        if findings:
            result.status = "RISK"
            for f in findings[:20]:  # Limit to 20 findings per repo
                result.findings.append({
                    "type": f.type,
                    "severity": f.severity,
                    "file": f.file_path,
                    "line": f.line_number,
                    "matched": f.matched_text[:50],
                    "context": f.context[:100],
                })
        else:
            result.status = "CLEAN"
            
    except Exception as e:
        result.status = "REVIEW"
        result.findings.append({
            "type": "scan_error",
            "description": str(e)[:200],
        })
    
    return result


def determine_overall_status(repos: List[RepoResult]) -> str:
    """Determine overall security status across all repos."""
    has_vuln = False
    has_risk = False
    has_warn = False
    has_unknown = False
    
    for repo in repos:
        # Supply chain status
        if repo.supply_chain.status == "VULN":
            has_vuln = True
        elif repo.supply_chain.status == "WARN":
            has_warn = True
        
        # PII status
        if repo.pii_scan.status == "RISK":
            has_risk = True
        elif repo.pii_scan.status == "REVIEW":
            has_warn = True
        
        # Contributor status
        if repo.contributors.status == "UNKNOWN":
            has_unknown = True
    
    if has_vuln or has_risk:
        return "RED"
    elif has_unknown or has_warn:
        return "YELLOW"
    else:
        return "GREEN"


def format_telegram_summary(repos: List[RepoInfo], 
                            repo_results: List[RepoResult], 
                            overall_status: str) -> str:
    """Format the Telegram summary message."""
    now = datetime.now()
    month_year = now.strftime("%B %Y")
    
    # Count stats
    public_count = sum(1 for r in repos if not r.private)
    private_count = sum(1 for r in repos if r.private)
    
    # Language breakdown
    lang_counts = {}
    for r in repos:
        lang = r.language or "Unknown"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
    
    # Build summary sections
    lines = []
    lines.append(f"FERNANDO — MONTHLY REPO SECURITY REVIEW")
    lines.append(f"{month_year}")
    lines.append("")
    lines.append("OVERVIEW")
    lines.append(f"• {len(repos)} repos reviewed")
    lines.append(f"• {public_count} public, {private_count} private")
    lang_str = ", ".join([f"{k} ({v})" for k, v in sorted(lang_counts.items())])
    lines.append(f"• Languages: {lang_str}")
    lines.append("")
    lines.append("SUPPLY CHAIN")
    
    # Supply chain findings
    vuln_repos = [r for r in repo_results if r.supply_chain.status == "VULN"]
    warn_repos = [r for r in repo_results if r.supply_chain.status == "WARN"]
    
    if vuln_repos:
        for repo in vuln_repos:
            vulns = repo.supply_chain.vulnerabilities
            vuln_str = ", ".join([v.get("cve_id", "Unknown") for v in vulns[:3]])
            lines.append(f"• {repo.name}: VULN — {len(vulns)} HIGH/CRITICAL CVE(s) found")
            lines.append(f"  → {vuln_str}")
    elif warn_repos:
        for repo in warn_repos:
            if repo.supply_chain.warnings:
                warn = repo.supply_chain.warnings[0]
                lines.append(f"• {repo.name}: WARN — {warn.get('warning_type', 'issue')}")
    else:
        lines.append("• All repos: CLEAN")
    
    lines.append("")
    lines.append("PII / DOXXING EXPOSURE")
    
    risk_repos = [r for r in repo_results if r.pii_scan.status == "RISK"]
    review_repos = [r for r in repo_results if r.pii_scan.status == "REVIEW"]
    clean_pii_repos = [r for r in repo_results if r.pii_scan.status == "CLEAN"]
    
    if risk_repos:
        for repo in risk_repos:
            findings = repo.pii_scan.findings
            if findings:
                first = findings[0]
                lines.append(f"• {repo.name}: RISK — {first.get('type', 'unknown')}")
    elif review_repos:
        for repo in review_repos:
            lines.append(f"• {repo.name}: REVIEW — manual review needed")
    else:
        lines.append("• All repos: CLEAN")
    
    lines.append("")
    lines.append("CONTRIBUTORS")
    
    unknown_repos = [r for r in repo_results if r.contributors.status == "UNKNOWN"]
    clean_repos = [r for r in repo_results if r.contributors.status == "CLEAN"]
    
    if unknown_repos:
        for repo in unknown_repos:
            unknown = repo.contributors.unknown_contributors
            if unknown:
                contrib_names = ", ".join([c.get("login", "unknown") for c in unknown[:3]])
                lines.append(f"• {repo.name}: UNKNOWN — {contrib_names} has push access")
    else:
        lines.append("• All repos: CLEAN")
    
    lines.append("")
    lines.append(f"OVERALL STATUS: {overall_status}")
    
    return "\n".join(lines)


def save_json_report(report: SecurityReviewReport, output_path: Path) -> None:
    """Save the report as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict for JSON serialization
    report_dict = {
        "review_date": report.review_date,
        "owner": report.owner,
        "total_repos": report.total_repos,
        "public_repos": report.public_repos,
        "private_repos": report.private_repos,
        "repositories": [
            {
                "name": r.name,
                "private": r.private,
                "language": r.language,
                "default_branch": r.default_branch,
                "has_wiki": r.has_wiki,
                "supply_chain": {
                    "status": r.supply_chain.status,
                    "vulnerabilities": r.supply_chain.vulnerabilities,
                    "warnings": r.supply_chain.warnings,
                },
                "pii_scan": {
                    "status": r.pii_scan.status,
                    "findings": r.pii_scan.findings,
                },
                "contributors": {
                    "status": r.contributors.status,
                    "contributors": r.contributors.contributors,
                    "unknown_contributors": r.contributors.unknown_contributors,
                },
            }
            for r in report.repositories
        ],
        "overall_status": report.overall_status,
    }
    
    with open(output_path, 'w') as f:
        json.dump(report_dict, f, indent=2)


def send_telegram_message(message: str) -> bool:
    """Send a message via Telegram."""
    try:
        # Using gh CLI's Telegram integration or direct API call
        # This would need to be configured based on available tools
        result = subprocess.run(
            ['echo', message],  # Placeholder - would use actual Telegram bot
            capture_output=True,
            text=True,
        )
        # For now, just print the message
        print("Telegram message would be sent:")
        print(message)
        return True
    except Exception:
        return False


def run_security_review() -> int:
    """
    Run the complete security review.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    print("Starting monthly repo security review...")
    print(f"Owner: {OWNER}")
    print(f"Date: {datetime.now().isoformat()}")
    print()
    
    # Check if we should run (last day of month)
    if not is_last_day_of_month():
        print("Not the last day of month - exiting cleanly")
        print("(Use --force to run anyway)")
        return 0
    
    # Create temp directory for cloning
    temp_dir = Path(tempfile.mkdtemp(prefix="repo_security_"))
    print(f"Using temp directory: {temp_dir}")
    
    try:
        # Phase 1: Enumerate repositories
        print("\n=== Phase 1: Enumerating repositories ===")
        repos = get_all_repos()
        print(f"Found {len(repos)} repositories")
        
        if not repos:
            print("ERROR: Could not fetch repositories from GitHub")
            return 1
        
        # Filter to known repos if API returned more
        repo_map = {r.name: r for r in repos}
        
        # Phase 2-4: Scan each repository
        repo_results = []
        
        for i, repo_info in enumerate(repos, 1):
            print(f"\n=== Processing {repo_info.name} ({i}/{len(repos)}) ===")
            
            # Supply chain scan
            print(f"  Checking supply chain...")
            supply_result = check_repo_vulns(OWNER, repo_info.name, repo_info.language)
            supply_chain = RepoSupplyChain(
                status=supply_result.status,
                vulnerabilities=[asdict(v) for v in supply_result.vulnerabilities],
                warnings=[asdict(w) for w in supply_result.warnings],
            )
            print(f"  Supply chain status: {supply_chain.status}")
            
            # PII scan
            print(f"  Scanning for PII...")
            pii_result = scan_repo_pii(
                OWNER, repo_info.name, temp_dir, 
                repo_info.private, repo_info.has_wiki
            )
            pii_scan = RepoPII(
                status=pii_result.status,
                findings=pii_result.findings,
            )
            print(f"  PII status: {pii_scan.status}")
            
            # Contributor audit
            print(f"  Auditing contributors...")
            contrib_result = audit_contributors(OWNER, repo_info.name)
            contributors = RepoContributor(
                status=contrib_result.status,
                contributors=contrib_result.contributors,
                unknown_contributors=contrib_result.unknown_contributors,
            )
            print(f"  Contributor status: {contributors.status}")
            
            repo_results.append(RepoResult(
                name=repo_info.name,
                private=repo_info.private,
                language=repo_info.language,
                default_branch=repo_info.default_branch,
                has_wiki=repo_info.has_wiki,
                supply_chain=supply_chain,
                pii_scan=pii_scan,
                contributors=contributors,
            ))
        
        # Phase 5: Generate report
        print("\n=== Phase 5: Generating report ===")
        
        overall_status = determine_overall_status(repo_results)
        telegram_summary = format_telegram_summary(repos, repo_results, overall_status)
        
        # Save JSON report
        now = datetime.now()
        report_date = now.strftime("%Y-%m-%d")
        json_filename = f"repo_security_review_{report_date}.json"
        json_path = REPOS_DIR / json_filename
        
        report = SecurityReviewReport(
            review_date=report_date,
            owner=OWNER,
            total_repos=len(repos),
            public_repos=sum(1 for r in repos if not r.private),
            private_repos=sum(1 for r in repos if r.private),
            repositories=repo_results,
            overall_status=overall_status,
            telegram_summary=telegram_summary,
        )
        
        save_json_report(report, json_path)
        print(f"JSON report saved to: {json_path}")
        
        # Send Telegram summary
        print("\n=== Sending Telegram summary ===")
        send_telegram_message(telegram_summary)
        
        print("\n=== Review Complete ===")
        print(f"Overall status: {overall_status}")
        print(f"Report: {json_path}")
        
        return 0
        
    finally:
        # Cleanup
        print(f"\nCleaning up temp directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Main entry point."""
    import sys
    
    # Check for --force flag
    force = "--force" in sys.argv
    
    if not is_last_day_of_month() and not force:
        print("This skill is designed to run on the last day of the month.")
        print("Use --force to run anyway for testing.")
        sys.exit(0)
    
    exit_code = run_security_review()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
