from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# All plugin skill directories to scan (where .skill files live alongside skill dirs)
PLUGIN_SKILL_DIRS: list[Path] = [
    REPO_ROOT / "obsidian-plugin" / "skills",
    REPO_ROOT / "productivity-plugin" / "skills",
    REPO_ROOT / "research-plugin" / "skills",
]

# Top-level skills/ directory (contains symlinks to plugin skills + standalone skills)
TOP_LEVEL_SKILLS_DIR = REPO_ROOT / "skills"


def check_plugin_skills(plugin_skills_dir: Path) -> tuple[list[str], int]:
    """Check skills under a plugin directory (obsidian-plugin, productivity-plugin, research-plugin)."""
    errors: list[str] = []
    ok_count = 0

    if not plugin_skills_dir.is_dir():
        errors.append(f"✗ Plugin skills directory not found: {plugin_skills_dir}")
        return errors, ok_count

    # Collect all .skill files in this plugin directory (for orphan detection)
    skill_files_in_plugin = {
        p.stem for p in plugin_skills_dir.glob("*.skill")
    }

    # Collect all skill directories (real dirs, not symlinks)
    skill_dirs_in_plugin = {
        p.name for p in plugin_skills_dir.iterdir() if p.is_dir() and not p.is_symlink()
    }

    # (orphan detection) .skill zip exists but no corresponding directory
    orphaned = skill_files_in_plugin - skill_dirs_in_plugin
    for orphan_name in sorted(orphaned):
        errors.append(
            f"✗ orphaned .skill file (no corresponding directory): "
            f"{plugin_skills_dir.relative_to(REPO_ROOT)}/{orphan_name}.skill"
        )

    # Check each skill directory
    skill_dirs = sorted(
        p for p in plugin_skills_dir.iterdir() if p.is_dir() and not p.is_symlink()
    )

    for skill_dir in skill_dirs:
        name = skill_dir.name
        skill_errors: list[str] = []

        # (a) .skill file exists alongside the skill directory
        skill_file = plugin_skills_dir / f"{name}.skill"
        if not skill_file.exists():
            skill_errors.append(
                f"  missing .skill file: {skill_file.relative_to(REPO_ROOT)}"
            )
        else:
            # (b) .skill file is a valid zip
            if not zipfile.is_zipfile(skill_file):
                skill_errors.append(
                    f"  .skill file is not a valid zip: {skill_file.relative_to(REPO_ROOT)}"
                )
            else:
                # (c) SKILL.md present at root of zip
                with zipfile.ZipFile(skill_file) as zf:
                    if "SKILL.md" not in zf.namelist():
                        skill_errors.append(
                            f"  SKILL.md not found at zip root in: {skill_file.relative_to(REPO_ROOT)}"
                        )

        # (d) top-level symlink exists at skills/<name>
        symlink = TOP_LEVEL_SKILLS_DIR / name
        if not symlink.is_symlink():
            skill_errors.append(f"  missing top-level symlink: skills/{name}")
        else:
            # (e) symlink resolves to the correct skill directory
            resolved = symlink.resolve()
            expected = skill_dir.resolve()
            if resolved != expected:
                skill_errors.append(
                    f"  symlink skills/{name} points to {resolved} "
                    f"(expected {expected})"
                )

        if skill_errors:
            errors.append(f"✗ {name} ({plugin_skills_dir.relative_to(REPO_ROOT)}):")
            errors.extend(skill_errors)
        else:
            ok_count += 1

    return errors, ok_count


def check_top_level_skills(top_level_dir: Path) -> tuple[list[str], int]:
    """
    Check standalone skills directly under the top-level skills/ directory.
    These are actual skill directories (not symlinks to plugin directories).
    Example: skills/game-theory-engine/
    """
    errors: list[str] = []
    ok_count = 0

    if not top_level_dir.is_dir():
        errors.append(f"✗ Top-level skills directory not found: {top_level_dir}")
        return errors, ok_count

    for skill_dir in sorted(
        p for p in top_level_dir.iterdir()
        if p.is_dir() and not p.is_symlink()
    ):
        name = skill_dir.name
        skill_errors: list[str] = []

        # (a) .skill file exists alongside the skill directory
        skill_file = top_level_dir / f"{name}.skill"
        if not skill_file.exists():
            skill_errors.append(
                f"  missing .skill file: {skill_file.relative_to(REPO_ROOT)}"
            )
        else:
            # (b) .skill file is a valid zip
            if not zipfile.is_zipfile(skill_file):
                skill_errors.append(
                    f"  .skill file is not a valid zip: {skill_file.relative_to(REPO_ROOT)}"
                )
            else:
                # (c) SKILL.md present at root of zip
                with zipfile.ZipFile(skill_file) as zf:
                    if "SKILL.md" not in zf.namelist():
                        skill_errors.append(
                            f"  SKILL.md not found at zip root in: {skill_file.relative_to(REPO_ROOT)}"
                        )

        # Note: No symlink check for standalone skills in skills/
        # (symlinks in skills/ point TO plugin directories, not FROM them)

        if skill_errors:
            errors.append(f"✗ {name} (skills/):")
            errors.extend(skill_errors)
        else:
            ok_count += 1

    return errors, ok_count


def main() -> None:
    all_errors: list[str] = []
    total_ok = 0

    # Check plugin-based skills (with symlink requirements)
    for plugin_dir in PLUGIN_SKILL_DIRS:
        errors, ok = check_plugin_skills(plugin_dir)
        all_errors.extend(errors)
        total_ok += ok

    # Check top-level standalone skills (no symlink requirement)
    errors, ok = check_top_level_skills(TOP_LEVEL_SKILLS_DIR)
    all_errors.extend(errors)
    total_ok += ok

    if all_errors:
        for line in all_errors:
            print(line)
        sys.exit(1)

    print(f"✓ Skill artifact check passed — {total_ok} skills OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
