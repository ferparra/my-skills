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

from repo_security_config import MALICIOUS_PACKAGES, LOCKFILE_CONFIGS


@dataclass
class VulnFinding:
    """Represents a vulnerability finding."""
    cve_id: str | None      # CVE identifier if available
    severity: str              # CRITICAL, HIGH, MEDIUM, LOW
    package_name: str          # Name of vulnerable package
    package_ecosystem: str     # npm, pip, go, etc.
    affected_versions: str     # Version range affected
    fixed_version: str | None  # Version with fix if available
    description: str           # Brief description
    html_url: str | None    # Link to advisory


@dataclass
class SupplyChainWarning:
    """Represents a supply chain warning."""
    warning_type: str           # missing_lockfile, malicious_package, etc.
    severity: str               # HIGH, MEDIUM, LOW
    details: str               # Detailed description


@dataclass
class SupplyChainResult:
    """Result of supply chain scan for a repository."""
    repo_name: str
    status: str                 # CLEAN, WARN, VULN
    vulnerabilities: list[VulnFinding] = field(default_factory=list)
    warnings: list[SupplyChainWarning] = field(default_factory=list)
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


def get_dependency_graph_summary(owner: str, repo: str) -> dict[str, object] | None:
    """Get dependency graph summary via GitHub API."""
    try:
        result = subprocess.run(
            ['gh', 'api', f'repos/{owner}/{repo}/dependency-graph/summary'],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            parsed: dict[str, object] = json.loads(result.stdout)
            return parsed
        return None

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def get_security_advisories(owner: str, repo: str) -> list[dict[str, object]]:
    """Get security advisories for a repository via GitHub API."""
    advisories: list[dict[str, object]] = []

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
                        advisory: dict[str, object] = json.loads(line)
                        advisories.append(advisory)
                    except json.JSONDecodeError:
                        continue
            
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    return advisories


def check_vulnerability_severity(severity: str) -> bool:
    """Check if severity is HIGH or CRITICAL."""
    return severity.upper() in ("HIGH", "CRITICAL")


def parse_advisory_for_high_cves(advisory: dict[str, object]) -> VulnFinding | None:
    """Parse a GitHub security advisory into a VulnFinding if it's HIGH/CRITICAL."""
    severity = str(advisory.get("severity", "")).upper()

    if not check_vulnerability_severity(severity):
        return None

    # Get fixed version if available
    fixed_version: str | None = None
    vulnerabilities = advisory.get("vulnerabilities", [])
    if vulnerabilities and isinstance(vulnerabilities, list):
        first_vuln = vulnerabilities[0]
        if isinstance(first_vuln, dict):
            fixed_version = first_vuln.get("fixed_in")

    package_dict = advisory.get("package", {})
    package_name = "unknown"
    package_ecosystem = "unknown"
    if isinstance(package_dict, dict):
        package_name = str(package_dict.get("name", "unknown"))
        package_ecosystem = str(package_dict.get("ecosystem", "unknown"))

    return VulnFinding(
        cve_id=str(advisory.get("ghsa_id") or advisory.get("cve_id") or ""),
        severity=severity,
        package_name=package_name,
        package_ecosystem=package_ecosystem,
        affected_versions=str(advisory.get("vulnerable_version_range", "unknown")),
        fixed_version=str(fixed_version) if fixed_version else None,
        description=str(advisory.get("description", ""))[:200],
        html_url=str(advisory.get("html_url")) if advisory.get("html_url") else None,
    )


def check_for_malicious_packages(dependencies: list[dict[str, object]]) -> list[SupplyChainWarning]:
    """Check if any dependencies match known malicious packages."""
    warnings: list[SupplyChainWarning] = []

    for dep in dependencies:
        dep_name = str(dep.get("package_name", "")).lower()

        if dep_name in MALICIOUS_PACKAGES:
            info = MALICIOUS_PACKAGES[dep_name]
            warnings.append(SupplyChainWarning(
                warning_type="malicious_package",
                severity=info.severity,
                details=f"Package '{dep_name}' is a known malicious package. "
                        f"Attack type: {info.attack_type}. {info.description}",
            ))

    return warnings


def detect_missing_lockfiles(owner: str, repo: str, language: str | None) -> list[SupplyChainWarning]:
    """Detect if lockfiles are missing for the project's package manager."""
    warnings: list[SupplyChainWarning] = []

    if not language:
        return warnings

    lang_lower = language.lower()

    # Map languages to their package managers
    lang_to_ecosystem: dict[str, str] = {
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

    # Find matching lockfile config
    expected_lockfiles: list[str] = []
    for config in LOCKFILE_CONFIGS:
        if config.ecosystem == ecosystem:
            expected_lockfiles = config.lockfiles
            break

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
            if isinstance(dep_count, int) and dep_count > 0:
                warnings.append(SupplyChainWarning(
                    warning_type="missing_lockfile",
                    severity="MEDIUM",
                    details=f"No lockfile found for {ecosystem}. "
                            f"Expected one of: {', '.join(expected_lockfiles)}. "
                            f"Found {dep_count} dependencies without version pinning.",
                ))

    return warnings


def check_repo_vulns(owner: str, repo: str, language: str | None = None) -> SupplyChainResult:
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
    high_cves: list[VulnFinding] = []
    for advisory in advisories:
        vuln = parse_advisory_for_high_cves(advisory)
        if vuln:
            high_cves.append(vuln)

    result.vulnerabilities = high_cves

    # Check for malicious packages
    dependencies: list[dict[str, object]] = []
    if dep_summary and isinstance(dep_summary.get("dependencies"), list):
        dependencies = dep_summary.get("dependencies", [])  # type: ignore

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
    lines: list[str] = []

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
