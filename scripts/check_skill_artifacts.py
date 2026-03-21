from __future__ import annotations

import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

PLUGIN_SKILL_DIRS: list[Path] = [
    REPO_ROOT / "obsidian-plugin" / "skills",
    REPO_ROOT / "productivity-plugin" / "skills",
]


def check_skills() -> list[str]:
    errors: list[str] = []
    ok_count = 0

    for plugin_skills_dir in PLUGIN_SKILL_DIRS:
        if not plugin_skills_dir.is_dir():
            errors.append(f"✗ Plugin skills directory not found: {plugin_skills_dir}")
            continue

        skill_dirs = sorted(p for p in plugin_skills_dir.iterdir() if p.is_dir())

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
            symlink = REPO_ROOT / "skills" / name
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
                errors.append(f"✗ {name}:")
                errors.extend(skill_errors)
            else:
                ok_count += 1

    check_skills._ok_count = ok_count  # type: ignore[attr-defined]
    return errors


def main() -> None:
    errors = check_skills()
    ok_count: int = getattr(check_skills, "_ok_count", 0)

    if errors:
        for line in errors:
            print(line)
        sys.exit(1)

    print(f"✓ Skill artifact check passed — {ok_count} skills OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
