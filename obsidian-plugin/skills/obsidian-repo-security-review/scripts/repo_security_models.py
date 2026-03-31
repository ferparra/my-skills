"""Pydantic models for repository security review."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel, Field


@dataclass
class PIIFinding:
    """Represents a PII finding in a repository."""
    type: str
    severity: str
    file_path: str
    line_number: int
    matched_text: str
    context: str


@dataclass
class VulnFinding:
    """Represents a vulnerability finding."""
    cve_id: str | None
    severity: str
    package_name: str
    package_ecosystem: str
    affected_versions: str
    fixed_version: str | None
    description: str
    html_url: str | None


@dataclass
class SupplyChainWarning:
    """Represents a supply chain warning."""
    warning_type: str
    severity: str
    details: str


class SupplyChainResult(BaseModel):
    """Result of supply chain scan for a repository."""
    repo_name: str
    status: str  # CLEAN, WARN, VULN
    vulnerabilities: list[VulnFinding] = Field(default_factory=list)
    warnings: list[SupplyChainWarning] = Field(default_factory=list)
    dependency_graph_available: bool = False
    advisories_available: bool = False


class RepoInfo(BaseModel):
    """Information about a repository."""
    name: str
    private: bool
    language: str | None
    default_branch: str
    has_wiki: bool


class RepoSupplyChain(BaseModel):
    """Supply chain scan results for a repository."""
    status: str  # CLEAN, WARN, VULN
    vulnerabilities: list[dict[str, object]] = Field(default_factory=list)
    warnings: list[dict[str, object]] = Field(default_factory=list)


class RepoPII(BaseModel):
    """PII scan results for a repository."""
    status: str  # CLEAN, RISK, REVIEW
    findings: list[dict[str, object]] = Field(default_factory=list)


class RepoContributor(BaseModel):
    """Contributor audit results for a repository."""
    status: str  # CLEAN, REVIEW
    unknown_contributors: list[str] = Field(default_factory=list)


class MonthlySecurityReport(BaseModel):
    """Monthly security review report for all repositories."""
    report_date: str
    owner: str
    total_repos_scanned: int
    repos_with_vulns: int
    repos_with_pii: int
    repos_with_unknown_contributors: int
    repo_reports: list[SingleRepoReport] = Field(default_factory=list)


class SingleRepoReport(BaseModel):
    """Security report for a single repository."""
    repo_name: str
    private: bool
    language: str | None
    supply_chain: RepoSupplyChain
    pii: RepoPII
    contributors: RepoContributor
    scanned_at: str


class PIIPatternConfig(BaseModel):
    """Configuration for a PII detection pattern."""
    pattern: str
    severity: str
    description: str
    exclude_domains: list[str] = Field(default_factory=list)


class MaliciousPackage(BaseModel):
    """Information about a known malicious package."""
    severity: str
    description: str
    attack_type: str


class LockfileConfig(BaseModel):
    """Lockfile requirements for an ecosystem."""
    ecosystem: str
    lockfiles: list[str]
