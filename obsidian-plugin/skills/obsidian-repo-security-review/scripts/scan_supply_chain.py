#!/usr/bin/env python3
"""
Supply Chain Vulnerability Scanner for Repo Security Review.

Checks repositories for supply chain vulnerabilities including:
- Known CVE vulnerabilities (HIGH/CRITICAL severity)
- Dependencies on known malicious packages
- Missing lockfiles in production code
"""

import json
import subprocess
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class VulnFinding:
    """Represents a vulnerability finding."""
    cve_id: Optional[str]      # CVE identifier if available
    severity: str              # CRITICAL, HIGH, MEDIUM, LOW
    package_name: str          # Name of vulnerable package
    package_ecosystem: str     # npm, pip, go, etc.
    affected_versions: str     # Version range affected
    fixed_version: Optional[str]  # Version with fix if available
    description: str           # Brief description
    html_url: Optional[str]    # Link to advisory


@dataclass 
class SupplyChainWarning:
    """Represents a supply chain warning."""
    warning_type: str           # missing_lockfile, malicious_package, etc.
    severity: str               # HIGH, MEDIUM, LOW
    details: str               # Detailed description


# Known malicious packages with their attack details
MALICIOUS_PACKAGES = {
    "event-stream": {
        "severity": "CRITICAL",
        "description": "2018 compromise - cryptocurrency wallet theft via flatmap-stream dependency",
        "attack_type": "Cryptocurrency theft",
    },
    "flatmap-stream": {
        "severity": "CRITICAL", 
        "description": "2018 compromise - backdoor installed by event-stream maintainer",
        "attack_type": "Backdoor",
    },
    "ua-parser-js": {
        "severity": "CRITICAL",
        "description": "Multiple supply chain attacks (2021-2022) - credential stealing backdoors",
        "attack_type": "Credential stealing",
    },
    "coa": {
        "severity": "CRITICAL",
        "description": "2022 supply chain attack - command injection payload",
        "attack_type": "Command injection",
    },
    "rc": {
        "severity": "CRITICAL",
        "description": "2022 supply chain attack - command injection payload (coa dependency)",
        "attack_type": "Command injection",
    },
    "j舅": {
        "severity": "CRITICAL",
        "description": "2022 malicious package mimicking popular Chinese package",
        "attack_type": "Typosquatting",
    },
}

# Lockfile requirements by ecosystem
LOCKFILES = {
    "npm": ["package-lock.json", "npm-shrinkwrap.json"],
    "yarn": ["yarn.lock"],
    "pnpm": ["pnpm-lock.yaml"],
    "pip": ["requirements.txt", "Pipfile.lock", "poetry.lock", "pip-tools.lock"],
    "go": ["go.sum"],
    "gem": ["Gemfile.lock"],
    "cargo": ["Cargo.lock"],
    "nuget": ["packages.lock.json"],
}


@dataclass
class SupplyChainResult:
    """Result of supply chain scan for a repository."""
    repo_name: str
    status: str                 # CLEAN, WARN, VULN
    vulnerabilities: List[VulnFinding] = field(default_factory=list)
    warnings: List[SupplyChainWarning] = field(default_factory=list)
    dependency_graph_available: bool = False
    advisories_available: bool = False


