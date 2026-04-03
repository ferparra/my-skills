#!/usr/bin/env python3
"""
Skill test harness.

Scans all skills with a `tests/` subdirectory, runs pytest for each,
reports pass/fail per skill, and exits 1 if any test fails.

Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""
from __future__ import annotations

import subprocess
import sys
import json
from pathlib import Path
from typing import TypedDict


class SkillTestResult(TypedDict):
    skill: str
    passed: bool
    tests_dir: Path
    output: str


def find_skills_with_tests(skills_root: Path) -> list[tuple[Path, Path]]:
    """
    Find all skills that have a tests/ subdirectory.

    Returns:
        List of (skill_dir, tests_dir) tuples
    """
    results = []
    for skill_md in skills_root.rglob("SKILL.md"):
        skill_dir = skill_md.parent
        tests_dir = skill_dir / "tests"
        if tests_dir.is_dir():
            results.append((skill_dir, tests_dir))
    return sorted(results, key=lambda x: x[0].name)


def run_pytest(tests_dir: Path, skill_name: str) -> tuple[bool, str]:
    """
    Run pytest on a skill's tests directory.

    Returns:
        (passed, output)
    """
    try:
        result = subprocess.run(
            ["pytest", str(tests_dir), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
        return passed, output
    except subprocess.TimeoutExpired:
        return False, f"pytest timed out after 120 seconds for {skill_name}"
    except FileNotFoundError:
        return False, f"pytest not found - install with: pip install pytest"
    except Exception as e:
        return False, f"Error running pytest for {skill_name}: {e}"


def main() -> int:
    # Find the repo root
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent

    # Find skills with tests
    skills_with_tests = find_skills_with_tests(repo_root)

    if not skills_with_tests:
        print("No skills with tests/ directories found.")
        return 0

    print(f"Found {len(skills_with_tests)} skills with tests/\n")

    results: list[SkillTestResult] = []
    all_passed = True

    for skill_dir, tests_dir in skills_with_tests:
        skill_name = skill_dir.name
        print(f"Testing: {skill_name}...")

        passed, output = run_pytest(tests_dir, skill_name)
        results.append({
            "skill": skill_name,
            "passed": passed,
            "tests_dir": tests_dir,
            "output": output,
        })

        if passed:
            print(f"  PASSED: {skill_name}")
        else:
            print(f"  FAILED: {skill_name}")
            all_passed = False

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count

    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['skill']}")

    print()
    print(f"Total: {len(results)} skills with tests")
    print(f"Passed: {passed_count}")
    print(f"Failed: {failed_count}")

    if not all_passed:
        print("\n" + "=" * 60)
        print("FAILED SKILLS - DETAILED OUTPUT")
        print("=" * 60)
        for r in results:
            if not r["passed"]:
                print(f"\n--- {r['skill']} ---")
                print(r["output"][-2000:] if len(r["output"]) > 2000 else r["output"])

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