def check_gh_api_available(owner: str, repo: str) -> bool:
    """Check if GitHub API is accessible."""
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}', '--jq', '.id'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_dependency_graph_summary(owner: str, repo: str) -> Optional[Dict[str, Any]]:
    """Get dependency graph summary via GitHub API."""
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/dependency-graph/summary'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
        
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def get_security_advisories(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Get security advisories for a repository via GitHub API."""
    advisories = []
    
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/advisories', '--paginate'],
            capture_output=True,
            text=True,
            timeout=60,
        )
        
        if result.returncode == 0:
            # Parse NDJSON output from --paginate
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        advisory = json.loads(line)
                        advisories.append(advisory)
                    except json.JSONDecodeError:
                        continue
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return advisories


def check_vulnerability_severity(severity: str) -> bool:
    """Check if severity is HIGH or CRITICAL."""
    return severity.upper() in ("HIGH", "CRITICAL")


def parse_advisory_for_high_cves(advisory: Dict[str, Any]) -> Optional[VulnFinding]:
    """Parse a GitHub security advisory into a VulnFinding if it's HIGH/CRITICAL."""
    severity = advisory.get("severity", "").upper()
    
    if not check_vulnerability_severity(severity):
        return None
    
    # Get fixed version if available
    fixed_version = None
    vulnerabilities = advisory.get("vulnerabilities", [])
    if vulnerabilities:
        first_vuln = vulnerabilities[0]
        fixed_version = first_vuln.get("fixed_in")
    
    return VulnFinding(
        cve_id=advisory.get("ghsa_id") or advisory.get("cve_id"),
        severity=severity,
        package_name=advisory.get("package", {}).get("name", "unknown"),
        package_ecosystem=advisory.get("package", {}).get("ecosystem", "unknown"),
        affected_versions=advisory.get("vulnerable_version_range", "unknown"),
        fixed_version=fixed_version,
        description=advisory.get("description", "")[:200],
        html_url=advisory.get("html_url"),
    )


def check_for_malicious_packages(dependencies: List[Dict[str, Any]]) -> List[SupplyChainWarning]:
    """Check if any dependencies match known malicious packages."""
    warnings = []
    
    for dep in dependencies:
        dep_name = dep.get("package_name", "").lower()
        
        if dep_name in MALICIOUS_PACKAGES:
            info = MALICIOUS_PACKAGES[dep_name]
            warnings.append(SupplyChainWarning(
                warning_type="malicious_package",
                severity=info["severity"],
                details=f"Package '{dep_name}' is a known malicious package. "
                        f"Attack type: {info['attack_type']}. {info['description']}",
            ))
    
    return warnings


def detect_missing_lockfiles(owner: str, repo: str, language: Optional[str]) -> List[SupplyChainWarning]:
    """Detect if lockfiles are missing for the project's package manager."""
    warnings = []
    
    if not language:
        return warnings
    
    lang_lower = language.lower()
    
    # Map languages to their package managers
    lang_to_ecosystem = {
        "python": "pip",
        "javascript": "npm",
        "typescript": "npm",
        "go": "go",
        "ruby": "gem",
        "rust": "cargo",
        "c#": "nuget",
        "java": "maven",
        "kotlin": "maven",
        "swift": "swift",
        "php": "composer",
    }
    
    ecosystem = lang_to_ecosystem.get(lang_lower)
    
    if not ecosystem:
        return warnings
    
    expected_lockfiles = LOCKFILES.get(ecosystem, [])
    
    # Check if any lockfile exists
    has_lockfile = False
    for lockfile in expected_lockfiles:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/contents/{lockfile}'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            has_lockfile = True
            break
    
    if not has_lockfile and expected_lockfiles:
        # It's a warning only if there are actual dependencies
        # Check dependency graph to see if there are dependencies
        dep_summary = get_dependency_graph_summary(owner, repo)
        if dep_summary:
            dep_count = dep_summary.get("dependency_count", 0)
            if dep_count > 0:
                warnings.append(SupplyChainWarning(
                    warning_type="missing_lockfile",
                    severity="MEDIUM",
                    details=f"No lockfile found for {ecosystem}. "
                            f"Expected one of: {', '.join(expected_lockfiles)}. "
                            f"Found {dep_count} dependencies without version pinning.",
                ))
    
    return warnings


def check_repo_vulns(owner: str, repo: str, language: Optional[str] = None) -> SupplyChainResult:
    """
    Check a repository for supply chain vulnerabilities.
    
    Args:
        owner: Repository owner
        repo: Repository name
        language: Primary language of the repository
        
    Returns:
        SupplyChainResult with vulnerability and warning lists
    """
    result = SupplyChainResult(repo_name=repo, status="CLEAN")
    
    # Get dependency graph summary
    dep_summary = get_dependency_graph_summary(owner, repo)
    if dep_summary:
        result.dependency_graph_available = True
    
    # Get security advisories
    advisories = get_security_advisories(owner, repo)
    if advisories:
        result.advisories_available = True
    
    # Parse HIGH/CRITICAL vulnerabilities
    high_cves = []
    for advisory in advisories:
        vuln = parse_advisory_for_high_cves(advisory)
        if vuln:
            high_cves.append(vuln)
    
    result.vulnerabilities = high_cves
    
    # Check for malicious packages
    dependencies = dep_summary.get("dependencies", []) if dep_summary else []
    malicious_warnings = check_for_malicious_packages(dependencies)
    result.warnings.extend(malicious_warnings)
    
    # Check for missing lockfiles
    lockfile_warnings = detect_missing_lockfiles(owner, repo, language)
    result.warnings.extend(lockfile_warnings)
    
    # Determine overall status
    if high_cves:
        result.status = "VULN"
    elif malicious_warnings or lockfile_warnings:
        result.status = "WARN"
    else:
        result.status = "CLEAN"
    
    return result


def format_vuln_summary(result: SupplyChainResult) -> str:
    """Format vulnerability results into a readable summary."""
    lines = []
    
    if result.status == "CLEAN":
        return "CLEAN - no vulnerabilities detected"
    
    if result.vulnerabilities:
        lines.append(f"VULN - {len(result.vulnerabilities)} HIGH/CRITICAL CVE(s):")
        for v in result.vulnerabilities[:5]:  # Limit to first 5
            cve = v.cve_id or "No CVE"
            lines.append(f"  [{v.severity}] {cve} - {v.package_name}")
    
    if result.warnings:
        for w in result.warnings:
            lines.append(f"WARN - {w.warning_type}: {w.details[:100]}")
    
    return '\n'.join(lines) if lines else "CLEAN"


if __name__ == '__main__':
    # Test with a known vulnerable repo pattern
    import sys
    
    if len(sys.argv) > 2:
        owner, repo = sys.argv[1], sys.argv[2]
        language = sys.argv[3] if len(sys.argv) > 3 else None
        
        result = check_repo_vulns(owner, repo, language)
        print(f"Repository: {owner}/{repo}")
        print(f"Status: {result.status}")
        print(f"Dependency graph available: {result.dependency_graph_available}")
        print(f"Advisories available: {result.advisories_available}")
        print(f"Vulnerabilities found: {len(result.vulnerabilities)}")
        print(f"Warnings found: {len(result.warnings)}")
        
        for v in result.vulnerabilities[:3]:
            print(f"  - {v.cve_id}: {v.package_name} ({v.severity})")
    else:
        print("Usage: python scan_supply_chain.py <owner> <repo> [language]")
